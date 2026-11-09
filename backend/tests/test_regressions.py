"""Regression tests for issues found while running against real Gemini."""

from __future__ import annotations

from app.config import Settings
from app.models.schemas import ActivityDraft


def test_llm_string_null_place_id_is_treated_as_none():
    # Gemini writes "null" as a string for non-attraction activities.
    for raw in ("null", "None", "", "  n/a "):
        draft = ActivityDraft(place_id=raw, title="Check in", description="x")
        assert draft.place_id is None
    assert ActivityDraft(place_id=" PLC0012 ", title="t",
                         description="d").place_id == "PLC0012"


def test_blank_env_values_fall_back_to_defaults(tmp_path):
    env = tmp_path / ".env"
    env.write_text("LLM_PROVIDER=gemini\nLLM_MODEL=\nLLM_TEMPERATURE=\n"
                   "GOOGLE_API_KEY=abc\nOPENAI_BASE_URL=\n", encoding="utf-8")
    settings = Settings(_env_file=env)
    assert settings.llm_temperature is None
    assert settings.resolved_model == "gemini-3.5-flash"
    assert settings.openai_base_url is None
    assert settings.llm_api_key == "abc"


def test_food_tier_follows_hotel_not_llm_argument():
    from app.services.data_repository import get_repository
    from app.tools.budget_estimator import estimate_budget
    hotels = get_repository().hotels
    five_star = hotels[hotels["stars"] == 5].iloc[0]["hotel_id"]
    a = estimate_budget(2, 2, hotel_id=five_star, accommodation_type="resort")
    b = estimate_budget(2, 2, hotel_id=five_star, accommodation_type="budget")
    assert a.grand_total == b.grand_total


def test_flight_or_hotel_id_in_place_field_keeps_activity():
    from app.agents.plan_assembler import _convert
    from app.models.schemas import ActivityDraft
    notes: list[str] = []
    acts = _convert([ActivityDraft(place_id="FL0007", title="Fly in",
                                   description="x")], {}, set(), notes)
    assert len(acts) == 1 and acts[0].place is None and not notes
    acts = _convert([ActivityDraft(place_id="PLC9999", title="Fake",
                                   description="x")], {}, set(), notes)
    assert acts == [] and notes


def test_cors_origins_tolerate_copy_paste_slips(tmp_path):
    env = tmp_path / ".env"
    env.write_text('CORS_ORIGINS="https://a.vercel.app/ , http://localhost:5173;"\n',
                   encoding="utf-8")
    assert Settings(_env_file=env).cors_origin_list == [
        "https://a.vercel.app", "http://localhost:5173"]


def test_met_norway_fallback_when_open_meteo_rate_limited(monkeypatch):
    from datetime import date, timedelta
    from app.services import weather_service as ws
    from app.utils.http import ExternalAPIError

    today = date.today()
    monkeypatch.setattr(ws, "geocode_city", lambda city: {
        "name": "Panjim", "admin1": "Goa", "latitude": 15.5,
        "longitude": 73.8, "timezone": "Asia/Kolkata"})

    def limited(*a, **k):
        raise ExternalAPIError("HTTP 429: Daily API request limit exceeded")
    monkeypatch.setattr(ws, "_fetch_forecast", limited)
    monkeypatch.setattr(ws, "_fetch_archive", limited)
    day = (today + timedelta(days=1)).isoformat()
    monkeypatch.setattr(ws, "_fetch_met_norway", lambda *a: {
        day: {"temperature_2m_max": 31.0, "temperature_2m_min": 24.0,
              "precipitation_sum": 6.2, "symbol": "lightrain"}})
    result = ws.get_trip_weather("Goa", today + timedelta(days=1),
                                 today + timedelta(days=2), today=today)
    first, second = result.days
    assert first.source == "forecast" and "MET Norway" in first.source_note
    assert first.condition == "Light rain" and first.temp_max_c == 31.0
    assert second.source == "unavailable"  # never invented
    assert "MET Norway" in result.note
