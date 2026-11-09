"""API endpoint tests (FastAPI TestClient) and live integration checks."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(start, **overrides):
    data = {"origin": "Bangalore", "destination": "Goa",
            "departure_date": start.isoformat(),
            "return_date": (start + timedelta(days=3)).isoformat(),
            "travelers": 2, "budget": 50000, "interests": ["beaches"],
            "accommodation_type": "any", "flight_preference": "balanced"}
    data.update(overrides)
    return data


def test_health_and_meta():
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert "Goa" in meta["cities"]
    assert "Goa" in meta["routes"]["Bangalore"]


def test_tool_endpoints():
    flights = client.get("/api/flights", params={
        "origin": "Bangalore", "destination": "Goa"}).json()
    assert flights["options"]
    hotels = client.get("/api/hotels", params={"city": "Goa"}).json()
    assert hotels["options"]
    places = client.get("/api/places", params={"city": "Goa"}).json()
    assert places["options"]


def test_validation_errors(trip_dates):
    start, _ = trip_dates
    bad = payload(start, return_date=start.isoformat())
    response = client.post("/api/plan", json=bad)
    assert response.status_code == 422
    past = payload(date.today() - timedelta(days=10))
    assert client.post("/api/plan", json=past).status_code == 422


def test_plan_stream_rule_based(trip_dates):
    start, _ = trip_dates
    with client.stream("POST", "/api/plan/stream?rule_based=true",
                       json=payload(start)) as response:
        assert response.status_code == 200
        events = [json.loads(line[6:]) for line in response.iter_lines()
                  if line.startswith("data: ")]
    kinds = [e["type"] for e in events]
    assert kinds[0] == "stage" and kinds[-1] == "result"
    stages = {e.get("stage") for e in events if e["type"] == "tool_end"}
    assert {"flights", "hotels", "places", "weather"} <= stages
    plan = events[-1]["plan"]
    assert len(plan["days"]) == 4 and plan["budget"]["grand_total"] > 0


@pytest.mark.live
def test_live_open_meteo_forecast():
    from app.services.weather_service import get_trip_weather
    start = date.today() + timedelta(days=2)
    result = get_trip_weather("Goa", start, start + timedelta(days=2))
    assert result.latitude and 14 < result.latitude < 16.5
    assert all(d.source == "forecast" for d in result.days)
    assert all(d.temp_max_c is not None for d in result.days)
