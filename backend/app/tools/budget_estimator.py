"""Tool 5 - Budget estimation.

Dataset prices (flights, hotels) are looked up by ID so the LLM can never
invent a fare. Food, local transport and activities are clearly marked as
estimates derived from configurable assumptions in ``config.py``.

All totals are for the whole group. Flight prices in the dataset are per
person; hotel prices are per room per night.
"""

from __future__ import annotations

import math

from app.config import get_settings
from app.models.schemas import AccommodationType, BudgetBreakdown, BudgetLine
from app.services.data_repository import DatasetRepository, get_repository
from app.tools.places_search import CATEGORY_COST_ESTIMATE


def food_rate(accommodation_type: AccommodationType | str,
              hotel_stars: int | None = None) -> int:
    """Per-person daily food estimate.

    When a hotel is chosen its star rating decides the tier (5 stars =
    luxury, 2 or fewer = budget, otherwise mid-range). That keeps every
    budget calculation consistent no matter which accommodation_type an LLM
    passes in. ``accommodation_type`` is used only when there is no hotel.
    """
    settings = get_settings()
    if hotel_stars is not None:
        if hotel_stars >= 5:
            return settings.food_per_person_per_day_luxury
        if hotel_stars <= 2:
            return settings.food_per_person_per_day_budget
        return settings.food_per_person_per_day_mid
    value = getattr(accommodation_type, "value", accommodation_type)
    if value == "luxury":
        return settings.food_per_person_per_day_luxury
    if value == "budget":
        return settings.food_per_person_per_day_budget
    return settings.food_per_person_per_day_mid


def estimate_budget(
    travelers: int,
    nights: int,
    outbound_flight_id: str | None = None,
    return_flight_id: str | None = None,
    hotel_id: str | None = None,
    place_ids: list[str] | None = None,
    accommodation_type: AccommodationType | str = AccommodationType.ANY,
    user_budget: int | None = None,
    repo: DatasetRepository | None = None,
) -> BudgetBreakdown:
    """Compute a group budget without double counting.

    * Flights: dataset fare per person x travellers, per leg.
    * Hotel: dataset nightly rate x rooms x nights.
    * Food: per-person daily estimate x travellers x days.
    * Local transport: per-vehicle daily estimate x vehicles x days.
    * Activities: per-person category estimate x travellers, each place once.
    """
    repo = repo or get_repository()
    settings = get_settings()
    days = nights + 1
    lines: list[BudgetLine] = []
    notes: list[str] = ["All amounts are group totals in INR."]

    flight_total = 0
    flight_details = []
    for leg, flight_id in (("Outbound", outbound_flight_id),
                           ("Return", return_flight_id)):
        if not flight_id:
            continue
        flight = repo.flight_by_id(flight_id)
        if not flight:
            notes.append(f"{leg} flight {flight_id} not found in dataset; "
                         "excluded.")
            continue
        cost = int(flight["price"]) * travelers
        flight_total += cost
        flight_details.append(
            f"{leg} {flight['airline']} {flight_id}: Rs {int(flight['price']):,}"
            f" x {travelers}"
        )
    if flight_details:
        lines.append(BudgetLine(category="Flights", amount=flight_total,
                                basis="dataset",
                                detail="; ".join(flight_details)))
    else:
        notes.append("No flight cost included (no flight selected).")

    hotel_stars: int | None = None
    if hotel_id:
        hotel = repo.hotel_by_id(hotel_id)
        if hotel:
            hotel_stars = int(hotel["stars"])
            rooms = math.ceil(travelers / settings.travelers_per_room)
            cost = int(hotel["price_per_night"]) * rooms * nights
            lines.append(BudgetLine(
                category="Accommodation", amount=cost, basis="dataset",
                detail=f"{hotel['name']}: Rs {int(hotel['price_per_night']):,}"
                       f"/night x {rooms} room(s) x {nights} night(s)",
            ))
        else:
            notes.append(f"Hotel {hotel_id} not found in dataset; excluded.")

    rate = food_rate(accommodation_type, hotel_stars)
    tier = (f"matched to a {hotel_stars}-star hotel" if hotel_stars
            else "by stay type")
    lines.append(BudgetLine(
        category="Food", amount=rate * travelers * days, basis="estimate",
        detail=f"Rs {rate:,}/person/day ({tier}) x {travelers} x {days} "
               "day(s)",
    ))

    vehicles = math.ceil(travelers / settings.travelers_per_vehicle)
    transport_days = max(days - 1, 1)  # arrival/departure days use 1 combined
    transport = (settings.local_transport_per_vehicle_per_day * vehicles
                 * transport_days)
    lines.append(BudgetLine(
        category="Local transport", amount=transport, basis="estimate",
        detail=f"Rs {settings.local_transport_per_vehicle_per_day:,}/vehicle/"
               f"day x {vehicles} vehicle(s) x {transport_days} day(s)",
    ))

    activity_total = 0
    seen: set[str] = set()
    for place_id in place_ids or []:
        if place_id in seen:
            continue
        seen.add(place_id)
        place = repo.place_by_id(place_id)
        if not place:
            continue
        activity_total += CATEGORY_COST_ESTIMATE.get(place["type"], 100) * travelers
    lines.append(BudgetLine(
        category="Activities", amount=activity_total, basis="estimate",
        detail=f"Entry/activity estimates for {len(seen)} attraction(s) x "
               f"{travelers}",
    ))

    dataset_total = sum(l.amount for l in lines if l.basis == "dataset")
    estimated_total = sum(l.amount for l in lines if l.basis == "estimate")
    grand_total = dataset_total + estimated_total
    remaining = user_budget - grand_total if user_budget else None
    return BudgetBreakdown(
        travelers=travelers, nights=nights, lines=lines,
        dataset_total=dataset_total, estimated_total=estimated_total,
        grand_total=grand_total,
        per_person=math.ceil(grand_total / travelers),
        user_budget=user_budget, remaining=remaining,
        within_budget=(remaining >= 0) if remaining is not None else None,
        note=" ".join(notes),
    )
