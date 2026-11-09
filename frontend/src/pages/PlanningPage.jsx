import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, Loader2, Plane, Terminal } from "lucide-react";
import { useEffect, useRef } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import Button from "../components/ui/Button.jsx";
import { STAGES, useTrip } from "../hooks/useTrip.jsx";
import { dateFull } from "../utils/format";

function StageRow({ stage, state, index }) {
  const { status, detail } = state;
  return (
    <motion.li
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="flex items-start gap-4"
    >
      <span
        className={`mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full border-2 transition-colors duration-300 ${
          status === "done"
            ? "border-lagoon bg-lagoon text-white"
            : status === "active"
              ? "border-sky bg-sky-soft text-sky"
              : "border-line bg-white text-mist"
        }`}
      >
        {status === "done" ? <Check size={17} /> : status === "active" ? <Loader2 size={17} className="animate-spin" /> : <span className="text-sm font-semibold">{index + 1}</span>}
      </span>
      <div className="min-w-0 pt-1">
        <p className={`font-medium ${status === "pending" ? "text-mist" : "text-ink"}`}>{stage.label}</p>
        <AnimatePresence mode="wait">
          {detail && status !== "pending" && (
            <motion.p key={detail} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="truncate text-sm text-slate">
              {detail}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  );
}

export default function PlanningPage() {
  const { run, draft, startPlanning, cancelPlanning } = useTrip();
  const navigate = useNavigate();
  const logRef = useRef(null);

  useEffect(() => {
    if (run.status === "done" && run.planId) {
      const t = setTimeout(() => navigate(`/trip/${run.planId}`, { replace: true }), 1100);
      return () => clearTimeout(t);
    }
  }, [run.status, run.planId, navigate]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [run.log.length]);

  if (run.status === "idle" || !draft) return <Navigate to="/plan" replace />;

  const doneCount = Object.values(run.stages).filter((s) => s.status === "done").length;
  const progress = Math.round((doneCount / STAGES.length) * 100);

  return (
    <div className="mx-auto max-w-6xl px-5 pt-28 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[24px] border border-line bg-white p-6 shadow-lift sm:p-8">
          <p className="text-sm text-slate">
            {draft.origin} to {draft.destination}, {dateFull(draft.departure_date)} to {dateFull(draft.return_date)}, {draft.travelers} traveller{draft.travelers > 1 ? "s" : ""}
          </p>
          <h1 className="mt-2 text-3xl md:text-4xl">
            {run.status === "done" ? "Your plan is ready" : run.status === "error" ? "Planning stopped" : "Your agent is planning"}
          </h1>

          <div className="relative mt-6 h-12 overflow-hidden rounded-full bg-cloud" aria-hidden="true">
            <motion.div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-sky to-lagoon"
              animate={{ width: `${Math.max(progress, 6)}%` }}
              transition={{ type: "spring", stiffness: 60, damping: 18 }}
            />
            <motion.span
              className="absolute top-1/2 -translate-y-1/2 text-white"
              animate={{ left: `calc(${Math.max(progress, 6)}% - 34px)` }}
              transition={{ type: "spring", stiffness: 60, damping: 18 }}
            >
              <Plane size={22} className="rotate-45" />
            </motion.span>
          </div>
          <p className="mt-2 text-right text-sm text-slate" aria-live="polite">{progress}% complete</p>

          <ol className="mt-6 space-y-5">
            {STAGES.map((stage, i) => (
              <StageRow key={stage.key} stage={stage} state={run.stages[stage.key]} index={i} />
            ))}
          </ol>

          {run.status === "error" && (
            <div className="mt-8 rounded-2xl bg-alert-soft p-5" role="alert">
              <p className="flex items-center gap-2 font-semibold text-alert"><AlertTriangle size={18} /> {run.error}</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button onClick={() => startPlanning(draft)}>Try again</Button>
                <Button variant="outline" onClick={() => startPlanning(draft, { ruleBased: true })}>Use the rule-based planner</Button>
                <Button variant="ghost" onClick={() => navigate("/plan")}>Change trip details</Button>
              </div>
            </div>
          )}
          {run.status === "running" && (
            <Button variant="ghost" className="mt-8" onClick={() => { cancelPlanning(); navigate("/plan"); }}>
              Cancel
            </Button>
          )}
        </div>

        <div className="flex flex-col rounded-[24px] bg-ink p-6 text-white sm:p-7">
          <h2 className="flex items-center gap-2 text-lg"><Terminal size={18} className="text-sky" /> Live agent activity</h2>
          <p className="mt-1 text-sm text-white/60">Every tool call and result, as it happens.</p>
          <ul ref={logRef} className="mt-5 max-h-[460px] flex-1 space-y-2.5 overflow-y-auto pr-1 font-[ui-monospace,monospace] text-[13px]">
            {run.log.length === 0 && <li className="text-white/50">Waiting for the first step...</li>}
            {run.log.map((entry, i) => (
              <motion.li key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="leading-relaxed">
                {entry.kind === "tool" && <span className="text-sky">call  {entry.text}</span>}
                {entry.kind === "result" && <span className="text-[#7fdcd2]">  ok  {entry.text}{entry.ms != null && <span className="text-white/40"> ({entry.ms} ms)</span>}</span>}
                {entry.kind === "error" && <span className="text-[#ff9c90]"> err  {entry.text}</span>}
                {entry.kind === "thought" && <span className="text-white/85">think {entry.text}</span>}
                {entry.kind === "info" && <span className="text-marigold">info  {entry.text}</span>}
              </motion.li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
