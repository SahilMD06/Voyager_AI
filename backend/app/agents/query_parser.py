"""Natural-language trip query -> structured fields (+ missing info)."""

from __future__ import annotations

from datetime import date

from app.agents.llm_factory import create_chat_model
from app.agents.prompts import QUERY_PARSER_PROMPT
from app.models.schemas import ParsedTripQuery
from app.services.data_repository import get_repository, normalise_city

REQUIRED = ["origin", "destination", "departure_date", "return_date",
            "travelers", "budget"]


def parse_trip_query(query: str) -> ParsedTripQuery:
    """Use the LLM to extract trip fields and list what is missing."""
    repo = get_repository()
    model = create_chat_model().with_structured_output(ParsedTripQuery)
    prompt = QUERY_PARSER_PROMPT.format(
        today=date.today().isoformat(), cities=", ".join(repo.cities()),
        query=query)
    parsed: ParsedTripQuery = model.invoke(prompt)
    if parsed.origin:
        parsed.origin = normalise_city(parsed.origin, repo)
    if parsed.destination:
        parsed.destination = normalise_city(parsed.destination, repo)
    # Recompute missing fields ourselves rather than trusting the model.
    parsed.missing_fields = [f for f in REQUIRED
                             if getattr(parsed, f) in (None, "", 0)]
    if not parsed.missing_fields:
        parsed.clarifying_question = None
    return parsed
