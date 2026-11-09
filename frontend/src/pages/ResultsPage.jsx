import { motion } from "framer-motion";
import { AlertTriangle, Bot, Braces, CalendarDays, Download, Pencil, RefreshCw, Users, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import AgentTrace from "../components/results/AgentTrace.jsx";
import BudgetPanel from "../components/results/BudgetPanel.jsx";
import DecisionPanel from "../components/results/DecisionPanel.jsx";
import FlightSection from "../components/results/FlightSection.jsx";
import HotelSection from "../components/results/HotelSection.jsx";
import ItineraryTimeline from "../components/results/ItineraryTimeline.jsx";
import TravelMap from "../components/results/TravelMap.jsx";
import WeatherPanel from "../components/results/WeatherPanel.jsx";
import Button from "../components/ui/Button.jsx";
import { useTrip } from "../hooks/useTrip.jsx";
import { dateFull, inr, titleCase } from "../utils/format";

const NAV = [
  ["flights", "Flights"], ["stay", "Stay"], ["itinerary", "Itinerary"], ["map", "Map"],
  ["weather", "Weather"], ["budget", "Budget"], ["why", "Why this plan"], ["trace", "Agent trace"],
];

function SectionNav() {
  const [active, setActive] = useState("flights");
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: "-30% 0px -60% 0px" },
    );
    NAV.forEach(([id]) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);
  return (
    <div className="no-print sticky top-16 z-30 -mx-5 border-b border-line bg-paper/90 px-5 backdrop-blur lg:-mx-8 lg:px-8">
      <nav className="flex gap-1 overflow-x-auto py-2.5" aria-label="Plan sections">
        {NAV.map(([id, label]) => (
          <a
            key={id}
            href={`#${id}`}
            className={`relative shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${active === id ? "text-white" : "text-slate hover:text-ink"}`}
          >
            {active === id && <motion.span layoutId="section-pill" className="absolute inset-0 rounded-full bg-ink" transition={{ type: "spring", stiffness: 400, damping: 34 }} />}
            <span className="relative">{label}</span>
          </a>
        ))}
      </nav>
    </div>
  );
}

export default function ResultsPage() {
  const { planId } = useParams();
  const { plans, startPlanning, setDraft } = useTrip();
  const navigate = useNavigate();
  const plan = plans[planId];

  if (!plan)
    return (
      <div className="mx-auto max-w-xl px-5 pt-36 text-center">
        <h1 className="text-3xl">This plan isn't saved on this device</h1>
        <p className="mt-2 text-slate">Plans are stored in your browser. Start a new one or open a saved trip.</p>
        <div className="mt-6 flex justify-center gap-3">
          <Button onClick={() => navigate("/plan")}>Plan a trip</Button>
          <Button variant="outline" onClick={() => navigate("/trips")}>My trips</Button>
        </div>
      </div>
    );

  const req = plan.request;
  const regenerate = () => {
    startPlanning(req);
    navigate("/planning");
  };
  const modify = () => {
    setDraft({ ...req, notes: req.notes || "" });
    navigate("/plan");
  };
  const pdf = async () => {
    try {
      const { exportPdf } = await import("../utils/exportPlan");
      exportPdf(plan);
      toast.success("Itinerary PDF downloaded.");
    } catch (e) {
      toast.error(`Couldn't create the PDF: ${e.message}`);
    }
  };
  const json = async () => {
    const { exportJson } = await import("../utils/exportPlan");
    exportJson(plan);
    toast.success("Itinerary JSON downloaded.");
  };

  const facts = [
    { Icon: CalendarDays, label: "Dates", value: `${dateFull(req.departure_date)} to ${dateFull(req.return_date)}`, sub: `${plan.days.length} days, ${plan.budget.nights} nights` },
    { Icon: Users, label: "Travellers", value: `${req.travelers}`, sub: `${plan.hotel?.rooms_needed ?? Math.ceil(req.travelers / 2)} room(s)` },
    { Icon: Wallet, label: "Estimated total", value: inr(plan.budget.grand_total), sub: plan.budget.within_budget ? `Within your ${inr(req.budget)}` : `Over your ${inr(req.budget)}` },
  ];

  return (
    <div>
      <header className="relative isolate overflow-hidden bg-ink pt-28 pb-10 text-white">
        {plan.destination.image_url && (
          <img src={plan.destination.image_url} alt="" className="absolute inset-0 -z-10 h-full w-full object-cover opacity-40" />
        )}
        <div className="absolute inset-0 -z-10 bg-gradient-to-t from-ink via-ink/70 to-ink/30" />
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <p className="flex items-center gap-2 text-sm text-white/75">
              <Bot size={16} className="text-sky" />
              {plan.mode === "agent" ? `Planned by the LangChain agent (${plan.model})` : "Planned by the rule-based fallback (no LLM available)"}
            </p>
            <h1 className="mt-3 max-w-3xl text-4xl md:text-6xl">{plan.trip_title}</h1>
            <p className="mt-4 max-w-2xl text-lg text-white/80">{plan.summary}</p>
          </motion.div>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {facts.map(({ Icon, label, value, sub }) => (
              <div key={label} className="rounded-2xl bg-white/10 p-4 backdrop-blur">
                <p className="flex items-center gap-1.5 text-sm text-white/65"><Icon size={15} /> {label}</p>
                <p className="mt-1 font-display text-xl font-semibold">{value}</p>
                <p className="text-sm text-white/65">{sub}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-white/65">
            {req.origin} to {plan.destination.city}. Flights: {req.flight_preference}. Stay: {req.accommodation_type === "any" ? "best match" : req.accommodation_type}.
            {req.interests.length > 0 && ` Interests: ${req.interests.map(titleCase).join(", ")}.`}
          </p>
          <div className="no-print mt-7 flex flex-wrap gap-3">
            <Button variant="light" icon={RefreshCw} onClick={regenerate}>Regenerate</Button>
            <Button variant="ghost" icon={Pencil} className="text-white hover:bg-white/10" onClick={modify}>Modify trip</Button>
            <Button variant="ghost" icon={Download} className="text-white hover:bg-white/10" onClick={pdf}>Download PDF</Button>
            <Button variant="ghost" icon={Braces} className="text-white hover:bg-white/10" onClick={json}>Export JSON</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 lg:px-8">
        <SectionNav />
        {plan.warnings.length > 0 && (
          <div className="mt-8 rounded-2xl border border-marigold/40 bg-marigold-soft/60 p-5" role="note">
            <p className="flex items-center gap-2 font-semibold text-[#8a5a12]"><AlertTriangle size={18} /> Good to know before you book</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/80">
              {plan.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}
        <div className="mt-12 space-y-20">
          <FlightSection plan={plan} />
          <HotelSection plan={plan} />
          <ItineraryTimeline plan={plan} />
          <TravelMap plan={plan} />
          <WeatherPanel plan={plan} />
          <BudgetPanel plan={plan} />
          <DecisionPanel plan={plan} />
          <AgentTrace plan={plan} />
        </div>
        <p className="mt-12 text-sm text-mist">
          Plan {plan.plan_id}, generated {new Date(plan.generated_at).toLocaleString("en-IN")}. <Link to="/trips" className="underline">See all saved trips</Link>
        </p>
      </div>
    </div>
  );
}
