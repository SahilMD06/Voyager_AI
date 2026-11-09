"""Agent loop, validation layer and fallback planner tests."""

from __future__ import annotations

from datetime import timedelta

import pytest
from langchain_core.messages import AIMessage

from app.agents import travel_agent
from app.config import get_settings
from app.models.schemas import TripRequest
from tests.fakes import ScriptedToolModel, call


@pytest.fixture
def fake_key(monkeypatch):
    """Pretend a key is configured; the model itself is replaced by a fake."""
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "google_api_key", "test-key")
    return settings


def make_request(start, days=4, **overrides) -> TripRequest:
    data = dict(origin="Bangalore", destination="Goa", departure_date=start,
                return_date=start + timedelta(days=days - 1), travelers=2,
                budget=60000, interests=["historical", "shopping"],
                accommodation_type="any", flight_preference="cheapest")
    data.update(overrides)
    return TripRequest(**data)


def scripted_draft(start, bad_place=True) -> dict:
    activity = {"place_id": "PLC0012", "title": "Visit Famous Park",
                "description": "Top-rated museum."}
    days = [
        {"day": 1, "theme": "Arrival", "morning": [], "afternoon": [activity],
         "evening": [], "weather_consideration": "", "tips": []},
        {"day": 2, "theme": "Forts", "morning": [
            {"place_id": "PLC0014", "title": "Beautiful Park",
             "description": "Fort"}],
         "afternoon": [
             {"place_id": "PLC9999" if bad_place else None,
              "title": "Invented Waterfall", "description": "x"},
             {"place_id": "PLC0012", "title": "Duplicate", "description": "x"}],
         "evening": [], "weather_consideration": "", "tips": []},
    ]  # days 3-4 intentionally missing
    return {
        "trip_title": "Goa Heritage Escape", "summary": "Test summary.",
        "outbound_flight_id": "FL0021", "return_flight_id": "FL_FAKE",
        "hotel_id": "HOT0014", "days": days,
        "explanations": {"flight": "f", "hotel": "h", "attractions": "a",
                         "weather_and_location": "w", "budget": "b"},
        "general_tips": ["tip"], "warnings": [],
    }


def test_agent_runs_tools_and_output_is_validated(monkeypatch, trip_dates,
                                                  fake_key):
    start, _ = trip_dates
    request = make_request(start)
    end = request.return_date.isoformat()
    script = [
        AIMessage(content="I'll gather flights, hotels, places and weather.",
                  tool_calls=[
                      call("search_flights", {"origin": "Bangalore",
                                              "destination": "Goa",
                                              "travelers": 2,
                                              "preference": "cheapest"}, "c1"),
                      call("search_flights", {"origin": "Goa",
                                              "destination": "Bangalore",
                                              "travelers": 2}, "c2"),
                      call("recommend_hotels", {"city": "Goa", "nights": 3,
                                                "travelers": 2}, "c3"),
                      call("discover_places", {"city": "Goa", "interests":
                                               ["historical"]}, "c4"),
                      call("get_weather", {"city": "Goa",
                                           "start_date": start.isoformat(),
                                           "end_date": end}, "c5"),
                  ]),
        AIMessage(content="", tool_calls=[call("estimate_budget", {
            "travelers": 2, "nights": 3, "outbound_flight_id": "FL0021",
            "hotel_id": "HOT0014", "user_budget": 60000}, "c6")]),
        AIMessage(content="", tool_calls=[call(
            "AgentPlanDraft", scripted_draft(start), "c7")]),
    ]
    fake = ScriptedToolModel(script=script)
    monkeypatch.setattr(travel_agent, "create_chat_model",
                        lambda **kw: fake)

    events = []
    plan = travel_agent.run_planning(request, emit=events.append)

    assert plan.mode == "agent"
    assert plan.trip_title == "Goa Heritage Escape"
    tools_called = [e["tool"] for e in events if e["type"] == "tool_start"]
    # The agent issued parallel calls, so order may vary.
    assert sorted(tools_called[:5]) == sorted([
        "search_flights", "search_flights", "recommend_hotels",
        "discover_places", "get_weather"])
    assert "estimate_budget" in tools_called
    # Each parallel flight call keeps its own result in the trace.
    flight_steps = [st.summary for st in plan.agent_trace
                    if st.kind == "tool_call" and st.tool == "search_flights"]
    assert any("Bangalore -> Goa" in x for x in flight_steps)
    assert any("Goa -> Bangalore" in x for x in flight_steps)
    # Valid agent choices are kept; invalid ones replaced from tool results.
    assert plan.outbound_flight.flight_id == "FL0021"
    assert plan.return_flight.flight_id != "FL_FAKE"
    assert plan.hotel.hotel_id == "HOT0014"
    # Hallucinated / duplicate places removed; missing days filled.
    assert len(plan.days) == 4
    ids = [a.place.place_id for d in plan.days
           for a in d.morning + d.afternoon + d.evening if a.place]
    assert "PLC9999" not in ids and len(ids) == len(set(ids))
    validations = [s.summary for s in plan.agent_trace
                   if s.kind == "validation"]
    assert any("PLC9999" in v for v in validations)
    assert any("omitted day" in v for v in validations)
    assert any("FL_FAKE" in v for v in validations)
    # Every day has the real (stubbed) weather attached.
    assert all(d.weather is not None for d in plan.days)
    assert plan.budget.grand_total == sum(l.amount for l in plan.budget.lines)


