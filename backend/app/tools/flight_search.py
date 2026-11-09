"""Tool 1 - Flight search over flights.json."""

from __future__ import annotations

from datetime import date

from app.models.schemas import FlightOption, FlightPreference, FlightSearchResult
from app.services.data_repository import (
    DatasetRepository, get_repository, normalise_city,
)

PREFERENCE_WEIGHTS = {
    FlightPreference.CHEAPEST: (0.85, 0.15),
    FlightPreference.FASTEST: (0.15, 0.85),
    FlightPreference.BALANCED: (0.5, 0.5),
}


def _fmt_duration(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _date_match(departure: date, travel_date: date | None) -> str:
    if travel_date is None:
        return "none"
    if departure == travel_date:
        return "exact"
    if departure.month == travel_date.month:
        return "same_month"
    return "none"


def search_flights(
    origin: str,
    destination: str,
    travel_date: date | None = None,
    travelers: int = 1,
    preference: FlightPreference = FlightPreference.BALANCED,
    max_results: int = 5,
    repo: DatasetRepository | None = None,
) -> FlightSearchResult:
    """Find direct flights from ``origin`` to ``destination``.

    Flights are scored on normalised price and duration (weights depend on
    ``preference``) with a small bonus when the dataset date matches the
    requested date. Prices in the dataset are per person.
    """
    repo = repo or get_repository()
    origin = normalise_city(origin, repo)
    destination = normalise_city(destination, repo)
    frame = repo.flights
    matches = frame[
        (frame["from"].str.lower() == origin.lower())
        & (frame["to"].str.lower() == destination.lower())
    ]

    if matches.empty:
        routes = repo.routes()
        from_origin = routes.get(origin, [])
        into_destination = sorted(
            src for src, dests in routes.items() if destination in dests
        )
        return FlightSearchResult(
            origin=origin, destination=destination, travel_date=travel_date,
            preference=preference, travelers=travelers, options=[],
            note=(
                f"No direct flight from {origin} to {destination} exists in "
                "flights.json. No flight was invented."
            ),
            alternatives={
                f"direct_from_{origin}": from_origin,
                f"direct_into_{destination}": into_destination,
            },
        )

    prices = matches["price"]
    durations = matches["duration_minutes"]
    price_span = max(int(prices.max() - prices.min()), 1)
    duration_span = max(int(durations.max() - durations.min()), 1)
    w_price, w_duration = PREFERENCE_WEIGHTS[preference]

    cheapest_id = matches.loc[prices.idxmin(), "flight_id"]
    fastest_id = matches.loc[durations.idxmin(), "flight_id"]

    options: list[FlightOption] = []
    for _, row in matches.iterrows():
        price_norm = (row["price"] - prices.min()) / price_span
        duration_norm = (row["duration_minutes"] - durations.min()) / duration_span
        match = _date_match(row["departure_time"].date(), travel_date)
        bonus = {"exact": 0.2, "same_month": 0.05, "none": 0.0}[match]
        score = round(1 - (w_price * price_norm + w_duration * duration_norm)
                      + bonus, 4)
        tags = []
        if row["flight_id"] == cheapest_id:
            tags.append("cheapest")
        if row["flight_id"] == fastest_id:
            tags.append("fastest")
        if match == "exact":
            tags.append("date_match")
        options.append(FlightOption(
            flight_id=row["flight_id"],
            airline=row["airline"],
            origin=row["from"],
            destination=row["to"],
            departure_time=row["departure_time"].to_pydatetime(),
            arrival_time=row["arrival_time"].to_pydatetime(),
            duration_minutes=int(row["duration_minutes"]),
            price_per_person=int(row["price"]),
            total_price=int(row["price"]) * travelers,
            date_match=match,
            tags=tags,
            score=score,
        ))

    options.sort(key=lambda o: o.score, reverse=True)
    if len(options) > 1:
        options[0].tags.append("best_" + preference.value)
    for option in options:
        option.reason = _explain(option, preference, len(options))

    note = ""
    if travel_date and not any(o.date_match == "exact" for o in options):
        note = (
            f"The dataset has no flight on {travel_date.isoformat()} for this "
            "route; the dataset's scheduled departure date is shown on each "
            "option. Treat times and fares as the route's reference schedule."
        )

    return FlightSearchResult(
        origin=origin, destination=destination, travel_date=travel_date,
        preference=preference, travelers=travelers,
        options=options[:max_results], cheapest_id=cheapest_id,
        fastest_id=fastest_id, recommended_id=options[0].flight_id, note=note,
    )


def _explain(option: FlightOption, preference: FlightPreference,
             count: int) -> str:
    parts = [
        f"{option.airline} {option.flight_id}: Rs {option.price_per_person:,}"
        f"/person, {_fmt_duration(option.duration_minutes)}"
    ]
    if count == 1:
        parts.append("the only direct flight on this route in the dataset")
    else:
        if "cheapest" in option.tags:
            parts.append("cheapest on the route")
        if "fastest" in option.tags:
            parts.append("shortest flight time")
        if f"best_{preference.value}" in option.tags:
            parts.append(f"top score for a '{preference.value}' preference")
    if option.date_match == "exact":
        parts.append("departs on your travel date")
    return "; ".join(parts) + "."
