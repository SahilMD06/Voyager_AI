import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Lightbulb, MapPin, Moon, Sun, Sunrise } from "lucide-react";
import { useState } from "react";
import { dateLong, inr, titleCase } from "../../utils/format";
import SectionHeading from "../ui/SectionHeading.jsx";
import SourceBadge from "../ui/SourceBadge.jsx";
import WeatherIcon from "../ui/WeatherIcon.jsx";

const SLOTS = [
  { key: "morning", label: "Morning", Icon: Sunrise },
  { key: "afternoon", label: "Afternoon", Icon: Sun },
  { key: "evening", label: "Evening", Icon: Moon },
];

function ActivityCard({ activity }) {
  const place = activity.place;
  return (
    <div className={`rounded-xl border p-3.5 ${place ? "border-sky/30 bg-sky-soft/40" : "border-line bg-white"}`}>
      <p className="font-medium leading-snug">{activity.title}</p>
      <p className="mt-0.5 text-sm text-slate">{activity.description}</p>
      {place && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate">
          <span className="flex items-center gap-1"><MapPin size={12} /> {titleCase(place.category)}</span>
          <span>Rated {place.rating}/5</span>
          <span>Entry est. {place.estimated_entry_cost ? inr(place.estimated_entry_cost) : "free"}</span>
        </p>
      )}
    </div>
  );
}

function DayCard({ day, open, onToggle, isLast }) {
  const wx = day.weather;
  const placeCount = [...day.morning, ...day.afternoon, ...day.evening].filter((a) => a.place).length;
  return (
    <li className="relative grid grid-cols-[44px_1fr] gap-4 sm:grid-cols-[64px_1fr]">
      <div className="relative flex flex-col items-center">
        <span className="z-10 grid h-11 w-11 place-items-center rounded-full bg-ink font-display text-lg font-semibold text-white sm:h-14 sm:w-14 sm:text-xl">
          {day.day}
        </span>
        {!isLast && <span className="absolute top-12 bottom-[-24px] w-0.5 bg-line sm:top-14" />}
      </div>
      <div className="mb-6 overflow-hidden rounded-[20px] border border-line bg-white shadow-lift">
        <button onClick={onToggle} className="flex w-full flex-wrap items-center justify-between gap-3 p-5 text-left sm:p-6" aria-expanded={open}>
          <div>
            <p className="text-sm text-slate">Day {day.day}, {dateLong(day.date)}</p>
            <h3 className="mt-0.5 text-xl">{day.theme}</h3>
            <p className="mt-1 text-sm text-slate">{placeCount} attraction{placeCount === 1 ? "" : "s"} planned, est. {inr(day.estimated_cost)}</p>
          </div>
          <div className="flex items-center gap-4">
            {wx && (
              <span className="flex items-center gap-2 rounded-full bg-cloud px-3 py-1.5 text-sm">
                <WeatherIcon icon={wx.icon} size={18} />
                {wx.source === "unavailable" ? "No data" : `${Math.round(wx.temp_max_c)}° / ${Math.round(wx.temp_min_c)}°`}
              </span>
            )}
            <ChevronDown className={`text-slate transition-transform ${open ? "rotate-180" : ""}`} />
          </div>
        </button>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden">
              <div className="border-t border-line p-5 sm:p-6">
                <div className="grid gap-5 md:grid-cols-3">
                  {SLOTS.map(({ key, label, Icon }) => (
                    <div key={key}>
                      <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate"><Icon size={15} /> {label}</p>
                      <div className="space-y-2.5">
                        {day[key].length ? day[key].map((a, i) => <ActivityCard key={i} activity={a} />) : <p className="text-sm text-mist">Free time</p>}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl bg-cloud/70 p-4 text-sm">
                    <p className="flex items-center gap-2 font-semibold">
                      {wx && <WeatherIcon icon={wx.icon} size={16} />} Weather plan
                      {wx && <SourceBadge kind={wx.source} />}
                    </p>
                    <p className="mt-1 text-slate">{day.weather_consideration || (wx ? `${wx.condition}.` : "No weather data.")}</p>
                  </div>
                  <div className="rounded-xl bg-marigold-soft/60 p-4 text-sm">
                    <p className="flex items-center gap-2 font-semibold"><Lightbulb size={16} className="text-marigold" /> Tips</p>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-slate">
                      {(day.tips.length ? day.tips : ["Keep the afternoon flexible."]).map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                </div>
                <p className="mt-4 text-xs text-mist">{day.cost_note}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </li>
  );
}

export default function ItineraryTimeline({ plan }) {
  const [open, setOpen] = useState(() => new Set([1]));
  const allOpen = open.size === plan.days.length;
  const toggle = (d) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });
  return (
    <section>
      <SectionHeading
        id="itinerary"
        title="Day-by-day itinerary"
        intro="Highlighted cards are attractions from places.json. Plain cards are meals, transfers and free time."
        action={
          <button
            onClick={() => setOpen(allOpen ? new Set() : new Set(plan.days.map((d) => d.day)))}
            className="rounded-xl border border-line bg-white px-4 py-2 text-sm font-semibold hover:bg-cloud"
          >
            {allOpen ? "Collapse all days" : "Expand all days"}
          </button>
        }
      />
      <ol>
        {plan.days.map((day, i) => (
          <DayCard key={day.day} day={day} open={open.has(day.day)} onToggle={() => toggle(day.day)} isLast={i === plan.days.length - 1} />
        ))}
      </ol>
    </section>
  );
}
