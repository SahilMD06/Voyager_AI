"""Validates an itinerary draft against real tool data and builds a TripPlan.

This is the anti-hallucination layer. Whatever the LLM proposes:
* flight / hotel / place ids must exist in the data the tools returned,
* any missing tool data is fetched (and logged as a validation step),
* the budget is recomputed from the final selections,
* every day gets the real weather for its date.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta

from app.agents.itinerary_scheduler import schedule_days
from app.config import get_settings
from app.models.schemas import (
    Activity, ActivityDraft, AgentPlanDraft, AgentStep, DayDraft, DayPlan,
    DecisionExplanations, DestinationInfo, FlightOption, FlightSearchResult,
    HotelOption, HotelSearchResult, PlaceOption, PlacesSearchResult,
    TripPlan, TripRequest, WeatherResult,
)
from app.services.data_repository import get_repository, normalise_city
from app.services.destination_service import get_destination_profile
from app.tools.budget_estimator import estimate_budget, food_rate
from app.tools.flight_search import search_flights
from app.tools.hotel_search import recommend_hotels
from app.tools.places_search import discover_places
from app.tools.registry import ToolLedger
from app.tools.weather_lookup import lookup_weather


def suggested_nightly_cap(request: TripRequest) -> int:
    """Heuristic per-room nightly cap: ~40% of the budget for lodging."""
    rooms = math.ceil(request.travelers / get_settings().travelers_per_room)
    return int(request.budget * 0.4 / max(request.nights, 1) / rooms)


# --------------------------------------------------------------------------
# Ensure tool coverage
# --------------------------------------------------------------------------


def _find_flights(ledger: ToolLedger, origin: str,
                  destination: str) -> FlightSearchResult | None:
    for result in reversed(ledger.flight_searches):
        if (result.origin.lower() == origin.lower()
                and result.destination.lower() == destination.lower()):
            return result
    return None


def _find_hotels(ledger: ToolLedger, city: str) -> HotelSearchResult | None:
    for result in reversed(ledger.hotel_searches):
        if result.city.lower() == city.lower():
            return result
    return None


def _find_places(ledger: ToolLedger, city: str) -> PlacesSearchResult | None:
    for result in reversed(ledger.place_searches):
        if result.city.lower() == city.lower():
            return result
    return None


def _find_weather(ledger: ToolLedger, city: str) -> WeatherResult | None:
    for result in reversed(ledger.weather):
        if normalise_city(result.city).lower() == city.lower():
            return result
    return None


def ensure_tool_data(request: TripRequest, ledger: ToolLedger,
                     notes: list[str]) -> dict:
    """Make sure every required dataset/API lookup happened.

    Missing lookups are executed through the ledger (so the UI sees them) and
    recorded in ``notes``.
    """
    origin = normalise_city(request.origin)
    dest = normalise_city(request.destination)

    def need(label: str):
        notes.append(f"Validator ran {label} because the agent did not.")

    outbound = _find_flights(ledger, origin, dest)
    if outbound is None:
        need("search_flights (outbound)")
        ledger.run("search_flights", {"origin": origin, "destination": dest},
                   lambda: search_flights(origin, dest, request.departure_date,
                                          request.travelers,
                                          request.flight_preference),
                   lambda r: f"{len(r.options)} outbound flight(s)")
        outbound = ledger.flight_searches[-1]
    inbound = _find_flights(ledger, dest, origin)
    if inbound is None:
        need("search_flights (return)")
        ledger.run("search_flights", {"origin": dest, "destination": origin},
                   lambda: search_flights(dest, origin, request.return_date,
                                          request.travelers,
                                          request.flight_preference),
                   lambda r: f"{len(r.options)} return flight(s)")
        inbound = ledger.flight_searches[-1]
    hotels = _find_hotels(ledger, dest)
    if hotels is None:
        need("recommend_hotels")
        ledger.run("recommend_hotels", {"city": dest},
                   lambda: recommend_hotels(
                       dest, request.nights, request.travelers,
                       suggested_nightly_cap(request),
                       request.accommodation_type,
                       request.preferred_amenities),
                   lambda r: f"{len(r.options)} hotel(s)")
        hotels = ledger.hotel_searches[-1]
    places = _find_places(ledger, dest)
    if places is None:
        need("discover_places")
        ledger.run("discover_places", {"city": dest},
                   lambda: discover_places(dest, request.interests),
                   lambda r: f"{len(r.options)} place(s)")
        places = ledger.place_searches[-1]
    weather = _find_weather(ledger, dest)
    if weather is None:
        need("get_weather")
        ledger.run("get_weather", {"city": dest},
                   lambda: lookup_weather(dest, request.departure_date,
                                          request.return_date),
                   lambda r: f"weather for {len(r.days)} day(s)")
        weather = ledger.weather[-1] if ledger.weather else None
    return {"outbound": outbound, "inbound": inbound, "hotels": hotels,
            "places": places, "weather": weather}


# --------------------------------------------------------------------------
# Selection validation
# --------------------------------------------------------------------------


def _pick_flight(search: FlightSearchResult, chosen_id: str | None,
                 leg: str, notes: list[str]) -> FlightOption | None:
    if not search.options:
        return None
    by_id = {o.flight_id: o for o in search.options}
    if chosen_id and chosen_id in by_id:
        return by_id[chosen_id]
    fallback = by_id.get(search.recommended_id) or search.options[0]
    if chosen_id:
        notes.append(f"{leg} flight id '{chosen_id}' was not in the search "
                     f"results; replaced with {fallback.flight_id}.")
    else:
        notes.append(f"No {leg.lower()} flight chosen; using top-ranked "
                     f"{fallback.flight_id}.")
    return fallback


def _pick_hotel(search: HotelSearchResult, chosen_id: str | None,
                notes: list[str]) -> HotelOption | None:
    if not search.options:
        return None
    by_id = {o.hotel_id: o for o in search.options}
    if chosen_id and chosen_id in by_id:
        return by_id[chosen_id]
    fallback = by_id.get(search.recommended_id) or search.options[0]
    notes.append(
        f"Hotel id '{chosen_id}' was not in the results; replaced with "
        f"{fallback.hotel_id}." if chosen_id else
        f"No hotel chosen; using top-ranked {fallback.hotel_id}.")
    return fallback


def _convert(drafts: list[ActivityDraft], places: dict[str, PlaceOption],
             used: set[str], notes: list[str]) -> list[Activity]:
    repo = get_repository()
    activities = []
    for draft in drafts:
        if draft.place_id:
            place = places.get(draft.place_id)
            if place is None and (repo.flight_by_id(draft.place_id)
                                  or repo.hotel_by_id(draft.place_id)):
                # A flight/hotel id in the attraction field: keep the
                # activity (e.g. "Check in") without attaching a place.
                activities.append(Activity(title=draft.title,
                                           description=draft.description))
                continue
            if place is None:
                notes.append(f"Removed unknown place id '{draft.place_id}' "
                             f"('{draft.title}').")
                continue
            if draft.place_id in used:
                notes.append(f"Removed duplicate visit to {place.name}.")
                continue
            used.add(draft.place_id)
            activities.append(Activity(title=draft.title,
                                       description=draft.description,
                                       place=place, from_dataset=True))
        else:
            activities.append(Activity(title=draft.title,
                                       description=draft.description))
    return activities


# --------------------------------------------------------------------------
# Build final plan
# --------------------------------------------------------------------------


def build_plan(
    request: TripRequest,
    draft: AgentPlanDraft | None,
    ledger: ToolLedger,
    mode: str,
    model: str | None,
    trace: list[AgentStep],
    extra_warnings: list[str] | None = None,
) -> TripPlan:
    """Validate ``draft`` (may be None) and assemble the final TripPlan."""
    notes: list[str] = []
    data = ensure_tool_data(request, ledger, notes)
    outbound_search: FlightSearchResult = data["outbound"]
    inbound_search: FlightSearchResult = data["inbound"]
    hotel_search: HotelSearchResult = data["hotels"]
    place_search: PlacesSearchResult = data["places"]
    weather: WeatherResult | None = data["weather"]

    outbound = _pick_flight(outbound_search, draft and draft.outbound_flight_id,
                            "Outbound", notes)
    inbound = _pick_flight(inbound_search, draft and draft.return_flight_id,
                           "Return", notes)
    hotel = _pick_hotel(hotel_search, draft and draft.hotel_id, notes)

    places_by_id = {p.place_id: p for s in ledger.place_searches
                    for p in s.options
                    if p.city.lower() == place_search.city.lower()}
    weather_by_date = {d.date: d for d in weather.days} if weather else {}

    fallback_days = schedule_days(request, list(places_by_id.values()),
                                  weather_by_date, outbound, inbound, hotel)
    draft_days: dict[int, DayDraft] = {}
    if draft:
        for day in draft.days:
            if 1 <= day.day <= request.days and day.day not in draft_days:
                draft_days[day.day] = day
        missing = [d for d in range(1, request.days + 1) if d not in draft_days]
        if missing:
            notes.append(f"Agent omitted day(s) {missing}; filled by the "
                         "scheduler.")
        if len(draft.days) > request.days:
            notes.append("Agent produced extra days; trimmed to trip length.")

    used: set[str] = set()
    settings = get_settings()
    per_day_food = food_rate(request.accommodation_type,
                             hotel.stars if hotel else None) \
        * request.travelers
    vehicles = math.ceil(request.travelers / settings.travelers_per_vehicle)
    days: list[DayPlan] = []
    for index in range(1, request.days + 1):
        source = draft_days.get(index) or fallback_days[index - 1]
        date_ = request.departure_date + timedelta(days=index - 1)
        morning = _convert(source.morning, places_by_id, used, notes)
        afternoon = _convert(source.afternoon, places_by_id, used, notes)
        evening = _convert(source.evening, places_by_id, used, notes)
        day_places = [a.place for a in morning + afternoon + evening if a.place]
        activities_cost = sum(p.estimated_entry_cost for p in day_places) \
            * request.travelers
        transport = (settings.local_transport_per_vehicle_per_day * vehicles
                     if index < request.days or request.days == 1 else 0)
        cost = per_day_food + transport + activities_cost
        days.append(DayPlan(
            day=index, date=date_, theme=source.theme,
            weather=weather_by_date.get(date_),
            morning=morning, afternoon=afternoon, evening=evening,
            estimated_cost=cost,
            cost_note=(f"Estimate: food Rs {per_day_food:,}, local transport "
                       f"Rs {transport:,}, entries Rs {activities_cost:,} "
                       "(excludes flights and hotel)"),
            weather_consideration=source.weather_consideration,
            tips=source.tips,
        ))

    scheduled_ids = [a.place.place_id for d in days
                     for a in d.morning + d.afternoon + d.evening if a.place]
    budget = estimate_budget(
        request.travelers, request.nights,
        outbound.flight_id if outbound else None,
        inbound.flight_id if inbound else None,
        hotel.hotel_id if hotel else None,
        scheduled_ids, request.accommodation_type, request.budget,
    )

    warnings = list(extra_warnings or [])
    if draft:
        # The validator adds its own notes about missing flights and dataset
        # dates below; skip the agent's restatements of the same facts.
        covered = ("no direct", "reference schedule", "2025", "dataset date",
                   "flight dataset", "flights.json")
        warnings.extend(w for w in draft.warnings
                        if not any(c in w.lower() for c in covered))
    if not outbound:
        warnings.append(outbound_search.note)
    if not inbound:
        warnings.append(inbound_search.note)
    if outbound and outbound.date_match != "exact":
        warnings.append(
            "Flight times/fares come from the dataset's reference schedule "
            f"(dataset date {outbound.departure_time:%d %b %Y}); confirm "
            "availability for your actual dates.")
    if not hotel:
        warnings.append(hotel_search.note)
    if budget.within_budget is False:
        warnings.append(
            f"Estimated total Rs {budget.grand_total:,} exceeds your budget "
            f"of Rs {request.budget:,} by Rs {-budget.remaining:,}.")
    if weather and weather.note:
        warnings.append(weather.note)
    if draft and mode == "agent" and ledger.budgets:
        quoted = ledger.budgets[-1].grand_total
        if quoted != budget.grand_total:
            warnings.append(
                f"The agent's explanation quotes its last estimate of Rs "
                f"{quoted:,}; after validation the plan's total is Rs "
                f"{budget.grand_total:,} (see Budget breakdown).")
    warnings = list(dict.fromkeys(w for w in warnings if w))

    for note in notes:
        trace.append(AgentStep(index=len(trace) + 1, kind="validation",
                               summary=note))

    use_draft_text = draft is not None and mode == "agent"
    explanations = (draft.explanations if use_draft_text else
                    rule_based_explanations(request, outbound, inbound, hotel,
                                            outbound_search, hotel_search,
                                            days, weather, budget))
    profile = get_destination_profile(place_search.city)
    destination = DestinationInfo(
        city=place_search.city,
        resolved_location=weather.resolved_location if weather else None,
        latitude=weather.latitude if weather else None,
        longitude=weather.longitude if weather else None,
        image_url=profile.get("image_url"),
        image_credit=profile.get("image_credit"),
    )
    title = (draft.trip_title if use_draft_text else
             f"{request.days}-Day Trip to {place_search.city}")
    summary = (draft.summary if use_draft_text else
               f"A {request.days}-day plan from {request.origin} to "
               f"{place_search.city} for {request.travelers} traveller(s), "
               f"built from the provided datasets and live Open-Meteo data.")
    plan = TripPlan(
        plan_id=uuid.uuid4().hex[:12],
        generated_at=datetime.now(),
        mode=mode, model=model, request=request,
        trip_title=title, summary=summary, destination=destination,
        outbound_flight=outbound, return_flight=inbound,
        flight_options_outbound=outbound_search.options,
        flight_options_return=inbound_search.options,
        hotel=hotel, hotel_options=hotel_search.options,
        places=list(places_by_id.values()), weather=weather, days=days,
        budget=budget, explanations=explanations,
        general_tips=(draft.general_tips if draft else []),
        warnings=warnings, agent_trace=trace, readable_summary="",
    )
    plan.readable_summary = render_readable(plan)
    return plan


def rule_based_explanations(request, outbound, inbound, hotel,
                            outbound_search, hotel_search, days, weather,
                            budget) -> DecisionExplanations:
    """Explanations built from the deterministic decision criteria."""
    pref = request.flight_preference.value
    if outbound:
        flight = (f"Chosen by the '{pref}' scoring rule (price/duration "
                  f"weights) from {len(outbound_search.options)} direct "
                  f"option(s): {outbound.reason}")
        if inbound:
            flight += f" Return: {inbound.reason}"
    else:
        flight = outbound_search.note
    hotel_text = (f"Highest score among {len(hotel_search.options)} hotel(s) "
                  f"(stars 40%, value 30%, amenities 20%, type fit bonus): "
                  f"{hotel.reason}" if hotel else hotel_search.note)
    visited = [a.place for d in days for a in d.morning + d.afternoon + d.evening
               if a.place]
    attractions = ("Ranked by rating (60%) and interest match (40%): "
                   + "; ".join(f"{p.name} ({p.category}, {p.rating})"
                               for p in visited)) if visited else \
        "No attractions for this city in places.json."
    wet = [d.day for d in days if d.weather and d.weather.icon in
           {"rain", "storm"}]
    weather_text = ("Outdoor categories were placed on drier days and indoor "
                    "ones on wet days"
                    + (f" (wet: day {', '.join(map(str, wet))})" if wet else
                       "; no wet days detected")
                    + ". Each day holds at most two attractions to keep "
                      "travel time realistic.")
    budget_text = (f"Estimated Rs {budget.grand_total:,} vs budget Rs "
                   f"{request.budget:,}: dataset prices Rs "
                   f"{budget.dataset_total:,}, estimates Rs "
                   f"{budget.estimated_total:,}. "
                   + ("Within budget." if budget.within_budget else
                      "Over budget - the cheapest valid alternatives were "
                      "tried first."))
    return DecisionExplanations(flight=flight, hotel=hotel_text,
                                attractions=attractions,
                                weather_and_location=weather_text,
                                budget=budget_text)


def render_readable(plan: TripPlan) -> str:
    """Human-readable plan in the style of the project brief."""
    req = plan.request
    lines = [
        f"{plan.trip_title} ({req.departure_date:%b %d} - "
        f"{req.return_date:%b %d, %Y})",
        f"{req.origin} -> {plan.destination.city} | {req.travelers} "
        f"traveller(s) | {req.nights} night(s)",
        "",
        "Flight Selected:",
    ]
    for label, flight in (("Outbound", plan.outbound_flight),
                          ("Return", plan.return_flight)):
        if flight:
            lines.append(
                f"- {label}: {flight.airline} {flight.flight_id} "
                f"(Rs {flight.price_per_person:,}/person) - departs "
                f"{flight.origin} at {flight.departure_time:%H:%M}")
        else:
            lines.append(f"- {label}: no direct flight in dataset")
    lines += ["", "Hotel Booked:"]
    if plan.hotel:
        lines.append(f"- {plan.hotel.name} (Rs {plan.hotel.price_per_night:,}"
                     f"/night, {plan.hotel.stars}-star)")
    else:
        lines.append("- No hotel available in dataset")
    lines += ["", "Weather:"]
    for day in plan.days:
        wx = day.weather
        if wx and wx.source != "unavailable":
            tag = "" if wx.source == "forecast" else " [last year]"
            lines.append(f"- Day {day.day}: {wx.condition} "
                         f"({wx.temp_max_c:.0f}°C){tag}")
        else:
            lines.append(f"- Day {day.day}: unavailable")
    lines += ["", "Itinerary:"]
    for day in plan.days:
        stops = [a.title for a in day.morning + day.afternoon + day.evening]
        lines.append(f"Day {day.day} ({day.date:%a %d %b}): " + ", ".join(stops))
    lines += ["", "Estimated Total Budget:"]
    for line in plan.budget.lines:
        tag = "" if line.basis == "dataset" else " (est.)"
        lines.append(f"- {line.category}{tag}: Rs {line.amount:,}")
    lines += ["-" * 37, f"Total Cost: Rs {plan.budget.grand_total:,}"]
    return "\n".join(lines)
