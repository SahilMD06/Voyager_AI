"""Deterministic, weather-aware itinerary scheduler.

Used by the rule-based planner, and by the plan assembler to fill any day the
LLM agent left out. It only schedules attractions that came from places.json;
free slots get clearly generic activities (meals, rest, transfers).
"""

from __future__ import annotations

from datetime import timedelta

from app.models.schemas import (
    ActivityDraft, DayDraft, FlightOption, HotelOption, PlaceOption,
    TripRequest, WeatherDay,
)

OUTDOOR = {"beach", "park", "lake", "fort", "monument"}
INDOOR = {"museum", "temple", "market"}

# Generic (non-attraction) fillers. They name no place, so nothing is invented.
AFTERNOON_FREE = [
    ("Rest & free time", "Unplanned hours to recharge or wander."),
    ("Long, unhurried lunch", "Try a regional thali or the local speciality."),
    ("Neighbourhood stroll", "Explore the streets around your hotel at your pace."),
]
AFTERNOON_FREE_POOL = [
    ("Relax at the hotel pool", "Beat the afternoon heat at the hotel."),
] + AFTERNOON_FREE[1:]
EVENING_FREE = [
    ("Dinner featuring local cuisine", "Explore restaurants near your hotel."),
    ("Evening at leisure", "Keep it light ahead of tomorrow's plans."),
    ("Street-food walk", "Sample local snacks; ask your hotel for a busy, "
                         "well-reviewed area."),
]


def is_wet(weather: WeatherDay | None) -> bool:
    """True when the day's weather suggests indoor plans."""
    if weather is None or weather.source == "unavailable":
        return False
    return (
        weather.icon in {"rain", "storm"}
        or (weather.precipitation_probability or 0) >= 50
        or (weather.precipitation_mm or 0) >= 5
    )


def _flight_text(flight: FlightOption | None, leg: str, origin: str,
                 destination: str) -> ActivityDraft:
    if flight is None:
        return ActivityDraft(
            title=f"{leg}: {origin} to {destination}",
            description="No direct flight for this route exists in the "
                        "dataset - arrange alternate transport.",
        )
    return ActivityDraft(
        title=f"{leg} flight {flight.airline} {flight.flight_id}",
        description=(
            f"{flight.origin} {flight.departure_time:%H:%M} -> "
            f"{flight.destination} {flight.arrival_time:%H:%M} "
            f"({flight.duration_minutes // 60}h {flight.duration_minutes % 60:02d}m)."
        ),
    )


def _place_activity(place: PlaceOption, wet: bool) -> ActivityDraft:
    text = f"Rated {place.rating}/5 {place.category}."
    if place.matched_interests:
        text += f" Matches your interest in {', '.join(place.matched_interests)}."
    if wet and place.category in INDOOR:
        text += " Indoor pick for a wet day."
    return ActivityDraft(place_id=place.place_id, title=f"Visit {place.name}",
                         description=text)


