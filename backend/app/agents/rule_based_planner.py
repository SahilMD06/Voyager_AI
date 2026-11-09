"""Deterministic fallback planner (used only when no LLM is available).

It calls the same five tools through the same ledger, applies explicit
ranking and budget-optimisation rules, and is labelled ``rule_based`` in the
output so it is never mistaken for the LLM agent.
"""

from __future__ import annotations

from app.agents.itinerary_scheduler import schedule_days
from app.agents.plan_assembler import ensure_tool_data
from app.models.schemas import (
    AgentPlanDraft, AgentStep, DecisionExplanations, TripRequest,
)
from app.tools.budget_estimator import estimate_budget
from app.tools.registry import ToolLedger


def plan_rule_based(request: TripRequest, ledger: ToolLedger,
                    trace: list[AgentStep],
                    emit=lambda event: None) -> AgentPlanDraft:
    """Run tools in a fixed order and pick options by explicit rules."""
    already_traced = len(ledger.calls)
    data = ensure_tool_data(request, ledger, [])
    for record in ledger.calls[already_traced:]:
        trace.append(AgentStep(
            index=len(trace) + 1, kind="tool_call", tool=record.tool,
            arguments=record.arguments, summary=record.summary,
            duration_ms=record.duration_ms))
    emit({"type": "stage", "stage": "itinerary", "status": "active",
          "message": "Scheduling with weather-aware planner rules"})
    outbound = data["outbound"].options
    inbound = data["inbound"].options
    hotels = data["hotels"].options
    places = data["places"].options
    weather = {d.date: d for d in data["weather"].days} if data["weather"] \
        else {}

    out_pick = outbound[0] if outbound else None
    in_pick = inbound[0] if inbound else None
    hotel_pick = hotels[0] if hotels else None

    def total(out, inn, hotel) -> int:
        days = schedule_days(request, places, weather, out, inn, hotel)
        ids = [a.place_id for d in days for a in d.morning + d.afternoon
               + d.evening if a.place_id]
        return estimate_budget(
            request.travelers, request.nights,
            out.flight_id if out else None, inn.flight_id if inn else None,
            hotel.hotel_id if hotel else None, ids,
            request.accommodation_type, request.budget).grand_total

    cost = total(out_pick, in_pick, hotel_pick)
    if cost > request.budget:
        # 1) cheaper hotels (cheapest first), 2) cheapest flights.
        for hotel in sorted(hotels, key=lambda h: h.price_per_night):
            if hotel.price_per_night < (hotel_pick.price_per_night
                                        if hotel_pick else 0):
                trial = total(out_pick, in_pick, hotel)
                if trial < cost:
                    trace.append(AgentStep(
                        index=len(trace) + 1, kind="reasoning",
                        summary=f"Over budget (Rs {cost:,}); switched hotel "
                                f"to {hotel.name} ({hotel.hotel_id}) -> Rs "
                                f"{trial:,}."))
                    hotel_pick, cost = hotel, trial
                    if cost <= request.budget:
                        break
        if cost > request.budget:
            cheap_out = min(outbound, key=lambda f: f.price_per_person,
                            default=None)
            cheap_in = min(inbound, key=lambda f: f.price_per_person,
                           default=None)
            trial = total(cheap_out, cheap_in, hotel_pick)
            if trial < cost:
                trace.append(AgentStep(
                    index=len(trace) + 1, kind="reasoning",
                    summary=f"Still over budget; switched to cheapest flights "
                            f"-> Rs {trial:,}."))
                out_pick, in_pick, cost = cheap_out, cheap_in, trial

    days = schedule_days(request, places, weather, out_pick, in_pick,
                         hotel_pick)
    if already_traced:
        trace.append(AgentStep(
            index=len(trace) + 1, kind="reasoning",
            summary=f"Rule-based planner reused {already_traced} tool "
                    "result(s) already fetched by the agent."))
    trace.append(AgentStep(
        index=len(trace) + 1, kind="reasoning",
        summary=f"Scheduled {sum(1 for d in days for a in d.morning + d.afternoon + d.evening if a.place_id)} "
                f"attraction(s) over {len(days)} day(s) using weather-aware "
                "rules."))
    placeholder = DecisionExplanations(flight="", hotel="", attractions="",
                                       weather_and_location="", budget="")
    return AgentPlanDraft(
        trip_title=f"{request.days}-Day Trip to {request.destination}",
        summary="", outbound_flight_id=out_pick.flight_id if out_pick else None,
        return_flight_id=in_pick.flight_id if in_pick else None,
        hotel_id=hotel_pick.hotel_id if hotel_pick else None,
        days=days, explanations=placeholder,
    )
