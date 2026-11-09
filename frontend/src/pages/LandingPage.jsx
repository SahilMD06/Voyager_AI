import { motion, useReducedMotion } from "framer-motion";
import {
  BedDouble, BrainCircuit, CloudSun, MapPinned, Plane, Wallet,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import SearchTicket from "../components/SearchTicket.jsx";
import Button from "../components/ui/Button.jsx";
import Skeleton from "../components/ui/Skeleton.jsx";
import { useTrip } from "../hooks/useTrip.jsx";
import { inr } from "../utils/format";

const tools = [
  {
    icon: Plane,
    name: "Flight search",
    text: "Filters flights.json by route, compares fares and durations, and flags the cheapest and fastest options.",
  },
  {
    icon: BedDouble,
    name: "Hotel recommendations",
    text: "Ranks hotels by stars, nightly price, amenities and the stay type you asked for, within your nightly cap.",
  },
  {
    icon: MapPinned,
    name: "Places discovery",
    text: "Matches attractions from places.json to your interests and ratings, without repeating a stop.",
  },
  {
    icon: CloudSun,
    name: "Live weather",
    text: "Pulls Open-Meteo forecasts for your dates, and shows last year's recorded weather when dates are too far out.",
  },
  {
    icon: Wallet,
    name: "Budget estimate",
    text: "Adds real dataset fares and room rates to clearly labelled estimates for food, transport and entry fees.",
  },
];

const steps = [
  ["Read your request", "The agent works out nights, rooms, a nightly cap and what it still needs to find."],
  ["Choose its tools", "It decides which of the five tools to call, in what order, and calls some in parallel."],
  ["Compare results", "Fares, star ratings, attraction scores and weather are weighed against your preferences."],
  ["Check the budget", "If the plan runs over, it swaps in cheaper options and estimates again."],
  ["Explain the plan", "Every choice comes back with the figures behind it, validated against the data."],
];

function HeroBackdrop({ image }) {
  return (
    <div className="absolute inset-0 -z-10 overflow-hidden bg-ink">
      {image && (
        <motion.img
          src={image}
          alt=""
          className="h-full w-full object-cover"
          initial={{ scale: 1.08, opacity: 0 }}
          animate={{ scale: 1, opacity: 0.55 }}
          transition={{ duration: 1.6, ease: "easeOut" }}
        />
      )}
      <div className="absolute inset-0 bg-[linear-gradient(100deg,#0E2240_10%,rgba(14,34,64,0.82)_45%,rgba(14,34,64,0.35))]" />
    </div>
  );
}

function DestinationCard({ card, index, onPlan }) {
  return (
    <motion.button
      type="button"
      onClick={() => onPlan(card.city)}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ delay: (index % 4) * 0.07, duration: 0.45 }}
      className="group relative flex aspect-[4/3] sm:aspect-[4/5] flex-col justify-end overflow-hidden rounded-[20px] bg-ink text-left text-white shadow-lift transition-shadow hover:shadow-float"
      aria-label={`Plan a trip to ${card.city}`}
    >
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={`${card.city}`}
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
      ) : (
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,#4AA3E8,#0E2240_70%)]" />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-ink via-ink/40 to-transparent" />
      <div className="relative p-5">
        <h3 className="text-2xl">{card.city}</h3>
        {card.description && <p className="mt-0.5 line-clamp-1 text-sm text-white/75">{card.description}</p>}
        <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div>
            <dt className="text-white/60">Hotels from</dt>
            <dd className="font-semibold">{inr(card.min_hotel_price)}</dd>
          </div>
          <div>
            <dt className="text-white/60">Attractions</dt>
            <dd className="font-semibold">{card.places} in dataset</dd>
          </div>
        </dl>
      </div>
    </motion.button>
  );
}