def test_llm_failure_falls_back_to_rule_based(monkeypatch, trip_dates,
                                              fake_key):
    start, _ = trip_dates

    calls = []

    def boom(**kw):
        calls.append(kw.get("model"))
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")
    monkeypatch.setattr(travel_agent, "create_chat_model", boom)
    plan = travel_agent.run_planning(make_request(start))
    assert plan.mode == "rule_based"
    assert any("rule-based" in w for w in plan.warnings)
    # Main model first, then the fallback model, then the rule-based planner.
    assert calls == [None, "gemini-3.5-flash-lite"]
    assert any("rate limit" in w for w in plan.warnings)


def test_rule_based_weather_aware_and_budget(trip_dates):
    start, _ = trip_dates
    plan = travel_agent.run_planning(
        make_request(start, days=5, budget=30000), force_rule_based=True)
    assert plan.mode == "rule_based"
    assert len(plan.days) == 5
    for day in plan.days:
        places = [a.place for a in day.morning + day.afternoon + day.evening
                  if a.place]
        assert len(places) <= 2
        if day.weather and day.weather.icon == "rain":
            outdoor = {"beach", "park", "lake", "fort", "monument"}
            assert not any(p.category in outdoor for p in places) or \
                all(d.weather.icon == "rain" for d in plan.days)
    assert plan.readable_summary.startswith(plan.trip_title)


def test_no_flight_route_produces_warning(trip_dates):
    start, _ = trip_dates
    plan = travel_agent.run_planning(
        make_request(start, origin="Delhi"), force_rule_based=True)
    assert plan.outbound_flight is None
    assert any("No direct flight" in w for w in plan.warnings)
    assert all(l.category != "Flights" for l in plan.budget.lines)


@pytest.mark.parametrize("days", [2, 8])
def test_trip_length_validation(days, trip_dates):
    start, _ = trip_dates
    with pytest.raises(ValueError):
        make_request(start, days=days)


def test_missing_key_uses_rule_based_with_warning(monkeypatch, trip_dates):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_api_key", None)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    start, _ = trip_dates
    plan = travel_agent.run_planning(make_request(start))
    assert plan.mode == "rule_based"
    assert any("No API key" in w for w in plan.warnings)
    assert any(s.kind == "tool_call" for s in plan.agent_trace)


def test_fallback_model_used_when_primary_rate_limited(monkeypatch, trip_dates,
                                                        fake_key):
    start, _ = trip_dates
    request = make_request(start)
    script = [AIMessage(content="", tool_calls=[call(
        "AgentPlanDraft", scripted_draft(start, bad_place=False), "c1")])]

    def factory(**kw):
        if kw.get("model") is None:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return ScriptedToolModel(script=script)
    monkeypatch.setattr(travel_agent, "create_chat_model", factory)
    plan = travel_agent.run_planning(request)
    assert plan.mode == "agent"
    assert plan.model == "gemini-3.5-flash-lite"
    assert any("fallback model" in w for w in plan.warnings)
    assert any("stopped" in s.summary for s in plan.agent_trace)
