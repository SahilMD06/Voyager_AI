import { AnimatePresence, motion } from "framer-motion";
import { Brain, ChevronDown, FileText, Info, ShieldCheck, Wrench } from "lucide-react";
import { useState } from "react";
import SectionHeading from "../ui/SectionHeading.jsx";

const KIND = {
  tool_call: { Icon: Wrench, label: "Tool call", cls: "bg-sky-soft text-ink" },
  reasoning: { Icon: Brain, label: "Reasoning", cls: "bg-lagoon-soft text-[#0a6b62]" },
  validation: { Icon: ShieldCheck, label: "Validation", cls: "bg-marigold-soft text-[#8a5a12]" },
  info: { Icon: Info, label: "Request", cls: "bg-cloud text-slate" },
};

export default function AgentTrace({ plan }) {
  const [open, setOpen] = useState(false);
  const [showText, setShowText] = useState(false);
  const toolCalls = plan.agent_trace.filter((s) => s.kind === "tool_call").length;
  return (
    <section>
      <SectionHeading
        id="trace"
        title="Agent trace"
        intro={`${plan.agent_trace.length} steps, ${toolCalls} tool calls decided by the ${plan.mode === "agent" ? "LLM agent" : "rule-based planner"}.`}
        action={
          <div className="flex gap-2">
            <button onClick={() => setShowText((v) => !v)} className="flex items-center gap-1.5 rounded-xl border border-line bg-white px-4 py-2 text-sm font-semibold hover:bg-cloud" aria-expanded={showText}>
              <FileText size={15} /> {showText ? "Hide text version" : "Text version"}
            </button>
            <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-1.5 rounded-xl border border-line bg-white px-4 py-2 text-sm font-semibold hover:bg-cloud" aria-expanded={open}>
              {open ? "Hide steps" : "Show steps"} <ChevronDown size={15} className={open ? "rotate-180" : ""} />
            </button>
          </div>
        }
      />
      <AnimatePresence>
        {showText && (
          <motion.pre key="text-version" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mb-5 overflow-x-auto rounded-2xl bg-ink p-6 text-[13px] leading-relaxed text-white/85">
            {plan.readable_summary}
          </motion.pre>
        )}
        {open && (
          <motion.ol key="steps" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="space-y-2 overflow-hidden">
            {plan.agent_trace.map((step) => {
              const k = KIND[step.kind] || KIND.info;
              return (
                <li key={step.index} className="flex gap-3 rounded-xl border border-line bg-white p-4">
                  <span className="w-7 shrink-0 pt-0.5 text-right text-sm text-mist">{step.index}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${k.cls}`}><k.Icon size={12} /> {k.label}</span>
                      {step.tool && <code className="text-sm font-semibold">{step.tool}</code>}
                      {step.duration_ms != null && <span className="text-xs text-mist">{step.duration_ms} ms</span>}
                    </div>
                    <p className="mt-1.5 text-sm text-slate">{step.summary}</p>
                    {step.arguments && (
                      <code className="mt-1.5 block overflow-x-auto whitespace-pre rounded-lg bg-cloud px-3 py-2 text-xs text-ink/80">
                        {JSON.stringify(step.arguments)}
                      </code>
                    )}
                  </div>
                </li>
              );
            })}
          </motion.ol>
        )}
      </AnimatePresence>
    </section>
  );
}
