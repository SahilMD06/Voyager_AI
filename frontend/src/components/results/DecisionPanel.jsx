import { BedDouble, CloudSun, MapPinned, Plane, Wallet } from "lucide-react";
import SectionHeading from "../ui/SectionHeading.jsx";

const ITEMS = [
  { key: "flight", title: "Why this flight", Icon: Plane },
  { key: "hotel", title: "Why this hotel", Icon: BedDouble },
  { key: "attractions", title: "Why these attractions", Icon: MapPinned },
  { key: "weather_and_location", title: "How weather and location shaped the days", Icon: CloudSun },
  { key: "budget", title: "How the budget was optimised", Icon: Wallet },
];

export default function DecisionPanel({ plan }) {
  return (
    <section>
      <SectionHeading
        id="why"
        title="Why Your AI Travel Agent Chose This Plan"
        intro={
          plan.mode === "agent"
            ? `Written by the agent (${plan.model}) from the tool results it retrieved, then checked against the data.`
            : "Generated from the rule-based planner's scoring criteria, because no LLM was available."
        }
      />
      <div className="overflow-hidden rounded-[22px] bg-ink text-white">
        <dl className="divide-y divide-white/10">
          {ITEMS.map(({ key, title, Icon }) => (
            <div key={key} className="grid gap-3 p-6 md:grid-cols-[280px_1fr] md:gap-8 sm:p-7">
              <dt className="flex items-center gap-3 font-display text-lg font-semibold">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/10 text-sky"><Icon size={19} /></span>
                {title}
              </dt>
              <dd className="leading-relaxed text-white/80">{plan.explanations[key]}</dd>
            </div>
          ))}
        </dl>
      </div>
      {plan.general_tips?.length > 0 && (
        <div className="mt-5 rounded-2xl border border-line bg-white p-5">
          <p className="font-semibold">Travel tips from the agent</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate">
            {plan.general_tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}
