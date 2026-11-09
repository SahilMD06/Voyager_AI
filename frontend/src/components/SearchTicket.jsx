import { ArrowLeftRight, CalendarDays, Check, Minus, Plane, Plus, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useTrip } from "../hooks/useTrip.jsx";
import { addDays, daysBetween, isoDate } from "../utils/format";
import Button from "./ui/Button.jsx";

// The hero search, styled as a boarding pass.
export default function SearchTicket() {
  const { meta, setDraft } = useTrip();
  const navigate = useNavigate();
  const today = isoDate(new Date());
  const [form, setForm] = useState({
    origin: "Bangalore",
    destination: "Goa",
    departure_date: addDays(today, 7),
    return_date: addDays(today, 10),
    travelers: 2,
  });
  const cities = meta?.cities || [];
  const direct = useMemo(
    () => meta?.routes?.[form.origin]?.includes(form.destination),
    [meta, form.origin, form.destination],
  );
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const submit = (e) => {
    e.preventDefault();
    if (form.origin === form.destination) return toast.error("Choose two different cities.");
    const days = daysBetween(form.departure_date, form.return_date) + 1;
    if (days < 3 || days > 7) return toast.error("Trips can be 3 to 7 days long.");
    setDraft((d) => ({ ...(d || {}), ...form }));
    navigate("/plan");
  };

  const select =
    "w-full appearance-none bg-transparent cursor-pointer font-display text-[23px] font-semibold leading-tight text-ink outline-none xl:text-[26px]";

  return (
    <form
      onSubmit={submit}
      className="relative grid overflow-visible rounded-[22px] bg-white text-ink shadow-float md:grid-cols-[1fr_28px_210px]"
      aria-label="Start planning a trip"
    >
      <div className="p-6 sm:p-7">
        <div className="flex items-center justify-between text-xs font-medium text-mist">
          <span>Boarding pass</span>
          <span className="flex items-center gap-1.5">
            <Plane size={14} /> Voyager agent
          </span>
        </div>
        <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-end gap-3">
          <label className="min-w-0">
            <span className="mb-2 block text-sm text-slate">From</span>
            <select className={select} value={form.origin} onChange={(e) => set("origin", e.target.value)}>
              {cities.length === 0 && <option>{form.origin}</option>}
              {cities.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => setForm((f) => ({ ...f, origin: f.destination, destination: f.origin }))}
            className="mb-1 grid h-9 w-9 place-items-center rounded-full border border-line text-slate transition hover:rotate-180 hover:border-sky hover:text-sky"
            aria-label="Swap cities"
          >
            <ArrowLeftRight size={16} />
          </button>
          <label className="min-w-0 text-right">
            <span className="mb-2 block text-sm text-slate">To</span>
            <select
              className={`${select} text-right`}
              dir="rtl"
              value={form.destination}
              onChange={(e) => set("destination", e.target.value)}
            >
              {cities.length === 0 && <option>{form.destination}</option>}
              {cities.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
        <svg viewBox="0 0 400 40" className="mt-3 h-8 w-full" aria-hidden="true">
          <path d="M8 32 Q200 -8 392 32" fill="none" stroke="#e3e7ec" strokeWidth="2" />
          <path d="M8 32 Q200 -8 392 32" fill="none" stroke="#4AA3E8" strokeWidth="2" className="route-dash" />
          <circle cx="8" cy="32" r="4" fill="#0E2240" />
          <circle cx="392" cy="32" r="4" fill="#0F9C8F" />
        </svg>
        <p className={`mt-1 flex items-center gap-1.5 text-sm ${direct ? "text-lagoon" : "text-[#9a6210]"}`}>
          {meta &&
            (direct ? (
              <>
                <Check size={15} /> Direct flights in the dataset
              </>
            ) : (
              <>No direct flight in the dataset for this pair. The agent will plan without one.</>
            ))}
        </p>
      </div>

      <div className="perforation ticket-notch relative hidden md:block" style={{ "--notch-bg": "transparent" }} />

      <div className="flex flex-col gap-4 border-t border-dashed border-line p-6 sm:p-7 md:border-t-0">
        <label>
          <span className="mb-1 flex items-center gap-1.5 text-sm text-slate">
            <CalendarDays size={14} /> Depart
          </span>
          <input
            type="date"
            min={today}
            value={form.departure_date}
            onChange={(e) => {
              const dep = e.target.value;
              setForm((f) => ({
                ...f,
                departure_date: dep,
                return_date: daysBetween(dep, f.return_date) < 2 ? addDays(dep, 3) : f.return_date,
              }));
            }}
            className="w-full rounded-lg border border-line px-3 py-2 font-medium"
            required
          />
        </label>
        <label>
          <span className="mb-1 flex items-center gap-1.5 text-sm text-slate">
            <CalendarDays size={14} /> Return
          </span>
          <input
            type="date"
            min={addDays(form.departure_date, 2)}
            max={addDays(form.departure_date, 6)}
            value={form.return_date}
            onChange={(e) => set("return_date", e.target.value)}
            className="w-full rounded-lg border border-line px-3 py-2 font-medium"
            required
          />
        </label>
        <div>
          <span className="mb-1 flex items-center gap-1.5 text-sm text-slate">
            <Users size={14} /> Travellers
          </span>
          <div className="flex items-center justify-between rounded-lg border border-line px-2 py-1">
            <button
              type="button"
              className="grid h-8 w-8 place-items-center rounded-md hover:bg-cloud"
              onClick={() => set("travelers", Math.max(1, form.travelers - 1))}
              aria-label="Fewer travellers"
            >
              <Minus size={16} />
            </button>
            <span className="font-semibold" aria-live="polite">{form.travelers}</span>
            <button
              type="button"
              className="grid h-8 w-8 place-items-center rounded-md hover:bg-cloud"
              onClick={() => set("travelers", Math.min(10, form.travelers + 1))}
              aria-label="More travellers"
            >
              <Plus size={16} />
            </button>
          </div>
        </div>
        <Button type="submit" variant="accent" className="mt-1 w-full">
          Start planning
        </Button>
      </div>
    </form>
  );
}
