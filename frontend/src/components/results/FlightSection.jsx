import { AnimatePresence, motion } from "framer-motion";
import { ArrowDownUp, Plane, PlaneLanding, PlaneTakeoff } from "lucide-react";
import { useMemo, useState } from "react";
import { dateFull, duration, inr, time } from "../../utils/format";
import SectionHeading from "../ui/SectionHeading.jsx";
import SourceBadge from "../ui/SourceBadge.jsx";

const TAG_LABELS = {
  cheapest: "Cheapest", fastest: "Fastest", date_match: "On your date",
  best_cheapest: "Best for cheapest", best_fastest: "Best for fastest", best_balanced: "Best balanced",
};

function FlightTicket({ flight, leg, travelers }) {
  if (!flight) {
    return (
      <div className="rounded-[20px] border border-dashed border-marigold bg-marigold-soft/50 p-6">
        <p className="font-semibold">{leg} flight</p>
        <p className="mt-1 text-slate">No direct flight for this route in flights.json. The agent didn't invent one, so arrange this leg separately.</p>
      </div>
    );
  }
  return (
    <div className="grid overflow-hidden rounded-[20px] border border-line bg-white shadow-lift sm:grid-cols-[1fr_26px_200px]">
      <div className="p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-sm font-medium text-slate">
            {leg === "Outbound" ? <PlaneTakeoff size={16} /> : <PlaneLanding size={16} />} {leg}
          </p>
          <p className="text-sm text-mist">{flight.flight_id}</p>
        </div>
        <p className="mt-2 font-display text-xl font-semibold">{flight.airline}</p>
        <div className="mt-4 grid grid-cols-[auto_1fr_auto] items-center gap-4">
          <div>
            <p className="font-display text-3xl font-semibold">{time(flight.departure_time)}</p>
            <p className="text-sm text-slate">{flight.origin}</p>
          </div>
          <div className="relative flex flex-col items-center">
            <span className="text-xs text-slate">{duration(flight.duration_minutes)}</span>
            <div className="relative my-1.5 h-px w-full bg-line">
              <Plane size={16} className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rotate-90 bg-white text-sky" />
            </div>
            <span className="text-xs text-mist">Direct</span>
          </div>
          <div className="text-right">
            <p className="font-display text-3xl font-semibold">{time(flight.arrival_time)}</p>
            <p className="text-sm text-slate">{flight.destination}</p>
          </div>
        </div>
        <p className="mt-4 text-sm text-slate">
          Dataset schedule date: {dateFull(flight.departure_time)}
          {flight.date_match !== "exact" && " (reference schedule, not your travel date)"}
        </p>
      </div>
      <div className="perforation ticket-notch relative hidden sm:block" />
      <div className="flex flex-col justify-between gap-3 border-t border-dashed border-line bg-cloud/60 p-5 sm:border-t-0 sm:p-6">
        <div>
          <p className="font-display text-2xl font-semibold">{inr(flight.price_per_person)}</p>
          <p className="text-sm text-slate">per person</p>
          <p className="mt-2 text-sm"><span className="font-semibold">{inr(flight.total_price)}</span> for {travelers}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <SourceBadge kind="dataset" />
          {flight.tags.filter((t) => TAG_LABELS[t]).map((t) => (
            <span key={t} className="rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-ink">{TAG_LABELS[t]}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function CompareTable({ options, selectedId, title }) {
  const [sort, setSort] = useState("price");
  const sorted = useMemo(
    () =>
      [...options].sort((a, b) =>
        sort === "price" ? a.price_per_person - b.price_per_person : sort === "duration" ? a.duration_minutes - b.duration_minutes : b.score - a.score,
      ),
    [options, sort],
  );
  if (!options.length) return null;
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <p className="font-medium">{title}</p>
        <label className="flex items-center gap-2 text-sm text-slate">
          <ArrowDownUp size={14} /> Sort by
          <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1 text-ink">
            <option value="price">Price</option>
            <option value="duration">Duration</option>
            <option value="score">Agent score</option>
          </select>
        </label>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-cloud/60 text-slate">
            <tr>
              <th className="px-5 py-2.5 font-medium">Flight</th>
              <th className="px-5 py-2.5 font-medium">Departs</th>
              <th className="px-5 py-2.5 font-medium">Arrives</th>
              <th className="px-5 py-2.5 font-medium">Duration</th>
              <th className="px-5 py-2.5 font-medium">Per person</th>
              <th className="px-5 py-2.5 font-medium">Why it ranks here</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((f) => (
              <tr key={f.flight_id} className={`border-t border-line ${f.flight_id === selectedId ? "bg-lagoon-soft/50" : ""}`}>
                <td className="px-5 py-3 font-medium">
                  {f.airline} <span className="text-mist">{f.flight_id}</span>
                  {f.flight_id === selectedId && <span className="ml-2 rounded-full bg-lagoon px-2 py-0.5 text-xs text-white">Selected</span>}
                </td>
                <td className="px-5 py-3">{time(f.departure_time)}</td>
                <td className="px-5 py-3">{time(f.arrival_time)}</td>
                <td className="px-5 py-3">{duration(f.duration_minutes)}</td>
                <td className="px-5 py-3 font-semibold">{inr(f.price_per_person)}</td>
                <td className="px-5 py-3 text-slate">{f.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function FlightSection({ plan }) {
  const [compare, setCompare] = useState(false);
  const total = plan.flight_options_outbound.length + plan.flight_options_return.length;
  return (
    <section>
      <SectionHeading
        id="flights"
        title="Flights"
        intro={`Picked for a "${plan.request.flight_preference}" preference from the direct flights in the dataset.`}
        action={
          total > 0 && (
            <button onClick={() => setCompare((v) => !v)} className="rounded-xl border border-line bg-white px-4 py-2 text-sm font-semibold hover:bg-cloud" aria-expanded={compare}>
              {compare ? "Hide comparison" : total === 1 ? "Show flight details" : `Compare all ${total} options`}
            </button>
          )
        }
      />
      <div className="grid gap-5 xl:grid-cols-2">
        <FlightTicket flight={plan.outbound_flight} leg="Outbound" travelers={plan.request.travelers} />
        <FlightTicket flight={plan.return_flight} leg="Return" travelers={plan.request.travelers} />
      </div>
      <AnimatePresence>
        {compare && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-5 space-y-5">
              <CompareTable title={`${plan.request.origin} to ${plan.destination.city}`} options={plan.flight_options_outbound} selectedId={plan.outbound_flight?.flight_id} />
              <CompareTable title={`${plan.destination.city} to ${plan.request.origin}`} options={plan.flight_options_return} selectedId={plan.return_flight?.flight_id} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
