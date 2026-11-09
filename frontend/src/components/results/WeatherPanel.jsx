import { motion } from "framer-motion";
import { Droplets } from "lucide-react";
import { dateLong } from "../../utils/format";
import SectionHeading from "../ui/SectionHeading.jsx";
import SourceBadge from "../ui/SourceBadge.jsx";
import WeatherIcon from "../ui/WeatherIcon.jsx";

export default function WeatherPanel({ plan }) {
  const weather = plan.weather;
  if (!weather) return null;
  return (
    <section>
      <SectionHeading id="weather" title="Weather" intro={`Open-Meteo data for ${weather.resolved_location || weather.city}.`} />
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
        {weather.days.map((d, i) => (
          <motion.li
            key={d.date}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.05 }}
            className="flex flex-col rounded-[18px] border border-line bg-white p-4"
          >
            <p className="text-sm font-medium text-slate">{dateLong(d.date)}</p>
            <WeatherIcon icon={d.icon} size={34} className="my-3" />
            <p className="font-medium leading-tight">{d.condition}</p>
            {d.source !== "unavailable" ? (
              <>
                <p className="mt-2 font-display text-2xl font-semibold">
                  {Math.round(d.temp_max_c)}°<span className="text-base font-medium text-mist"> / {Math.round(d.temp_min_c)}°</span>
                </p>
                <p className="mt-1 flex items-center gap-1 text-sm text-slate">
                  <Droplets size={14} className="text-sky" />
                  {d.precipitation_probability != null ? `${d.precipitation_probability}% chance` : `${d.precipitation_mm ?? 0} mm recorded`}
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-slate">{d.source_note}</p>
            )}
            <SourceBadge kind={d.source} className="mt-3 self-start" />
          </motion.li>
        ))}
      </ul>
      {weather.note && <p className="mt-3 text-sm text-slate">{weather.note}</p>}
    </section>
  );
}
