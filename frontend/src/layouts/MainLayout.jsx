import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import Logo from "../components/Logo.jsx";
import { useTrip } from "../hooks/useTrip.jsx";

const links = [
  { to: "/", label: "Home", end: true },
  { to: "/plan", label: "Plan a trip" },
  { to: "/trips", label: "My trips" },
];

function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const { meta } = useTrip();
  const onHome = location.pathname === "/";

  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const transparent = onHome && !scrolled && !open;
  return (
    <nav
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        transparent ? "bg-transparent text-white" : "bg-paper/90 text-ink shadow-[0_1px_0_var(--color-line)] backdrop-blur"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
        <Link to="/" aria-label="Voyager AI home">
          <Logo light={transparent} />
        </Link>
        <div className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `relative rounded-full px-4 py-2 text-[15px] font-medium transition-colors ${
                  isActive ? "" : transparent ? "text-white/80 hover:text-white" : "text-slate hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="nav-pill"
                      className={`absolute inset-0 rounded-full ${transparent ? "bg-white/15" : "bg-cloud"}`}
                      transition={{ type: "spring", stiffness: 400, damping: 32 }}
                    />
                  )}
                  <span className="relative">{l.label}</span>
                </>
              )}
            </NavLink>
          ))}
          <span
            className={`ml-3 flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ${
              transparent ? "bg-white/10 text-white/80" : "bg-cloud text-slate"
            }`}
            title={meta?.llm?.configured ? `Agent model: ${meta.llm.model}` : "No LLM key configured"}
          >
            <span className={`h-2 w-2 rounded-full ${meta?.llm?.configured ? "bg-lagoon" : "bg-marigold"}`} />
            {meta ? (meta.llm.configured ? `Agent online (${meta.llm.provider})` : "Agent offline") : "Connecting"}
          </span>
        </div>
        <button
          className="rounded-lg p-2 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-line bg-paper md:hidden"
          >
            <div className="flex flex-col px-5 py-3">
              {links.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.end}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-3 text-base font-medium ${isActive ? "bg-cloud text-ink" : "text-slate"}`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="mt-24 bg-ink text-white/70">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 md:grid-cols-[1.4fr_1fr_1fr_1fr] lg:px-8">
        <div>
          <Logo light />
          <p className="mt-4 max-w-xs text-sm leading-relaxed">
            An autonomous LangChain agent that searches flights, hotels and attractions, checks live
            weather and builds a day-by-day plan you can understand.
          </p>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold text-white">Plan</h4>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-white" to="/plan">New trip</Link></li>
            <li><Link className="hover:text-white" to="/trips">My trips</Link></li>
            <li><a className="hover:text-white" href="/#destinations">Destinations</a></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold text-white">How it works</h4>
          <ul className="space-y-2 text-sm">
            <li><a className="hover:text-white" href="/#how-it-works">Agent workflow</a></li>
            <li><a className="hover:text-white" href="/#features">Agent tools</a></li>
            <li><a className="hover:text-white" href="/api/health" target="_blank" rel="noreferrer">API status</a></li>
          </ul>
        </div>
        <div>
          <h4 className="mb-3 text-sm font-semibold text-white">Data sources</h4>
          <ul className="space-y-2 text-sm">
            <li>flights.json, hotels.json, places.json</li>
            <li><a className="hover:text-white" href="https://open-meteo.com" target="_blank" rel="noreferrer">Open-Meteo weather</a></li>
            <li><a className="hover:text-white" href="https://commons.wikimedia.org" target="_blank" rel="noreferrer">Wikimedia Commons images</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-7xl px-5 py-5 text-xs lg:px-8">
          Voyager AI is a demonstration project. Fares and schedules come from the provided sample
          datasets; confirm with the airline or hotel before booking.
        </p>
      </div>
    </footer>
  );
}

export default function MainLayout() {
  const location = useLocation();
  useEffect(() => {
    if (!location.hash) window.scrollTo({ top: 0 });
  }, [location.pathname, location.hash]);
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <motion.main
        key={location.pathname}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
        className="flex-1"
      >
        <Outlet />
      </motion.main>
      <Footer />
    </div>
  );
}
