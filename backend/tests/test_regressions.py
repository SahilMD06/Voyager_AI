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
