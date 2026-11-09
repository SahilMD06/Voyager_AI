"""Tool 2 - Hotel recommendations over hotels.json."""

from __future__ import annotations

import math

from app.config import get_settings
from app.models.schemas import AccommodationType, HotelOption, HotelSearchResult
from app.services.data_repository import (
    DatasetRepository, get_repository, normalise_city,
)


def hotel_tier(stars: int, name: str) -> str:
    """Classify a hotel into an accommodation tier from its stars and name."""
    if "resort" in name.lower():
        return "resort"
    if stars >= 5:
        return "luxury"
    if stars >= 3:
        return "mid-range"
    return "budget"


def _matches_type(tier: str, stars: int, wanted: AccommodationType) -> bool:
    if wanted == AccommodationType.ANY:
        return True
    if wanted == AccommodationType.RESORT:
        return tier == "resort"
    if wanted == AccommodationType.LUXURY:
        return stars >= 5
    if wanted == AccommodationType.MID_RANGE:
        return 3 <= stars <= 4
    return stars <= 3  # budget


def recommend_hotels(
    city: str,
    nights: int,
    travelers: int = 1,
    max_price_per_night: int | None = None,
    accommodation_type: AccommodationType = AccommodationType.ANY,
    preferred_amenities: list[str] | None = None,
    max_results: int = 5,
    repo: DatasetRepository | None = None,
) -> HotelSearchResult:
    """Rank hotels in ``city`` by stars, value, amenities and fit.

    ``max_price_per_night`` is a per-room soft cap: hotels above it are kept
    but flagged ``within_budget=False`` and ranked lower, so the traveller can
    still see what over-budget options exist.
    """
    repo = repo or get_repository()
    settings = get_settings()
    city = normalise_city(city, repo)
    wanted_amenities = {a.strip().lower() for a in preferred_amenities or []}
    frame = repo.hotels[repo.hotels["city"].str.lower() == city.lower()]

    if frame.empty:
        return HotelSearchResult(
            city=city, nights=nights, travelers=travelers, options=[],
            note=f"hotels.json has no hotels in {city}.",
        )

    rooms = math.ceil(travelers / settings.travelers_per_room)
    min_price = int(frame["price_per_night"].min())
    max_price = int(frame["price_per_night"].max())
    span = max(max_price - min_price, 1)

    options: list[HotelOption] = []
    for _, row in frame.iterrows():
        tier = hotel_tier(int(row["stars"]), row["name"])
        type_fit = _matches_type(tier, int(row["stars"]), accommodation_type)
        within = (
            max_price_per_night is None
            or row["price_per_night"] <= max_price_per_night
        )
        amenity_hits = wanted_amenities & set(row["amenities"])
        value = 1 - (row["price_per_night"] - min_price) / span
        score = (
            0.40 * (row["stars"] / 5)
            + 0.30 * value
            + 0.10 * (len(row["amenities"]) / 5)
            + 0.10 * (len(amenity_hits) / max(len(wanted_amenities), 1))
            + (0.25 if type_fit else 0)
            - (0.45 if not within else 0)
        )
        options.append(HotelOption(
            hotel_id=row["hotel_id"],
            name=row["name"],
            city=row["city"],
            stars=int(row["stars"]),
            price_per_night=int(row["price_per_night"]),
            amenities=list(row["amenities"]),
            tier=tier,
            rooms_needed=rooms,
            total_stay_cost=int(row["price_per_night"]) * rooms * nights,
            within_budget=bool(within),
            score=round(float(score), 4),
            reason=_explain(row, tier, type_fit, within, amenity_hits,
                            accommodation_type, min_price),
        ))

    options.sort(key=lambda o: o.score, reverse=True)
    note_parts = [
        f"{rooms} room(s) for {travelers} traveller(s) x {nights} night(s).",
    ]
    if accommodation_type != AccommodationType.ANY and not any(
        _matches_type(o.tier, o.stars, accommodation_type) for o in options
    ):
        note_parts.append(
            f"No '{accommodation_type.value}' hotel exists in {city}; showing "
            "the best alternatives."
        )
    if max_price_per_night and not any(o.within_budget for o in options):
        note_parts.append(
            f"Every hotel in {city} costs more than Rs "
            f"{max_price_per_night:,}/night."
        )
    return HotelSearchResult(
        city=city, nights=nights, travelers=travelers,
        options=options[:max_results], recommended_id=options[0].hotel_id,
        note=" ".join(note_parts),
    )


def _explain(row, tier, type_fit, within, amenity_hits, wanted, min_price):
    parts = [f"{row['stars']}-star {tier} at Rs {row['price_per_night']:,}/night"]
    if row["price_per_night"] == min_price:
        parts.append("lowest nightly rate in the city")
    if type_fit and wanted != AccommodationType.ANY:
        parts.append(f"matches your '{wanted.value}' preference")
    if amenity_hits:
        parts.append("has " + ", ".join(sorted(amenity_hits)))
    if not within:
        parts.append("above your nightly budget")
    return "; ".join(parts) + "."
