"""Pydantic models shared by tools, the agent and the API."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MIN_TRIP_DAYS = 3
MAX_TRIP_DAYS = 7


class FlightPreference(str, Enum):
    """How the user wants flights ranked."""

    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    BALANCED = "balanced"


class AccommodationType(str, Enum):
    """Accommodation tiers derived from the hotel star rating / name."""

    ANY = "any"
    BUDGET = "budget"
    MID_RANGE = "mid-range"
    LUXURY = "luxury"
    RESORT = "resort"


class Interest(str, Enum):
    """Traveller interests mapped onto place categories."""

    ADVENTURE = "adventure"
    BEACHES = "beaches"
    HISTORICAL = "historical"
    NATURE = "nature"
    FOOD = "food"
    SHOPPING = "shopping"
    CULTURE = "culture"
    SPIRITUAL = "spiritual"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class TripRequest(BaseModel):
    """Validated trip request coming from the UI or API."""

    origin: str = Field(..., min_length=2, max_length=60)
    destination: str = Field(..., min_length=2, max_length=60)
    departure_date: date
    return_date: date
    travelers: int = Field(1, ge=1, le=10)
    budget: int = Field(..., ge=1000, le=5_000_000, description="Total INR")
    accommodation_type: AccommodationType = AccommodationType.ANY
    interests: list[Interest] = Field(default_factory=list)
    flight_preference: FlightPreference = FlightPreference.BALANCED
    preferred_amenities: list[str] = Field(default_factory=list)
    notes: str | None = Field(None, max_length=600)

    @field_validator("origin", "destination")
    @classmethod
    def _strip_city(cls, value: str) -> str:
        return value.strip().title()

    @model_validator(mode="after")
    def _check_dates(self) -> "TripRequest":
        if self.origin.lower() == self.destination.lower():
            raise ValueError("Origin and destination must be different.")
        if self.return_date <= self.departure_date:
            raise ValueError("Return date must be after departure date.")
        days = (self.return_date - self.departure_date).days + 1
        if not MIN_TRIP_DAYS <= days <= MAX_TRIP_DAYS:
            raise ValueError(
                f"Trip length must be {MIN_TRIP_DAYS}-{MAX_TRIP_DAYS} days "
                f"(got {days})."
            )
        return self

    @property
    def nights(self) -> int:
        """Number of hotel nights."""
        return (self.return_date - self.departure_date).days

    @property
    def days(self) -> int:
        """Number of itinerary days (inclusive)."""
        return self.nights + 1


class QueryParseRequest(BaseModel):
    """Free-text request to be parsed into a TripRequest by the LLM."""

    query: str = Field(..., min_length=5, max_length=1000)


class ParsedTripQuery(BaseModel):
    """LLM extraction of a natural-language trip query."""

    origin: str | None = Field(None, description="Departure city")
    destination: str | None = Field(None, description="Destination city")
    departure_date: date | None = Field(None, description="ISO date")
    return_date: date | None = Field(None, description="ISO date")
    travelers: int | None = None
    budget: int | None = Field(None, description="Total budget in INR")
    accommodation_type: AccommodationType | None = None
    interests: list[Interest] = Field(default_factory=list)
    flight_preference: FlightPreference | None = None
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Required fields the user did not provide",
    )
    clarifying_question: str | None = Field(
        None, description="One short question asking for missing details"
    )


# ---------------------------------------------------------------------------
# Tool results
# ---------------------------------------------------------------------------


class FlightOption(BaseModel):
    """A flight record from flights.json enriched with derived metrics."""

    flight_id: str
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    price_per_person: int
    total_price: int
    date_match: Literal["exact", "same_month", "none"]
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0
    reason: str = ""


class FlightSearchResult(BaseModel):
    """Output of the flight search tool."""

    origin: str
    destination: str
    travel_date: date | None
    preference: FlightPreference
    travelers: int
    options: list[FlightOption]
    cheapest_id: str | None = None
    fastest_id: str | None = None
    recommended_id: str | None = None
    note: str = ""
    alternatives: dict[str, list[str]] = Field(default_factory=dict)


class HotelOption(BaseModel):
    """A hotel record from hotels.json enriched with ranking data."""

    hotel_id: str
    name: str
    city: str
    stars: int
    price_per_night: int
    amenities: list[str]
    tier: str
    rooms_needed: int
    total_stay_cost: int
    within_budget: bool
    score: float = 0.0
    reason: str = ""


class HotelSearchResult(BaseModel):
    """Output of the hotel recommendation tool."""

    city: str
    nights: int
    travelers: int
    options: list[HotelOption]
    recommended_id: str | None = None
    note: str = ""


class PlaceOption(BaseModel):
    """An attraction from places.json."""

    place_id: str
    name: str
    city: str
    category: str
    rating: float
    matched_interests: list[str] = Field(default_factory=list)
    estimated_entry_cost: int = 0
    score: float = 0.0
    reason: str = ""


class PlacesSearchResult(BaseModel):
    """Output of the places discovery tool."""

    city: str
    interests: list[str]
    options: list[PlaceOption]
    note: str = ""


class WeatherDay(BaseModel):
    """Weather for a single trip day."""

    date: date
    condition: str
    icon: str
    weather_code: int | None
    temp_max_c: float | None
    temp_min_c: float | None
    precipitation_probability: int | None = None
    precipitation_mm: float | None = None
    source: Literal["forecast", "historical", "unavailable"]
    source_note: str = ""


class WeatherResult(BaseModel):
    """Output of the weather lookup tool."""

    city: str
    resolved_location: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    days: list[WeatherDay]
    note: str = ""


class BudgetLine(BaseModel):
    """A single budget category."""

    category: str
    amount: int
    basis: Literal["dataset", "estimate"]
    detail: str


class BudgetBreakdown(BaseModel):
    """Output of the budget estimation tool (group totals, INR)."""

    currency: str = "INR"
    travelers: int
    nights: int
    lines: list[BudgetLine]
    dataset_total: int
    estimated_total: int
    grand_total: int
    per_person: int
    user_budget: int | None = None
    remaining: int | None = None
    within_budget: bool | None = None
    note: str = "All amounts are group totals."


# ---------------------------------------------------------------------------
# Agent structured output (what the LLM must produce)
# ---------------------------------------------------------------------------


class ActivityDraft(BaseModel):
    """One activity slot in the agent's itinerary draft."""

    place_id: str | None = Field(
        None,
        description="place_id from search_places results, or null for a "
        "non-attraction activity (check-in, meal, transfer, leisure)",
    )
    title: str = Field(..., description="Short activity title")
    description: str = Field(..., description="One or two sentences")

    @field_validator("place_id", mode="before")
    @classmethod
    def _blank_place_id(cls, value):
        """LLMs sometimes write the string "null"/"none" for no place."""
        if value is None:
            return None
        text = str(value).strip()
        return None if text.lower() in {"", "null", "none", "n/a"} else text


