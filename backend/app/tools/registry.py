"""LangChain tool definitions bound to a per-request ``ToolLedger``.

Each request gets fresh tool instances. Every call is recorded in the ledger
(arguments, result, timing) so that:

* the API can stream real progress events to the UI, and
* the plan assembler can validate the agent's final answer against the data
  the tools actually returned.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.models.schemas import (
    AccommodationType, BudgetBreakdown, FlightPreference, FlightSearchResult,
    HotelSearchResult, Interest, PlacesSearchResult, WeatherResult,
)
from app.tools.budget_estimator import estimate_budget
from app.tools.flight_search import search_flights
from app.tools.hotel_search import recommend_hotels
from app.tools.places_search import discover_places
from app.tools.weather_lookup import lookup_weather

logger = logging.getLogger(__name__)

# Tool name -> UI planning stage
TOOL_STAGES = {
    "search_flights": "flights",
    "recommend_hotels": "hotels",
    "discover_places": "places",
    "get_weather": "weather",
    "estimate_budget": "budget",
}


@dataclass
class ToolCallRecord:
    """A single tool invocation."""

    tool: str
    arguments: dict
    result: Any
    summary: str
    duration_ms: int
    error: str | None = None


@dataclass
class ToolLedger:
    """Collects tool results for one planning run."""

    emit: Callable[[dict], None] = lambda event: None
    calls: list[ToolCallRecord] = field(default_factory=list)
    flight_searches: list[FlightSearchResult] = field(default_factory=list)
    hotel_searches: list[HotelSearchResult] = field(default_factory=list)
    place_searches: list[PlacesSearchResult] = field(default_factory=list)
    weather: list[WeatherResult] = field(default_factory=list)
    budgets: list[BudgetBreakdown] = field(default_factory=list)

    def run(self, tool: str, arguments: dict, fn: Callable[[], BaseModel],
            summarise: Callable[[Any], str]) -> str:
        """Execute ``fn`` with progress events and record the outcome."""
        stage = TOOL_STAGES.get(tool)
        self.emit({"type": "tool_start", "tool": tool, "stage": stage,
                   "arguments": arguments})
        started = time.perf_counter()
        try:
            result = fn()
            summary = summarise(result)
            error = None
        except Exception as exc:  # report the failure to the agent honestly
            logger.exception("Tool %s failed", tool)
            result, summary, error = None, f"Tool error: {exc}", str(exc)
        elapsed = int((time.perf_counter() - started) * 1000)
        self.calls.append(ToolCallRecord(tool, arguments, result, summary,
                                         elapsed, error))
        self._store(result)
        self.emit({"type": "tool_end", "tool": tool, "stage": stage,
                   "summary": summary, "duration_ms": elapsed,
                   "ok": error is None})
        if result is None:
            return json.dumps({"error": summary})
        return result.model_dump_json(exclude_none=True)

    def _store(self, result: Any) -> None:
        if isinstance(result, FlightSearchResult):
            self.flight_searches.append(result)
        elif isinstance(result, HotelSearchResult):
            self.hotel_searches.append(result)
        elif isinstance(result, PlacesSearchResult):
            self.place_searches.append(result)
        elif isinstance(result, WeatherResult):
            self.weather.append(result)
        elif isinstance(result, BudgetBreakdown):
            self.budgets.append(result)

    def tools_used(self) -> set[str]:
        """Names of tools invoked at least once."""
        return {c.tool for c in self.calls}


# --------------------------------------------------------------------------
# Argument schemas (these become the JSON schema the LLM sees)
# --------------------------------------------------------------------------


class FlightArgs(BaseModel):
    origin: str = Field(..., description="Departure city, e.g. 'Bangalore'")
    destination: str = Field(..., description="Arrival city, e.g. 'Goa'")
    travel_date: date | None = Field(None, description="Desired date YYYY-MM-DD")
    travelers: int = Field(1, ge=1, le=10)
    preference: FlightPreference = Field(
        FlightPreference.BALANCED, description="cheapest | fastest | balanced")


class HotelArgs(BaseModel):
    city: str
    nights: int = Field(..., ge=1, le=14)
    travelers: int = Field(1, ge=1, le=10)
    max_price_per_night: int | None = Field(
        None, description="Soft cap per room per night in INR")
    accommodation_type: AccommodationType = AccommodationType.ANY
    preferred_amenities: list[str] = Field(
        default_factory=list, description="e.g. ['pool', 'wifi']")


class PlacesArgs(BaseModel):
    city: str
    interests: list[Interest] = Field(default_factory=list)
    min_rating: float = Field(0.0, ge=0, le=5)


class WeatherArgs(BaseModel):
    city: str
    start_date: date
    end_date: date


class BudgetArgs(BaseModel):
    travelers: int = Field(..., ge=1, le=10)
    nights: int = Field(..., ge=1, le=14)
    outbound_flight_id: str | None = None
    return_flight_id: str | None = None
    hotel_id: str | None = None
    place_ids: list[str] = Field(default_factory=list)
    accommodation_type: AccommodationType = AccommodationType.ANY
    user_budget: int | None = Field(None, description="Total budget INR")


def build_tools(ledger: ToolLedger) -> list[StructuredTool]:
    """Create the five LangChain tools bound to ``ledger``."""

    def _flights(**kw) -> str:
        args = FlightArgs(**kw)
        return ledger.run(
            "search_flights", args.model_dump(mode="json"),
            lambda: search_flights(args.origin, args.destination,
                                   args.travel_date, args.travelers,
                                   args.preference),
            lambda r: (f"{len(r.options)} direct flight(s) "
                       f"{r.origin} -> {r.destination}"
                       + (f"; recommended {r.recommended_id}"
                          if r.recommended_id else "; none in dataset")),
        )

    def _hotels(**kw) -> str:
        args = HotelArgs(**kw)
        return ledger.run(
            "recommend_hotels", args.model_dump(mode="json"),
            lambda: recommend_hotels(args.city, args.nights, args.travelers,
                                     args.max_price_per_night,
                                     args.accommodation_type,
                                     args.preferred_amenities),
            lambda r: (f"{len(r.options)} hotel(s) ranked in {r.city}"
                       + (f"; top pick {r.options[0].name}"
                          if r.options else "")),
        )

    def _places(**kw) -> str:
        args = PlacesArgs(**kw)
        return ledger.run(
            "discover_places", args.model_dump(mode="json"),
            lambda: discover_places(args.city, args.interests, args.min_rating),
            lambda r: f"{len(r.options)} attraction(s) found in {r.city}",
        )

    def _weather(**kw) -> str:
        args = WeatherArgs(**kw)
        return ledger.run(
            "get_weather", args.model_dump(mode="json"),
            lambda: lookup_weather(args.city, args.start_date, args.end_date),
            lambda r: (f"{sum(d.source == 'forecast' for d in r.days)} "
                       f"forecast day(s), "
                       f"{sum(d.source == 'historical' for d in r.days)} "
                       f"historical day(s) for {r.resolved_location or r.city}"),
        )

    def _budget(**kw) -> str:
        args = BudgetArgs(**kw)
        return ledger.run(
            "estimate_budget", args.model_dump(mode="json"),
            lambda: estimate_budget(args.travelers, args.nights,
                                    args.outbound_flight_id,
                                    args.return_flight_id, args.hotel_id,
                                    args.place_ids, args.accommodation_type,
                                    args.user_budget),
            lambda r: (f"Total Rs {r.grand_total:,} "
                       + ("(within budget)" if r.within_budget
                          else "(over budget)" if r.within_budget is False
                          else "")),
        )

    return [
        StructuredTool.from_function(
            func=_flights, name="search_flights", args_schema=FlightArgs,
            description=(
                "Search flights.json for DIRECT flights between two cities. "
                "Returns options with flight_id, airline, times, duration, "
                "per-person and group price, plus cheapest/fastest/recommended "
                "ids. Call once for the outbound leg and once for the return "
                "leg (swap origin/destination). An empty list means no flight "
                "exists in the dataset - never invent one."),
        ),
        StructuredTool.from_function(
            func=_hotels, name="recommend_hotels", args_schema=HotelArgs,
            description=(
                "Rank hotels from hotels.json in a city by star rating, value, "
                "amenities and accommodation-type fit. Returns hotel_id, "
                "stars, price_per_night, amenities, total stay cost and "
                "whether each is within the nightly cap."),
        ),
        StructuredTool.from_function(
            func=_places, name="discover_places", args_schema=PlacesArgs,
            description=(
                "Find attractions from places.json in a city ranked by rating "
                "and match to traveller interests. Returns place_id, name, "
                "category, rating and an entry-cost estimate. Use only these "
                "place_ids in the itinerary."),
        ),
        StructuredTool.from_function(
            func=_weather, name="get_weather", args_schema=WeatherArgs,
            description=(
                "Get daily weather for a city between two dates from the "
                "Open-Meteo API: condition, max/min temperature, precipitation. "
                "Each day has source = forecast | historical | unavailable. "
                "Historical means last year's recorded weather on that date."),
        ),
        StructuredTool.from_function(
            func=_budget, name="estimate_budget", args_schema=BudgetArgs,
            description=(
                "Compute the group trip cost from selected flight_ids, hotel_id "
                "and place_ids. Looks up real dataset prices by id and adds "
                "labelled estimates for food, local transport and activities. "
                "Returns grand_total and whether it fits user_budget."),
        ),
    ]
