# Architecture notes

## Request lifecycle

1. The planner form posts a `TripRequest` to `POST /api/plan/stream`.
2. `routes.plan_stream` starts `run_planning` in a worker thread and relays
   every event from a thread-safe queue as an SSE `data:` line.
3. `run_planning` (`agents/travel_agent.py`):
   - emits the *understanding* stage,
   - builds five `StructuredTool`s bound to a fresh `ToolLedger`,
   - runs `langchain.agents.create_agent(model, tools, system_prompt,
     response_format=ToolStrategy(AgentPlanDraft))` with
     `stream_mode="updates"` so every model turn and tool result is observed,
   - passes the structured `AgentPlanDraft` to `plan_assembler.build_plan`.
4. `build_plan` validates and assembles the `TripPlan` and the readable text.
5. The final event `{"type": "result", "plan": {...}}` closes the stream.

## SSE event types

| type | fields | meaning |
| --- | --- | --- |
| `stage` | stage, status (`active`/`done`), message | pipeline stage change |
| `tool_start` | tool, stage, arguments | a tool is about to run (agent-chosen args) |
| `tool_end` | tool, stage, summary, duration_ms, ok | tool finished |
| `thought` | text | interim text the model produced between tool calls |
| `info` | message | mode information (agent start, fallback) |
| `result` | plan | the complete `TripPlan` |
| `error` | message | unrecoverable failure |

Stages: `understanding, flights, hotels, places, weather, itinerary, budget`.
Tool → stage mapping lives in `tools/registry.py::TOOL_STAGES`.

## Validation rules (plan_assembler.py)

| Check | Action when it fails |
| --- | --- |
| A required lookup (either flight leg, hotels, places, weather) was not made | Validator runs the tool itself and logs it |
| Chosen flight/hotel id not in the tool results | Replaced with the top-ranked option; logged |
| Activity `place_id` unknown | Activity removed; logged |
| Same place scheduled twice | Second visit removed; logged |
| Day missing / extra days | Missing days filled by the scheduler; extras trimmed |
| Budget | Always recomputed from final ids with `estimate_budget` |
| Weather | Attached per date from the weather tool result |

## Fallback modes

| Situation | Behaviour | Visible as |
| --- | --- | --- |
| No API key | Rule-based planner (same tools, explicit scoring + budget swap) | `mode: rule_based`, warning, "Agent offline" pill |
| LLM error (quota, network, bad output) | Same rule-based planner | warning with the error |
| No direct flight | Leg is `null`; existing routes listed | warning, dashed flight card |
| Dates > 16 days ahead | Last year's recorded weather | "Last year's record" badge |
| Weather API down | Day marked unavailable | "Unavailable" badge |

## Configuration

All settings are in `backend/app/config.py` and can be overridden in
`backend/.env` (see `.env.example`): LLM provider/model/temperature/keys,
Open-Meteo URLs, HTTP timeout and retries, budget estimate assumptions, CORS
origins.
