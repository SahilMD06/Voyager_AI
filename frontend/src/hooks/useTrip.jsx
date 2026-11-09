import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, streamPlan } from "../services/api";

const TripContext = createContext(null);

// Planning stages shown in the UI. They are driven by real backend events:
// tool_start / tool_end events carry the stage of the tool being run.
export const STAGES = [
  { key: "understanding", label: "Understanding your travel preferences" },
  { key: "flights", label: "Searching available flights" },
  { key: "hotels", label: "Comparing hotel options" },
  { key: "places", label: "Discovering attractions" },
  { key: "weather", label: "Checking weather forecasts" },
  { key: "itinerary", label: "Optimizing your daily itinerary" },
  { key: "budget", label: "Calculating your estimated budget" },
];

const STORAGE_KEY = "voyager.plans.v1";

function loadPlans() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function savePlans(plans) {
  try {
    // Keep the 8 most recent plans.
    const entries = Object.entries(plans)
      .sort((a, b) => (b[1].generated_at > a[1].generated_at ? 1 : -1))
      .slice(0, 8);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(entries)));
  } catch {
    /* storage unavailable: plans stay in memory */
  }
}

const initialRun = () => ({
  status: "idle", // idle | running | done | error
  stages: Object.fromEntries(STAGES.map((s) => [s.key, { status: "pending", detail: "" }])),
  log: [],
  error: null,
  planId: null,
});

export function TripProvider({ children }) {
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(null);
  const [destinations, setDestinations] = useState(null);
  const [draft, setDraft] = useState(null); // last submitted / prefilled request
  const [plans, setPlans] = useState(loadPlans);
  const [run, setRun] = useState(initialRun);
  const controller = useRef(null);

  const loadMeta = useCallback(() => {
    setMetaError(null);
    api.meta().then(setMeta).catch((e) => setMetaError(e.message));
    api.destinations().then(setDestinations).catch(() => setDestinations([]));
  }, []);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const handleEvent = useCallback((event) => {
    setRun((prev) => {
      const next = { ...prev, stages: { ...prev.stages }, log: prev.log };
      const mark = (key, status, detail) => {
        if (!key || !next.stages[key]) return;
        const current = next.stages[key];
        // Never move a finished stage back to active.
        if (current.status === "done" && status === "active") return;
        next.stages[key] = { status, detail: detail ?? current.detail };
      };
      if (event.type === "stage") {
        mark(event.stage, event.status, event.message || undefined);
      } else if (event.type === "tool_start") {
        mark(event.stage, "active", `Running ${event.tool}`);
        next.log = [...prev.log, { kind: "tool", text: `${event.tool}(${summariseArgs(event.arguments)})` }];
      } else if (event.type === "tool_end") {
        next.stages[event.stage] = { status: "done", detail: event.summary };
        next.log = [...next.log, { kind: event.ok ? "result" : "error", text: event.summary, ms: event.duration_ms }];
      } else if (event.type === "thought") {
        next.log = [...prev.log, { kind: "thought", text: event.text }];
      } else if (event.type === "info") {
        next.log = [...prev.log, { kind: "info", text: event.message }];
      } else if (event.type === "error") {
        next.status = "error";
        next.error = event.message;
      }
      return next;
    });
    if (event.type === "result") {
      const plan = event.plan;
      setPlans((prev) => {
        const updated = { ...prev, [plan.plan_id]: plan };
        savePlans(updated);
        return updated;
      });
      setRun((prev) => ({
        ...prev,
        status: "done",
        planId: plan.plan_id,
        stages: Object.fromEntries(
          Object.entries(prev.stages).map(([k, v]) => [k, { ...v, status: "done" }]),
        ),
      }));
    }
  }, []);

  const startPlanning = useCallback(
    async (tripRequest, { ruleBased = false } = {}) => {
      controller.current?.abort();
      const ctrl = new AbortController();
      controller.current = ctrl;
      setDraft(tripRequest);
      setRun({ ...initialRun(), status: "running" });
      try {
        await streamPlan(tripRequest, { onEvent: handleEvent, signal: ctrl.signal, ruleBased });
        setRun((prev) =>
          prev.status === "running"
            ? { ...prev, status: "error", error: "The planner stopped before returning a plan. Try again." }
            : prev,
        );
      } catch (err) {
        if (err.name === "AbortError") return;
        setRun((prev) => ({ ...prev, status: "error", error: err.message }));
      }
    },
    [handleEvent],
  );

  const cancelPlanning = useCallback(() => {
    controller.current?.abort();
    setRun(initialRun());
  }, []);

  const value = {
    meta,
    metaError,
    reloadMeta: loadMeta,
    destinations,
    draft,
    setDraft,
    plans,
    run,
    startPlanning,
    cancelPlanning,
  };
  return <TripContext.Provider value={value}>{children}</TripContext.Provider>;
}

function summariseArgs(args = {}) {
  return Object.entries(args)
    .filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0))
    .slice(0, 4)
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("|") : v}`)
    .join(", ");
}

export function useTrip() {
  const ctx = useContext(TripContext);
  if (!ctx) throw new Error("useTrip must be used inside <TripProvider>");
  return ctx;
}