def schedule_days(
    request: TripRequest,
    places: list[PlaceOption],
    weather: dict,
    outbound: FlightOption | None,
    inbound: FlightOption | None,
    hotel: HotelOption | None,
) -> list[DayDraft]:
    """Build a full list of DayDrafts for the trip."""
    n_days = request.days
    dates = [request.departure_date + timedelta(days=i) for i in range(n_days)]
    capacity = {1: 1, n_days: 1}
    for day in range(2, n_days):
        capacity[day] = 2
    wet_days = {i + 1 for i, d in enumerate(dates) if is_wet(weather.get(d))}
    assigned: dict[int, list[PlaceOption]] = {d: [] for d in range(1, n_days + 1)}

    for place in sorted(places, key=lambda p: p.score, reverse=True):
        open_days = [d for d in assigned if len(assigned[d]) < capacity[d]]
        if not open_days:
            break
        outdoor = place.category in OUTDOOR
        preferred = [d for d in open_days if (d in wet_days) != outdoor]
        candidates = preferred or open_days
        # Spread attractions: most remaining capacity first, then earliest.
        candidates.sort(key=lambda d: (-(capacity[d] - len(assigned[d])), d))
        assigned[candidates[0]].append(place)

    hotel_name = hotel.name if hotel else "your hotel"
    has_pool = bool(hotel and "pool" in hotel.amenities)
    drafts: list[DayDraft] = []
    for day in range(1, n_days + 1):
        date_ = dates[day - 1]
        wx = weather.get(date_)
        wet = day in wet_days
        morning: list[ActivityDraft] = []
        afternoon: list[ActivityDraft] = []
        evening: list[ActivityDraft] = []
        day_places = assigned[day]

        for place in day_places:
            act = _place_activity(place, wet)
            if place.category == "market":
                evening.append(act)
            elif day == 1:
                afternoon.append(act)
            elif day == n_days:
                morning.append(act)
            elif place.category in {"fort", "monument"} and not morning:
                morning.append(act)
            elif not morning:
                morning.append(act)
            else:
                afternoon.append(act)

        if day == 1:
            morning.insert(0, _flight_text(outbound, "Outbound",
                                           request.origin, request.destination))
            afternoon.insert(0, ActivityDraft(
                title=f"Check in at {hotel_name}",
                description="Drop your bags and freshen up."))
        if day == n_days:
            afternoon.append(ActivityDraft(
                title=f"Check out of {hotel_name}",
                description="Settle the bill and head to the airport."))
            afternoon.append(_flight_text(inbound, "Return",
                                          request.destination, request.origin))
        if not morning:
            morning.append(ActivityDraft(
                title="Leisurely breakfast & neighbourhood walk",
                description="Unscheduled time - no further attractions for "
                            "this city in the dataset."))
        if not afternoon:
            options = AFTERNOON_FREE_POOL if has_pool else AFTERNOON_FREE
            title, text = options[day % len(options)]
            afternoon.append(ActivityDraft(title=title, description=text))
        if not evening and day != n_days:
            title, text = EVENING_FREE[day % len(EVENING_FREE)]
            evening.append(ActivityDraft(title=title, description=text))

        theme = (
            "Arrival & first impressions" if day == 1
            else "Wrap-up & departure" if day == n_days
            else " & ".join(sorted({p.category.title() for p in day_places}))
            or "Leisure day"
        )
        consideration = _weather_note(wx, wet, day_places)
        drafts.append(DayDraft(
            day=day, theme=theme, morning=morning, afternoon=afternoon,
            evening=evening, weather_consideration=consideration,
            tips=weather_tips(wx),
        ))
    return drafts


def _weather_note(wx: WeatherDay | None, wet: bool,
                  day_places: list[PlaceOption]) -> str:
    if wx is None or wx.source == "unavailable":
        return "Weather data unavailable for this date; plan kept flexible."
    label = "Forecast" if wx.source == "forecast" else "Typical (last year)"
    base = f"{label}: {wx.condition}, {wx.temp_min_c}-{wx.temp_max_c} C."
    if wet:
        indoor = [p.name for p in day_places if p.category in INDOOR]
        return base + (" Wet day - indoor attractions prioritised"
                       + (f" ({', '.join(indoor)})." if indoor else "."))
    outdoor = [p.name for p in day_places if p.category in OUTDOOR]
    if outdoor:
        return base + f" Dry conditions suit outdoor visits ({', '.join(outdoor)})."
    return base


def weather_tips(wx: WeatherDay | None) -> list[str]:
    """Practical tips derived from the day's weather."""
    if wx is None or wx.source == "unavailable":
        return ["Check the latest forecast the day before."]
    tips = []
    if (wx.temp_max_c or 0) >= 33:
        tips.append("Hot afternoon expected - carry water and sunscreen.")
    if is_wet(wx):
        tips.append("Carry an umbrella or rain jacket.")
    if (wx.temp_min_c or 99) <= 15:
        tips.append("Cool evening - pack a light jacket.")
    if wx.source == "historical":
        tips.append("Weather shown is last year's record for this date.")
    return tips or ["Comfortable weather - great for sightseeing."]
