import { motion } from "framer-motion";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { inr } from "../../utils/format";
import SectionHeading from "../ui/SectionHeading.jsx";
import SourceBadge from "../ui/SourceBadge.jsx";

const COLORS = {
  Flights: "#0E2240",
  Accommodation: "#4AA3E8",
  Food: "#F2A93B",
  "Local transport": "#0F9C8F",
  Activities: "#8A9BB0",
};

export default function BudgetPanel({ plan }) {
  const b = plan.budget;
  const data = b.lines.filter((l) => l.amount > 0).map((l) => ({ name: l.category, value: l.amount }));
  const used = b.user_budget ? Math.min(100, (b.grand_total / b.user_budget) * 100) : 0;
  return (
    <section>
      <SectionHeading id="budget" title="Budget breakdown" intro={`${b.note} Prices from the dataset are marked separately from estimates.`} />
      <div className="grid gap-6 rounded-[22px] border border-line bg-white p-5 shadow-lift sm:p-7 lg:grid-cols-[320px_1fr]">
        <div className="relative h-72">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="92%" paddingAngle={2} stroke="none" animationDuration={900}>
                {data.map((d) => <Cell key={d.name} fill={COLORS[d.name] || "#8A9BB0"} />)}
              </Pie>
              <Tooltip formatter={(v) => inr(v)} contentStyle={{ borderRadius: 12, border: "1px solid #e3e7ec" }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
            <div>
              <p className="text-sm text-slate">Total</p>
              <p className="font-display text-2xl font-semibold">{inr(b.grand_total)}</p>
              <p className="text-xs text-mist">{inr(b.per_person)} per person</p>
            </div>
          </div>
        </div>
        <div>
          <ul className="divide-y divide-line">
            {b.lines.map((l) => (
              <li key={l.category} className="flex flex-wrap items-center justify-between gap-3 py-3.5">
                <div className="flex items-start gap-3">
                  <span className="mt-1.5 h-3 w-3 shrink-0 rounded-full" style={{ background: COLORS[l.category] }} />
                  <div>
                    <p className="font-medium">{l.category} <SourceBadge kind={l.basis} className="ml-1.5" /></p>
                    <p className="text-sm text-slate">{l.detail}</p>
                  </div>
                </div>
                <p className="font-display text-lg font-semibold">{inr(l.amount)}</p>
              </li>
            ))}
          </ul>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl bg-sky-soft/60 p-3"><p className="text-slate">From dataset prices</p><p className="font-semibold">{inr(b.dataset_total)}</p></div>
            <div className="rounded-xl bg-marigold-soft/60 p-3"><p className="text-slate">Estimated</p><p className="font-semibold">{inr(b.estimated_total)}</p></div>
          </div>
          {b.user_budget && (
            <div className="mt-5">
              <div className="flex justify-between text-sm">
                <span className="text-slate">Your budget {inr(b.user_budget)}</span>
                <span className={b.within_budget ? "font-semibold text-lagoon" : "font-semibold text-alert"}>
                  {b.within_budget ? `${inr(b.remaining)} left` : `${inr(-b.remaining)} over`}
                </span>
              </div>
              <div className="mt-2 h-3 overflow-hidden rounded-full bg-cloud">
                <motion.div
                  className={`h-full rounded-full ${b.within_budget ? "bg-lagoon" : "bg-alert"}`}
                  initial={{ width: 0 }}
                  whileInView={{ width: `${used}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, ease: "easeOut" }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
