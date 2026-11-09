"""Unit tests for dataset loading and the five tools."""

from __future__ import annotations

from datetime import date

from app.models.schemas import (
    AccommodationType, FlightPreference, Interest,
)
from app.services.data_repository import get_repository, normalise_city
from app.tools.budget_estimator import estimate_budget
from app.tools.flight_search import search_flights
from app.tools.hotel_search import recommend_hotels
from app.tools.places_search import discover_places
from app.tools.weather_lookup import lookup_weather


def test_datasets_load():
    repo = get_repository()
    assert len(repo.flights) == 30
    assert len(repo.hotels) == 40
    assert len(repo.places) == 40
    assert (repo.flights["duration_minutes"] > 0).all()
    assert "Goa" in repo.cities()


def test_city_aliases():
    assert normalise_city("bengaluru") == "Bangalore"
    assert normalise_city("  goa ") == "Goa"
    assert normalise_city("Bombay") == "Mumbai"


def test_flight_search_cheapest_and_fastest():
    result = search_flights("Bangalore", "Goa", date(2026, 12, 1), 2,
                            FlightPreference.CHEAPEST)
    assert result.options, "Bangalore->Goa exists in the dataset"
    prices = [o.price_per_person for o in result.options]
    assert result.options[0].flight_id == result.cheapest_id
    assert min(prices) == result.options[0].price_per_person
    assert all(o.total_price == o.price_per_person * 2 for o in result.options)

    fastest = search_flights("Bangalore", "Goa",
                             preference=FlightPreference.FASTEST)
    assert fastest.options[0].flight_id == fastest.fastest_id


def test_flight_search_no_route_is_honest():
    result = search_flights("Delhi", "Goa")
    assert result.options == []
    assert "No direct flight" in result.note
    assert "Bangalore" in result.alternatives["direct_into_Goa"]


def test_hotel_ranking_respects_preferences():
    result = recommend_hotels("Goa", nights=3, travelers=3,
                              max_price_per_night=4000,
                              accommodation_type=AccommodationType.RESORT,
                              preferred_amenities=["pool"])
    assert result.options[0].tier == "resort"
    assert result.options[0].within_budget
    assert result.options[0].rooms_needed == 2
    top = result.options[0]
    assert top.total_stay_cost == top.price_per_night * 2 * 3
    # Over-budget hotels are ranked below in-budget ones.
    flags = [o.within_budget for o in result.options]
    assert flags == sorted(flags, reverse=True)


def test_hotel_unknown_city():
    result = recommend_hotels("Atlantis", nights=2)
    assert result.options == [] and "no hotels" in result.note


def test_places_interest_matching():
    result = discover_places("Goa", [Interest.HISTORICAL])
    assert result.options
    assert result.options[0].matched_interests == ["historical"]
    ids = [p.place_id for p in result.options]
    assert len(ids) == len(set(ids))


def test_budget_uses_dataset_prices_and_no_double_count():
    repo = get_repository()
    flight = repo.flights.iloc[0]
    hotel = repo.hotels.iloc[0]
    place_ids = list(repo.places["place_id"][:2])
    budget = estimate_budget(
        travelers=3, nights=2, outbound_flight_id=flight["flight_id"],
        hotel_id=hotel["hotel_id"], place_ids=place_ids + place_ids,
        accommodation_type="mid-range", user_budget=10_000)
    lines = {line.category: line for line in budget.lines}
    assert lines["Flights"].amount == int(flight["price"]) * 3
    assert lines["Flights"].basis == "dataset"
    assert lines["Accommodation"].amount == int(hotel["price_per_night"]) * 2 * 2
    assert lines["Food"].basis == "estimate"
    assert "2 attraction(s)" in lines["Activities"].detail  # deduplicated
    assert budget.grand_total == sum(l.amount for l in budget.lines)
    assert budget.dataset_total + budget.estimated_total == budget.grand_total
    assert budget.within_budget is (budget.grand_total <= 10_000)


def test_budget_ignores_unknown_ids():
    budget = estimate_budget(travelers=1, nights=2,
                             outbound_flight_id="FAKE123", hotel_id="NOPE")
    assert all(l.category not in {"Flights", "Accommodation"}
               for l in budget.lines)
    assert "not found" in budget.note


def test_weather_tool_stubbed(trip_dates):
    start, end = trip_dates
    result = lookup_weather("Goa", start, end)
    assert len(result.days) == (end - start).days + 1