export default function LandingPage() {
  const { destinations, setDraft, meta } = useTrip();
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const heroImage = destinations?.find((d) => d.city === "Goa")?.image_url || destinations?.find((d) => d.image_url)?.image_url;

  const planTo = (city) => {
    setDraft((d) => {
      const current = d?.origin || "Bangalore";
      // Avoid "Bangalore to Bangalore": prefer a city with a direct flight in.
      const withFlight = Object.entries(meta?.routes || {}).find(([, dests]) => dests.includes(city))?.[0];
      const origin = current !== city ? current : withFlight || (meta?.cities || []).find((c) => c !== city);
      return { ...(d || {}), origin, destination: city };
    });
    navigate("/plan");
  };

  const rise = (delay) => ({
    initial: { opacity: 0, y: reduce ? 0 : 28 },
    animate: { opacity: 1, y: 0 },
    transition: { delay, duration: 0.7, ease: [0.2, 0.7, 0.2, 1] },
  });

  return (
    <>
      <section className="relative isolate min-h-[92vh] pt-28 pb-20 text-white">
        <HeroBackdrop image={heroImage} />
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 lg:grid-cols-[0.95fr_1.1fr] lg:px-8">
          <div>
            <motion.h1 {...rise(0.05)} className="max-w-xl text-[44px] font-bold sm:text-6xl lg:text-[68px]">
              Your next journey, planned by AI.
            </motion.h1>
            <motion.p {...rise(0.2)} className="mt-6 max-w-lg text-lg text-white/80">
              Tell Voyager where and when. Its agent searches real flights, hotels and attractions,
              checks the live forecast, then hands you a day-by-day plan with a budget and the
              reasons behind every pick.
            </motion.p>
            <motion.div {...rise(0.32)} className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" variant="light" onClick={() => navigate("/plan")}>
                Start planning
              </Button>
              <Button as="a" href="#how-it-works" size="lg" variant="ghost" className="text-white hover:bg-white/10">
                See how the agent works
              </Button>
            </motion.div>
            {meta && (
              <motion.p {...rise(0.45)} className="mt-10 text-sm text-white/60">
                Searching {meta.dataset.flights} flights, {meta.dataset.hotels} hotels and{" "}
                {meta.dataset.places} attractions across {meta.cities.length} Indian cities.
              </motion.p>
            )}
          </div>
          <motion.div
            initial={{ opacity: 0, y: reduce ? 0 : 40, rotate: reduce ? 0 : -1.5 }}
            animate={{ opacity: 1, y: 0, rotate: 0 }}
            transition={{ delay: 0.35, duration: 0.9, ease: [0.2, 0.7, 0.2, 1] }}
          >
            <SearchTicket />
          </motion.div>
        </div>
      </section>

      <section id="destinations" className="mx-auto max-w-7xl scroll-mt-20 px-5 pt-20 lg:px-8">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-xl">
            <h2 className="text-3xl md:text-4xl">Where the agent can take you</h2>
            <p className="mt-2 text-slate">
              Every city here has hotels and attractions in the dataset. Pick one to start a plan.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {destinations === null
            ? Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="aspect-[4/3] sm:aspect-[4/5]" />)
            : destinations.map((card, i) => (
                <DestinationCard key={card.city} card={card} index={i} onPlan={planTo} />
              ))}
        </div>
        {destinations?.length === 0 && (
          <p className="rounded-xl bg-alert-soft p-4 text-alert">
            Destinations couldn't load. Check that the backend is running on port 8000.
          </p>
        )}
        {destinations?.some((d) => d.image_url) && (
          <p className="mt-3 text-xs text-mist">Photos: Wikimedia Commons via Wikipedia.</p>
        )}
      </section>

      <section id="features" className="mx-auto mt-28 max-w-7xl scroll-mt-20 px-5 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <BrainCircuit className="text-lagoon" size={36} />
            <h2 className="mt-4 text-3xl md:text-4xl">One agent, five tools</h2>
            <p className="mt-3 max-w-md text-slate">
              Voyager runs a LangChain tool-calling agent. The language model decides which tools
              to use and when. Each tool reads real data and nothing in your plan is made up: if the
              data has no flight, the plan says so.
            </p>
          </div>
          <ul className="divide-y divide-line rounded-[22px] border border-line bg-white">
            {tools.map(({ icon: Icon, name, text }) => (
              <li key={name} className="flex gap-5 p-6">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-sky-soft text-ink">
                  <Icon size={22} />
                </span>
                <div>
                  <h3 className="text-lg">{name}</h3>
                  <p className="mt-1 text-slate">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="how-it-works" className="mt-28 scroll-mt-20 bg-ink py-20 text-white">
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <h2 className="max-w-lg text-3xl md:text-4xl">How a plan comes together</h2>
          <p className="mt-3 max-w-xl text-white/70">
            You'll watch these steps happen live while the agent works.
          </p>
          <ol className="mt-12 grid gap-8 md:grid-cols-5">
            {steps.map(([title, text], i) => (
              <li key={title} className="relative">
                <span className="font-display text-5xl font-bold text-sky/70">{i + 1}</span>
                <h3 className="mt-3 text-lg">{title}</h3>
                <p className="mt-1.5 text-sm text-white/70">{text}</p>
              </li>
            ))}
          </ol>
          <Button className="mt-12" variant="light" size="lg" onClick={() => navigate("/plan")}>
            Plan my trip
          </Button>
        </div>
      </section>
    </>
  );
}
