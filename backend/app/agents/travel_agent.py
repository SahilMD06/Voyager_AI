"""The LangChain tool-calling travel agent and the planning orchestrator.

``run_planning`` is the single entry point used by the API. It:
1. builds per-request tools bound to a ToolLedger (which emits progress),
2. runs the LangChain agent (``langchain.agents.create_agent``) - the model
   decides which tools to call, in which order, and how often,
3. receives a validated ``AgentPlanDraft`` via structured output,
4. passes it through the plan assembler (anti-hallucination checks),
5. falls back to the rule-based planner only if no LLM is configured or the
   LLM call fails - and says so in the result.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.llm_factory import LLMNotConfiguredError, create_chat_model
from app.agents.plan_assembler import build_plan
from app.agents.prompts import AGENT_SYSTEM_PROMPT, build_agent_user_message
from app.agents.rule_based_planner import plan_rule_based
from app.config import get_settings
from app.models.schemas import AgentPlanDraft, AgentStep, TripPlan, TripRequest
from app.tools.registry import ToolLedger, build_tools

logger = logging.getLogger(__name__)

Emit = Callable[[dict], None]


def _stage(emit: Emit, stage: str, status: str, message: str = "") -> None:
    emit({"type": "stage", "stage": stage, "status": status,
          "message": message})


def _text_of(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts = [c.get("text", "") for c in content
             if isinstance(c, dict) and c.get("type") == "text"]
    return " ".join(p for p in parts if p).strip()


def run_agent(request: TripRequest, ledger: ToolLedger, trace: list[AgentStep],
              emit: Emit, model_name: str | None = None) -> AgentPlanDraft:
    """Run the LangChain agent and return its structured draft."""
    try:
        return _run_agent(request, ledger, trace, emit, model_name)
    finally:
        # Fill in tool results even if the run stopped part-way.
        _attach_tool_results(trace, ledger)


def _run_agent(request: TripRequest, ledger: ToolLedger,
               trace: list[AgentStep], emit: Emit,
               model_name: str | None) -> AgentPlanDraft:
    model = create_chat_model(model=model_name) if model_name else \
        create_chat_model()
    tools = build_tools(ledger)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
        response_format=ToolStrategy(AgentPlanDraft),
    )
    inputs = {"messages": [HumanMessage(
        build_agent_user_message(request, date.today()))]}
    structured: AgentPlanDraft | None = None

    for update in agent.stream(inputs, stream_mode="updates",
                               config={"recursion_limit": 40}):
        for node, state in update.items():
            if not isinstance(state, dict):
                continue
            if state.get("structured_response") is not None:
                structured = state["structured_response"]
            for message in state.get("messages", []) or []:
                if isinstance(message, AIMessage):
                    thought = _text_of(message)
                    if thought:
                        trace.append(AgentStep(index=len(trace) + 1,
                                               kind="reasoning",
                                               summary=thought[:600]))
                        emit({"type": "thought", "text": thought[:600]})
                    for call in message.tool_calls or []:
                        if call["name"] == "AgentPlanDraft":
                            _stage(emit, "itinerary", "active",
                                   "Composing the day-wise itinerary")
                            continue
                        trace.append(AgentStep(
                            index=len(trace) + 1, kind="tool_call",
                            tool=call["name"], arguments=call["args"],
                            summary=f"Agent decided to call {call['name']}"))
    if structured is None:
        raise RuntimeError("The agent finished without a structured plan.")
    return structured


def _short_error(exc: Exception) -> str:
    """One-line, user-readable reason for an LLM failure."""
    text = str(exc)
    if "RESOURCE_EXHAUSTED" in text or "429" in text or "rate" in text.lower():
        return "rate limit or quota reached (HTTP 429)"
    if "NOT_FOUND" in text or "404" in text:
        return "model not available for this API key (HTTP 404)"
    if "API key" in text or "PERMISSION_DENIED" in text or "401" in text:
        return "API key rejected"
    return f"{type(exc).__name__}: {text[:140]}"


def _same_args(call_args: dict, recorded: dict) -> bool:
    """True when every argument the model sent matches the recorded call."""
    for key, value in (call_args or {}).items():
        if key in recorded and str(recorded[key]).lower() != str(value).lower():
            return False
    return True


def _attach_tool_results(trace: list[AgentStep], ledger: ToolLedger) -> None:
    """Pair each agent tool-call step with its ledger record.

    Parallel calls finish in any order, so records are matched on tool name
    and arguments rather than on completion order.
    """
    used: set[int] = set()
    for step in trace:
        if step.kind != "tool_call" or step.duration_ms is not None:
            continue
        for index, record in enumerate(ledger.calls):
            if index in used or record.tool != step.tool:
                continue
            if _same_args(step.arguments or {}, record.arguments):
                used.add(index)
                step.summary = record.summary
                step.duration_ms = record.duration_ms
                break


def run_planning(request: TripRequest, emit: Emit | None = None,
                 force_rule_based: bool = False) -> TripPlan:
    """Plan a trip end to end, streaming progress events through ``emit``."""
    emit = emit or (lambda event: None)
    settings = get_settings()
    trace: list[AgentStep] = []
    ledger = ToolLedger(emit=emit)
    warnings: list[str] = []

    _stage(emit, "understanding", "active",
           f"{request.days}-day trip {request.origin} -> {request.destination}"
           f" for {request.travelers}")
    trace.append(AgentStep(
        index=1, kind="info",
        summary=(f"Request: {request.origin} -> {request.destination}, "
                 f"{request.departure_date} to {request.return_date} "
                 f"({request.nights} nights), {request.travelers} traveller(s),"
                 f" budget Rs {request.budget:,}, interests "
                 f"{[i.value for i in request.interests] or 'none'}, "
                 f"flights '{request.flight_preference.value}', stay "
                 f"'{request.accommodation_type.value}'.")))
    _stage(emit, "understanding", "done")

    draft: AgentPlanDraft | None = None
    mode = "rule_based"
    model_name = None
    if not force_rule_based and settings.llm_api_key is None:
        warnings.append(
            f"No API key is configured for LLM provider "
            f"'{settings.llm_provider}', so the rule-based planner was used. "
            "Add the key to backend/.env to enable the AI agent.")
        emit({"type": "info", "message":
              "No LLM key configured - running the rule-based planner"})
    elif force_rule_based:
        emit({"type": "info", "message": "Rule-based planner requested"})
    else:
        models = [settings.resolved_model]
        if settings.resolved_fallback_model:
            models.append(settings.resolved_fallback_model)
        errors: list[str] = []
        for attempt, name in enumerate(models):
            try:
                emit({"type": "info", "message":
                      f"Starting LangChain agent ({settings.llm_provider} / "
                      f"{name})"})
                draft = run_agent(request, ledger, trace, emit,
                                  None if attempt == 0 else name)
                mode, model_name = "agent", name
                break
            except LLMNotConfiguredError as exc:
                errors.append(str(exc))
                break
            except Exception as exc:  # LLM/network/quota errors
                logger.exception("Agent run with %s failed", name)
                reason = _short_error(exc)
                errors.append(f"{name}: {reason}")
                trace.append(AgentStep(
                    index=len(trace) + 1, kind="info",
                    summary=f"Agent run with {name} stopped: {reason}"))
                if attempt + 1 < len(models):
                    emit({"type": "info", "message":
                          f"{name} unavailable ({reason}) - retrying with "
                          f"{models[attempt + 1]}"})
        if draft is None:
            warnings.append(
                "The AI agent could not finish ("
                + "; ".join(errors)
                + "), so the rule-based planner completed the plan using the "
                  "same tools.")
            emit({"type": "info", "message":
                  "Agent unavailable - switching to rule-based planner"})
        elif model_name != settings.resolved_model:
            warnings.append(
                f"{settings.resolved_model} was unavailable ({errors[0]}); "
                f"this plan was made by the fallback model {model_name}.")

    if draft is None:
        draft = plan_rule_based(request, ledger, trace, emit)

    _stage(emit, "itinerary", "done")
    _stage(emit, "budget", "active", "Validating selections and costs")
    plan = build_plan(request, draft, ledger, mode, model_name, trace,
                      warnings)
    _stage(emit, "budget", "done",
           f"Estimated total Rs {plan.budget.grand_total:,}")
    return plan
