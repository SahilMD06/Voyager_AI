"""Loads and validates the provided JSON datasets (flights, hotels, places).

The datasets are read once with pandas and cached. Every record is checked
for required fields; malformed records are skipped and reported rather than
silently "fixed".
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import get_settings

logger = logging.getLogger(__name__)

FLIGHT_COLUMNS = [
    "flight_id", "airline", "from", "to",
    "departure_time", "arrival_time", "price",
]
HOTEL_COLUMNS = [
    "hotel_id", "name", "city", "stars", "price_per_night", "amenities",
]
PLACE_COLUMNS = ["place_id", "name", "city", "type", "rating"]


class DatasetError(RuntimeError):
    """Raised when a dataset file is missing or unreadable."""


@dataclass
class DatasetRepository:
    """In-memory, validated view of the three datasets."""

    flights: pd.DataFrame
    hotels: pd.DataFrame
    places: pd.DataFrame
    issues: list[str] = field(default_factory=list)

    # ----------------------------------------------------------------- meta
    def cities(self) -> list[str]:
        """All cities that appear in any dataset."""
        values: set[str] = set()
        values.update(self.flights["from"].unique())
        values.update(self.flights["to"].unique())
        values.update(self.hotels["city"].unique())
        values.update(self.places["city"].unique())
        return sorted(values)

    def routes(self) -> dict[str, list[str]]:
        """Mapping origin -> destinations with at least one direct flight."""
        grouped = self.flights.groupby("from")["to"].unique()
        return {k: sorted(v.tolist()) for k, v in grouped.items()}

    def summary(self) -> dict:
        """Dataset statistics for the /meta endpoint and docs."""
        return {
            "flights": int(len(self.flights)),
            "hotels": int(len(self.hotels)),
            "places": int(len(self.places)),
            "airlines": sorted(self.flights["airline"].unique().tolist()),
            "place_categories": sorted(self.places["type"].unique().tolist()),
            "flight_date_range": [
                self.flights["departure_time"].min().date().isoformat(),
                self.flights["departure_time"].max().date().isoformat(),
            ],
            "issues": self.issues,
        }

    # -------------------------------------------------------------- lookups
    def flight_by_id(self, flight_id: str) -> dict | None:
        """Return one flight row as a dict, or None."""
        rows = self.flights[self.flights["flight_id"] == flight_id]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def hotel_by_id(self, hotel_id: str) -> dict | None:
        """Return one hotel row as a dict, or None."""
        rows = self.hotels[self.hotels["hotel_id"] == hotel_id]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def place_by_id(self, place_id: str) -> dict | None:
        """Return one place row as a dict, or None."""
        rows = self.places[self.places["place_id"] == place_id]
        return rows.iloc[0].to_dict() if not rows.empty else None


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        raise DatasetError(f"Dataset not found: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise DatasetError(f"Invalid JSON in {path.name}: {exc}") from exc
    if isinstance(data, dict):
        # Accept {"flights": [...]} style wrappers as well as bare lists.
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if lists else []
    if not isinstance(data, list):
        raise DatasetError(f"{path.name} must contain a list of records")
    return data


def _validate(
    records: list[dict], columns: list[str], name: str, issues: list[str]
) -> pd.DataFrame:
    valid = []
    for index, record in enumerate(records):
        missing = [c for c in columns if record.get(c) in (None, "")]
        if missing:
            issues.append(f"{name}[{index}] skipped: missing {missing}")
            continue
        valid.append(record)
    return pd.DataFrame(valid, columns=columns)


def load_repository(data_dir: Path | None = None) -> DatasetRepository:
    """Load all datasets from ``data_dir`` and normalise their types."""
    data_dir = data_dir or get_settings().data_dir
    issues: list[str] = []

    flights = _validate(
        _read_json(data_dir / "flights.json"), FLIGHT_COLUMNS, "flights", issues
    )
    flights["departure_time"] = pd.to_datetime(
        flights["departure_time"], errors="coerce"
    )
    flights["arrival_time"] = pd.to_datetime(
        flights["arrival_time"], errors="coerce"
    )
    flights["price"] = pd.to_numeric(flights["price"], errors="coerce")
    bad = flights[
        flights[["departure_time", "arrival_time", "price"]].isna().any(axis=1)
    ]
    for fid in bad["flight_id"]:
        issues.append(f"flight {fid} skipped: unparseable time or price")
    flights = flights.drop(bad.index)
    flights["duration_minutes"] = (
        (flights["arrival_time"] - flights["departure_time"])
        .dt.total_seconds() // 60
    ).astype(int)
    negative = flights[flights["duration_minutes"] <= 0]
    for fid in negative["flight_id"]:
        issues.append(f"flight {fid} skipped: arrival before departure")
    flights = flights.drop(negative.index).reset_index(drop=True)
    flights["price"] = flights["price"].astype(int)

    hotels = _validate(
        _read_json(data_dir / "hotels.json"), HOTEL_COLUMNS, "hotels", issues
    )
    hotels["stars"] = pd.to_numeric(hotels["stars"], errors="coerce")
    hotels["price_per_night"] = pd.to_numeric(
        hotels["price_per_night"], errors="coerce"
    )
    hotels = hotels.dropna(subset=["stars", "price_per_night"])
    hotels["stars"] = hotels["stars"].astype(int)
    hotels["price_per_night"] = hotels["price_per_night"].astype(int)
    hotels["amenities"] = hotels["amenities"].apply(
        lambda a: [str(x).lower() for x in a] if isinstance(a, list) else []
    )
    hotels = hotels.reset_index(drop=True)

    places = _validate(
        _read_json(data_dir / "places.json"), PLACE_COLUMNS, "places", issues
    )
    places["rating"] = pd.to_numeric(places["rating"], errors="coerce")
    places = places.dropna(subset=["rating"])
    places["type"] = places["type"].str.lower()
    places = places.reset_index(drop=True)

    for frame, col in ((flights, "from"), (flights, "to"),
                       (hotels, "city"), (places, "city")):
        frame[col] = frame[col].astype(str).str.strip()

    if issues:
        logger.warning("Dataset issues: %s", issues)
    logger.info(
        "Loaded %d flights, %d hotels, %d places",
        len(flights), len(hotels), len(places),
    )
    return DatasetRepository(flights, hotels, places, issues)


@lru_cache
def get_repository() -> DatasetRepository:
    """Cached repository singleton."""
    return load_repository()


def normalise_city(city: str, repo: DatasetRepository | None = None) -> str:
    """Map user input onto the dataset's city spelling (case-insensitive).

    A few common alternate spellings are accepted (Bengaluru -> Bangalore,
    Bombay -> Mumbai, ...). Unknown cities are returned title-cased.
    """
    repo = repo or get_repository()
    aliases = {
        "bengaluru": "bangalore", "bombay": "mumbai", "madras": "chennai",
        "calcutta": "kolkata", "new delhi": "delhi", "panaji": "goa",
        "panjim": "goa",
    }
    key = city.strip().lower()
    key = aliases.get(key, key)
    for known in repo.cities():
        if known.lower() == key:
            return known
    return city.strip().title()
