import { motion } from "framer-motion";
import {
  AlertCircle, ArrowLeftRight, BedDouble, Check, Gauge, Minus, Plane, Plus, Sparkles, Wand2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import Button from "../components/ui/Button.jsx";
import Skeleton from "../components/ui/Skeleton.jsx";
import { useTrip } from "../hooks/useTrip.jsx";
import { api } from "../services/api";
import { addDays, daysBetween, inr, isoDate, titleCase } from "../utils/format";

const INTEREST_LABELS = {
  adventure: "Adventure", beaches: "Beaches", historical: "Historical places", nature: "Nature",
  food: "Food", shopping: "Shopping", culture: "Culture", spiritual: "Spiritual",
};
const STAY_LABELS = {
  any: ["Best match", "Any type"], budget: ["Budget", "Up to 3 stars"],
  "mid-range": ["Mid-range", "3 to 4 stars"], luxury: ["Luxury", "5 stars"], resort: ["Resort", "Resort properties"],
};
const FLIGHT_LABELS = {
  cheapest: ["Cheapest", "Lowest fare wins"], fastest: ["Fastest", "Shortest flight time"],
  balanced: ["Balanced", "Weighs fare and time"],
};

function defaults() {
  const today = isoDate(new Date());
  return {
    origin: "Bangalore",
    destination: "Goa",
    departure_date: addDays(today, 7),
    return_date: addDays(today, 10),
    travelers: 2,
    budget: 45000,
    accommodation_type: "any",
    interests: ["beaches", "historical"],
    flight_preference: "balanced",
    preferred_amenities: [],
    notes: "",
  };
}

function validate(form) {
  const errors = {};
  const today = isoDate(new Date());
  if (!form.origin) errors.origin = "Choose where you're leaving from.";
  if (!form.destination) errors.destination = "Choose where you're going.";
  if (form.origin && form.origin === form.destination) errors.destination = "Pick a different city from your origin.";
  if (!form.departure_date) errors.departure_date = "Pick a departure date.";
  else if (form.departure_date < today) errors.departure_date = "Departure can't be in the past.";
  if (!form.return_date) errors.return_date = "Pick a return date.";
  else if (form.departure_date) {
    const days = daysBetween(form.departure_date, form.return_date) + 1;
    if (days < 3 || days > 7) errors.return_date = `Trips can be 3 to 7 days. This one is ${days} day${days === 1 ? "" : "s"}.`;
  }
  if (!(form.travelers >= 1 && form.travelers <= 10)) errors.travelers = "Between 1 and 10 travellers.";
  if (!(Number(form.budget) >= 1000)) errors.budget = "Enter a total budget of at least ₹1,000.";
  return errors;
}

function Field({ label, error, hint, children, htmlFor }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>
      {children}
      {error ? (
        <p className="mt-1.5 flex items-center gap-1 text-sm text-alert" role="alert">
          <AlertCircle size={14} /> {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-sm text-mist">{hint}</p>
      ) : null}
    </div>
  );
}

function Segmented({ options, value, onChange, name }) {
  return (
    <div role="radiogroup" aria-label={name} className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {Object.entries(options).map(([key, [title, sub]]) => {
        const active = value === key;
        return (
          <button
            type="button"
            role="radio"
            aria-checked={active}
            key={key}
            onClick={() => onChange(key)}
            className={`rounded-xl border px-3.5 py-3 text-left transition ${
              active ? "border-ink bg-ink text-white" : "border-line bg-white hover:border-slate/40"
            }`}
          >
            <span className="block text-[15px] font-semibold">{title}</span>
            <span className={`block text-xs ${active ? "text-white/70" : "text-mist"}`}>{sub}</span>
          </button>
        );
      })}
    </div>
  );
}

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition ${
        active ? "border-lagoon bg-lagoon-soft text-[#0a6b62]" : "border-line bg-white text-slate hover:border-slate/40"
      }`}
    >
      {active && <Check size={14} />} {children}
    </button>
  );
}

export default function PlannerPage() {
  const { meta, metaError, reloadMeta, draft, startPlanning } = useTrip();
  const navigate = useNavigate();
  const [form, setForm] = useState(() => ({ ...defaults(), ...(draft || {}) }));
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState(false);
  const [query, setQuery] = useState("");
  const [parsing, setParsing] = useState(false);
  const [missing, setMissing] = useState([]);

  useEffect(() => {
    if (touched) setErrors(validate(form));
  }, [form, touched]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const toggle = (key, value) =>
    setForm((f) => ({
      ...f,
      [key]: f[key].includes(value) ? f[key].filter((v) => v !== value) : [...f[key], value],
    }));

  const nights = form.departure_date && form.return_date ? daysBetween(form.departure_date, form.return_date) : 0;
  const rooms = Math.ceil((form.travelers || 1) / 2);
  const direct = meta?.routes?.[form.origin]?.includes(form.destination);
  const back = meta?.routes?.[form.destination]?.includes(form.origin);
  const perPersonPerDay = nights > 0 ? Number(form.budget) / form.travelers / (nights + 1) : 0;
  const reachable = useMemo(() => meta?.routes?.[form.origin] || [], [meta, form.origin]);

  const parse = async () => {
    if (query.trim().length < 5) return toast.error("Describe your trip in a sentence first.");
    setParsing(true);
    try {
      const parsed = await api.parseQuery(query);
      const filled = Object.fromEntries(
        Object.entries(parsed).filter(
          ([k, v]) => !["missing_fields", "clarifying_question"].includes(k) && v != null && !(Array.isArray(v) && v.length === 0),
        ),
      );
      setForm((f) => ({ ...f, ...filled }));
      setMissing(parsed.missing_fields || []);
      if (parsed.missing_fields?.length) toast.info(parsed.clarifying_question || "A few details are still missing.");
      else toast.success("Form filled from your description. Review it and start planning.");
    } catch (e) {
      toast.error(e.status === 503 ? "Describing your trip needs the AI model. Add an LLM API key to backend/.env." : e.message);
    } finally {
      setParsing(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    setTouched(true);
    const errs = validate(form);
    setErrors(errs);
    if (Object.keys(errs).length) {
      toast.error("Fix the highlighted fields to continue.");
      document.getElementById(`field-${Object.keys(errs)[0]}`)?.focus();
      return;
    }
    const request = {
      ...form,
      travelers: Number(form.travelers),
      budget: Math.round(Number(form.budget)),
      notes: form.notes?.trim() || null,
    };
    startPlanning(request);
    navigate("/planning");
  };

  const inputCls = (key) =>
    `h-12 w-full rounded-xl border bg-white px-3.5 text-[15px] transition focus:border-sky focus:outline-none ${
      errors[key] ? "border-alert" : missing.includes(key) ? "border-marigold bg-marigold-soft/40" : "border-line"
    }`;

  if (metaError)
    return (
      <div className="mx-auto max-w-xl px-5 pt-36 text-center">
        <AlertCircle className="mx-auto text-alert" size={40} />
        <h1 className="mt-4 text-2xl">The planning server isn't responding</h1>
        <p className="mt-2 text-slate">{metaError}</p>
        <Button className="mt-6" onClick={reloadMeta}>Try again</Button>
      </div>
    );

  return (
    <div className="mx-auto max-w-7xl px-5 pt-28 lg:px-8">
      <h1 className="text-4xl md:text-5xl">Plan your trip</h1>
      <p className="mt-2 max-w-2xl text-slate">
        Fill in the details, or describe the trip in your own words and let the AI fill the form.
      </p>

      <div className="mt-8 rounded-[22px] bg-ink p-5 text-white sm:p-6">
        <label htmlFor="nl-query" className="flex items-center gap-2 font-medium">
          <Sparkles size={18} className="text-sky" /> Describe your trip
        </label>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
          <input
            id="nl-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), parse())}
            placeholder="e.g. 4 days in Goa from Bangalore next Friday for 2 people, beaches and forts, under 45k"
            className="h-12 flex-1 rounded-xl border border-white/15 bg-white/10 px-4 text-white placeholder:text-white/50 focus:border-sky focus:outline-none"
          />
          <Button type="button" variant="light" onClick={parse} loading={parsing} icon={Wand2}>
            Fill the form
          </Button>
        </div>
        {meta && !meta.llm.configured && (
          <p className="mt-2 text-sm text-white/60">Needs an LLM API key in backend/.env. The form below works without it.</p>
        )}
        {missing.length > 0 && (
          <p className="mt-2 text-sm text-marigold">Still needed: {missing.map((m) => m.replace("_", " ")).join(", ")}</p>
        )}
      </div>

      <form onSubmit={submit} noValidate className="mt-8 grid gap-8 lg:grid-cols-[1fr_340px]">
        <div className="space-y-8">
          <section className="rounded-[22px] border border-line bg-white p-5 sm:p-7">
            <h2 className="text-xl">Route and dates</h2>
            {!meta ? (
              <div className="mt-5 grid gap-4 sm:grid-cols-2"><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
            ) : (
              <div className="mt-5 grid gap-5 sm:grid-cols-[1fr_auto_1fr]">
                <Field label="Starting city" error={errors.origin} htmlFor="field-origin">
                  <select id="field-origin" className={inputCls("origin")} value={form.origin} onChange={(e) => set("origin", e.target.value)}>
                    <option value="">Select a city</option>
                    {meta.cities.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </Field>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, origin: f.destination, destination: f.origin }))}
                  className="mt-7 hidden h-12 w-12 place-items-center rounded-xl border border-line text-slate hover:text-sky sm:grid"
                  aria-label="Swap starting city and destination"
                >
                  <ArrowLeftRight size={18} />
                </button>
                <Field
                  label="Destination city"
                  error={errors.destination}
                  htmlFor="field-destination"
                  hint={reachable.length ? `Direct flights from ${form.origin}: ${reachable.join(", ")}` : undefined}
                >
                  <select id="field-destination" className={inputCls("destination")} value={form.destination} onChange={(e) => set("destination", e.target.value)}>
                    <option value="">Select a city</option>
                    {meta.cities.map((c) => (
                      <option key={c} value={c}>{c}{reachable.includes(c) ? "  (direct flight)" : ""}</option>
                    ))}
                  </select>
                </Field>
              </div>
            )}
            <div className="mt-5 grid gap-5 sm:grid-cols-3">
              <Field label="Departure date" error={errors.departure_date} htmlFor="field-departure_date">
                <input id="field-departure_date" type="date" min={isoDate(new Date())} className={inputCls("departure_date")} value={form.departure_date || ""} onChange={(e) => set("departure_date", e.target.value)} />
              </Field>
              <Field label="Return date" error={errors.return_date} hint={nights > 0 ? `${nights + 1} days, ${nights} nights` : undefined} htmlFor="field-return_date">
                <input id="field-return_date" type="date" min={form.departure_date ? addDays(form.departure_date, 2) : undefined} max={form.departure_date ? addDays(form.departure_date, 6) : undefined} className={inputCls("return_date")} value={form.return_date || ""} onChange={(e) => set("return_date", e.target.value)} />
              </Field>
              <Field label="Travellers" error={errors.travelers} htmlFor="field-travelers">
                <div className={`flex h-12 items-center justify-between rounded-xl border px-2 ${errors.travelers ? "border-alert" : "border-line"} bg-white`}>
                  <button type="button" aria-label="Fewer travellers" className="grid h-9 w-9 place-items-center rounded-lg hover:bg-cloud" onClick={() => set("travelers", Math.max(1, form.travelers - 1))}><Minus size={16} /></button>
                  <input id="field-travelers" type="number" min={1} max={10} value={form.travelers} onChange={(e) => set("travelers", Number(e.target.value))} className="w-12 bg-transparent text-center font-semibold outline-none" />
                  <button type="button" aria-label="More travellers" className="grid h-9 w-9 place-items-center rounded-lg hover:bg-cloud" onClick={() => set("travelers", Math.min(10, form.travelers + 1))}><Plus size={16} /></button>
                </div>
              </Field>
            </div>
          </section>

          <section className="rounded-[22px] border border-line bg-white p-5 sm:p-7">
            <h2 className="text-xl">Budget</h2>
            <div className="mt-5 grid gap-5 sm:grid-cols-[1fr_auto]">
              <Field label="Total budget for the group (₹)" error={errors.budget} htmlFor="field-budget" hint="Covers flights, hotel, food, local transport and entry fees.">
                <input id="field-budget" type="number" min={1000} step={500} inputMode="numeric" className={inputCls("budget")} value={form.budget} onChange={(e) => set("budget", e.target.value)} />
              </Field>
              <div className="flex flex-wrap items-start gap-2 sm:pt-7">
                {[25000, 45000, 75000, 120000].map((b) => (
                  <Chip key={b} active={Number(form.budget) === b} onClick={() => set("budget", b)}>{inr(b)}</Chip>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-[22px] border border-line bg-white p-5 sm:p-7">
            <h2 className="flex items-center gap-2 text-xl"><BedDouble size={20} /> Where you'll stay</h2>
            <div className="mt-5">
              <Segmented name="Accommodation type" options={STAY_LABELS} value={form.accommodation_type} onChange={(v) => set("accommodation_type", v)} />
            </div>
            <p className="mb-2 mt-6 text-sm font-medium">Must-have amenities</p>
            <div className="flex flex-wrap gap-2">
              {(meta?.amenities || []).map((a) => (
                <Chip key={a} active={form.preferred_amenities.includes(a)} onClick={() => toggle("preferred_amenities", a)}>{titleCase(a)}</Chip>
              ))}
            </div>
          </section>

          <section className="rounded-[22px] border border-line bg-white p-5 sm:p-7">
            <h2 className="text-xl">What you enjoy</h2>
            <div className="mt-5 flex flex-wrap gap-2">
              {Object.entries(INTEREST_LABELS).map(([k, label]) => (
                <Chip key={k} active={form.interests.includes(k)} onClick={() => toggle("interests", k)}>{label}</Chip>
              ))}
            </div>
            <h2 className="mt-8 flex items-center gap-2 text-xl"><Plane size={20} /> Flight preference</h2>
            <div className="mt-5">
              <Segmented name="Flight preference" options={FLIGHT_LABELS} value={form.flight_preference} onChange={(v) => set("flight_preference", v)} />
            </div>
            <div className="mt-8">
              <Field label="Anything else the agent should know?" htmlFor="field-notes" hint="Optional. e.g. travelling with grandparents, prefer relaxed mornings.">
                <textarea id="field-notes" rows={3} maxLength={600} className="w-full rounded-xl border border-line bg-white p-3.5 text-[15px] focus:border-sky focus:outline-none" value={form.notes || ""} onChange={(e) => set("notes", e.target.value)} />
              </Field>
            </div>
          </section>
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <motion.div layout className="rounded-[22px] border border-line bg-white p-6 shadow-lift">
            <h2 className="text-lg">Trip at a glance</h2>
            <p className="mt-3 font-display text-2xl font-semibold">
              {form.origin || "?"} <span className="text-mist">to</span> {form.destination || "?"}
            </p>
            <dl className="mt-5 space-y-3 text-[15px]">
              <div className="flex justify-between"><dt className="text-slate">Length</dt><dd className="font-medium">{nights > 0 ? `${nights + 1} days` : "—"}</dd></div>
              <div className="flex justify-between"><dt className="text-slate">Rooms needed</dt><dd className="font-medium">{rooms}</dd></div>
              <div className="flex justify-between"><dt className="text-slate">Budget per person per day</dt><dd className="font-medium">{perPersonPerDay ? inr(perPersonPerDay) : "—"}</dd></div>
            </dl>
            {meta && form.origin && form.destination && form.origin !== form.destination && (
              <div className={`mt-5 rounded-xl p-3 text-sm ${direct && back ? "bg-lagoon-soft text-[#0a6b62]" : "bg-marigold-soft text-[#8a5a12]"}`}>
                <p className="flex items-center gap-1.5 font-medium"><Gauge size={15} /> Flight data for this route</p>
                <p className="mt-1">
                  Outbound: {direct ? "direct flights available" : "none in dataset"}. Return: {back ? "direct flights available" : "none in dataset"}.
                </p>
              </div>
            )}
            <Button type="submit" variant="accent" size="lg" className="mt-6 w-full" icon={Sparkles}>
              Plan my trip
            </Button>
            <p className="mt-3 text-center text-xs text-mist">
              {meta?.llm?.configured ? `The ${meta.llm.model} agent will plan this trip.` : "No LLM key set: the rule-based planner will run instead."}
            </p>
          </motion.div>
        </aside>
      </form>
    </div>
  );
}
