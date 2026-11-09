"""REST + Server-Sent-Events API."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.agents.llm_factory import LLMNotConfiguredError, llm_status
from app.agents.query_parser import parse_trip_query
from app.agents.travel_agent import run_planning
from app.models.schemas import (
    AccommodationType, FlightPreference, Interest, ParsedTripQuery,
    QueryParseRequest, TripPlan, TripRequest,
)
from app.services.data_repository import get_repository
from app.services.destination_service import get_destination_profile
from app.tools.flight_search import search_flights
from app.tools.hotel_search import recommend_hotels
from app.tools.places_search import discover_places
from app.tools.weather_lookup import lookup_weather
from app.utils.http import ExternalAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    """Liveness probe plus configuration status (no secrets)."""
    repo = get_repository()
    return {"status": "ok", "llm": llm_status(), "datasets": {
        "flights": len(repo.flights), "hotels": len(repo.hotels),
        "places": len(repo.places)}}


@router.get("/meta")
def meta() -> dict:
    """Everything the planner form needs: cities, routes, enums."""
    repo = get_repository()
    return {
        "cities": repo.cities(),
        "routes": repo.routes(),
        "interests": [i.value for i in Interest],
        "accommodation_types": [a.value for a in AccommodationType],
        "flight_preferences": [f.value for f in FlightPreference],
        "amenities": sorted({a for lst in repo.hotels["amenities"] for a in lst}),
        "dataset": repo.summary(),
        "llm": llm_status(),
    }


@router.get("/destinations")
def destinations() -> list[dict]:
    """Destination cards: real dataset counts + Wikipedia imagery."""
    repo = get_repository()
    cards = []
    for city in repo.cities():
        hotels = repo.hotels[repo.hotels["city"] == city]
        places = repo.places[repo.places["city"] == city]
        inbound = repo.flights[repo.flights["to"] == city]
        profile = get_destination_profile(city)
        cards.append({
            "city": city,
            "description": profile.get("description"),
            "image_url": profile.get("image_url"),
            "image_credit": profile.get("image_credit"),
            "hotels": int(len(hotels)),
            "places": int(len(places)),
            "inbound_flights": int(len(inbound)),
            "min_hotel_price": int(hotels["price_per_night"].min())
            if not hotels.empty else None,
            "min_flight_price": int(inbound["price"].min())
            if not inbound.empty else None,
            "top_rating": float(places["rating"].max())
            if not places.empty else None,
        })
    return cards


@router.get("/flights")
def flights(origin: str, destination: str, travel_date: date | None = None,
            travelers: int = Query(1, ge=1, le=10),
            preference: FlightPreference = FlightPreference.BALANCED):
    """Direct access to the flight search tool."""
    return search_flights(origin, destination, travel_date, travelers,
                          preference, max_results=20)


@router.get("/hotels")
def hotels(city: str, nights: int = Query(3, ge=1, le=14),
           travelers: int = Query(1, ge=1, le=10),
           max_price_per_night: int | None = None,
           accommodation_type: AccommodationType = AccommodationType.ANY):
    """Direct access to the hotel recommendation tool."""
    return recommend_hotels(city, nights, travelers, max_price_per_night,
                            accommodation_type, max_results=20)


@router.get("/places")
def places(city: str, interests: list[Interest] = Query(default=[])):
    """Direct access to the places discovery tool."""
    return discover_places(city, interests, max_results=20)


@router.get("/weather")
def weather(city: str, start_date: date, end_date: date):
    """Direct access to the weather tool."""
    if (end_date - start_date).days > 15:
        raise HTTPException(400, "Range limited to 16 days.")
    try:
        return lookup_weather(city, start_date, end_date)
    except ExternalAPIError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/parse-query", response_model=ParsedTripQuery)
def parse_query(body: QueryParseRequest) -> ParsedTripQuery:
    """Turn a free-text request into form fields using the LLM."""
    try:
        return parse_trip_query(body.query)
    except LLMNotConfiguredError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        logger.exception("Query parsing failed")
        raise HTTPException(502, f"LLM error: {exc}") from exc


def _validate_trip(request: TripRequest) -> None:
    if request.departure_date < date.today():
        raise HTTPException(422, "Departure date cannot be in the past.")


@router.post("/plan", response_model=TripPlan)
def plan(request: TripRequest, rule_based: bool = False) -> TripPlan:
    """Plan a trip synchronously (returns the full plan)."""
    _validate_trip(request)
    return run_planning(request, force_rule_based=rule_based)


@router.post("/plan/stream")
async def plan_stream(request: TripRequest, rule_based: bool = False):
    """Plan a trip and stream real progress as Server-Sent Events."""
    _validate_trip(request)
    events: queue.Queue = queue.Queue()
    done = object()

    def worker() -> None:
        try:
            result = run_planning(request, emit=events.put,
                                  force_rule_based=rule_based)
            events.put({"type": "result",
                        "plan": json.loads(result.model_dump_json())})
        except Exception as exc:
            logger.exception("Planning failed")
            events.put({"type": "error", "message": str(exc)})
        finally:
            events.put(done)

    threading.Thread(target=worker, daemon=True).start()

    async def event_source():
        while True:
            try:
                item = events.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if item is done:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return StreamingResponse(
        event_source(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