class DayDraft(BaseModel):
    """One day in the agent's itinerary draft."""

    day: int = Field(..., ge=1, le=MAX_TRIP_DAYS)
    theme: str = Field(..., description="Short theme for the day")
    morning: list[ActivityDraft] = Field(default_factory=list)
    afternoon: list[ActivityDraft] = Field(default_factory=list)
    evening: list[ActivityDraft] = Field(default_factory=list)
    weather_consideration: str = Field(
        "", description="How the day's weather shaped the plan"
    )
    tips: list[str] = Field(default_factory=list)


class DecisionExplanations(BaseModel):
    """Why the agent picked what it picked."""

    flight: str
    hotel: str
    attractions: str
    weather_and_location: str
    budget: str


class AgentPlanDraft(BaseModel):
    """Final structured response produced by the LangChain agent."""

    trip_title: str = Field(..., description="e.g. '4-Day Beach Escape to Goa'")
    summary: str = Field(..., description="2-3 sentence trip summary")
    outbound_flight_id: str | None = Field(
        None, description="flight_id chosen for the outbound leg, or null"
    )
    return_flight_id: str | None = Field(
        None, description="flight_id chosen for the return leg, or null"
    )
    hotel_id: str | None = Field(None, description="hotel_id chosen, or null")
    days: list[DayDraft]
    explanations: DecisionExplanations
    general_tips: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=list,
        description="Data gaps or trade-offs the traveller should know",
    )


# ---------------------------------------------------------------------------
# Final plan (validated, returned to the UI)
# ---------------------------------------------------------------------------


class Activity(BaseModel):
    """Validated activity."""

    title: str
    description: str
    place: PlaceOption | None = None
    from_dataset: bool = False


class DayPlan(BaseModel):
    """Validated day of the itinerary."""

    day: int
    date: date
    theme: str
    weather: WeatherDay | None
    morning: list[Activity]
    afternoon: list[Activity]
    evening: list[Activity]
    estimated_cost: int
    cost_note: str
    weather_consideration: str = ""
    tips: list[str] = Field(default_factory=list)


class AgentStep(BaseModel):
    """One step in the agent's execution trace."""

    index: int
    kind: Literal["tool_call", "reasoning", "validation", "info"]
    tool: str | None = None
    arguments: dict | None = None
    summary: str
    duration_ms: int | None = None


class DestinationInfo(BaseModel):
    """Geographic info about the destination."""

    city: str
    resolved_location: str | None
    latitude: float | None
    longitude: float | None
    image_url: str | None = None
    image_credit: str | None = None


class TripPlan(BaseModel):
    """Complete plan returned to the client."""

    plan_id: str
    generated_at: datetime
    mode: Literal["agent", "rule_based"]
    model: str | None
    request: TripRequest
    trip_title: str
    summary: str
    destination: DestinationInfo
    outbound_flight: FlightOption | None
    return_flight: FlightOption | None
    flight_options_outbound: list[FlightOption]
    flight_options_return: list[FlightOption]
    hotel: HotelOption | None
    hotel_options: list[HotelOption]
    places: list[PlaceOption]
    weather: WeatherResult | None
    days: list[DayPlan]
    budget: BudgetBreakdown
    explanations: DecisionExplanations
    general_tips: list[str]
    warnings: list[str]
    agent_trace: list[AgentStep]
    readable_summary: str
