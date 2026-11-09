import { AnimatePresence, motion } from "framer-motion";
import { Car, Coffee, Dumbbell, Sparkles, Waves, Wifi } from "lucide-react";
import { useMemo, useState } from "react";
import { inr, titleCase } from "../../utils/format";
import SectionHeading from "../ui/SectionHeading.jsx";
import SourceBadge from "../ui/SourceBadge.jsx";
import Stars from "../ui/Stars.jsx";

const AMENITY_ICONS = { wifi: Wifi, pool: Waves, gym: Dumbbell, breakfast: Coffee, parking: Car, spa: Sparkles };

function Amenities({ list }) {
  if (!list?.length) return <p className="text-sm text-mist">No amenities listed in the dataset.</p>;
  return (
    <ul className="flex flex-wrap gap-2">
      {list.map((a) => {
        const Icon = AMENITY_ICONS[a] || Sparkles;
        return (
          <li key={a} className="flex items-center gap-1.5 rounded-full bg-cloud px-3 py-1 text-sm">
            <Icon size={14} className="text-slate" /> {titleCase(a)}
          </li>
        );
      })}
    </ul>
  );
}

// The dataset has no hotel photos, so we draw a designed placeholder rather
// than attaching an unrelated stock image.
function HotelVisual({ hotel, image }) {
  const initials = hotel.name.split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <div className="relative min-h-56 overflow-hidden bg-ink">
      {image && <img src={image} alt="" className="absolute inset-0 h-full w-full object-cover opacity-35" />}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_10%,rgba(74,163,232,0.55),transparent_55%),radial-gradient(circle_at_10%_90%,rgba(15,156,143,0.5),transparent_50%)]" />
      <div className="relative flex h-full flex-col justify-between p-6 text-white">
        <span className="font-display text-6xl font-bold opacity-90">{initials}</span>
        <p className="text-sm text-white/75">{image ? `${hotel.city} (destination photo, not the hotel)` : hotel.city}</p>
      </div>
    </div>
  );
}

export default function HotelSection({ plan }) {
  const [sort, setSort] = useState("score");
  const [compare, setCompare] = useState(false);
  const hotel = plan.hotel;
  const others = useMemo(
    () =>
      [...plan.hotel_options].sort((a, b) =>
        sort === "price" ? a.price_per_night - b.price_per_night : sort === "stars" ? b.stars - a.stars : b.score - a.score,
      ),
    [plan.hotel_options, sort],
  );

  return (
    <section>
      <SectionHeading
        id="stay"
        title="Where you'll stay"
        intro={`${hotel ? hotel.rooms_needed : Math.ceil(plan.request.travelers / 2)} room(s) for ${plan.request.travelers} traveller(s), ${plan.budget.nights} nights.`}
        action={
          plan.hotel_options.length > 1 && (
            <button onClick={() => setCompare((v) => !v)} className="rounded-xl border border-line bg-white px-4 py-2 text-sm font-semibold hover:bg-cloud" aria-expanded={compare}>
              {compare ? "Hide other hotels" : `Compare ${plan.hotel_options.length} hotels`}
            </button>
          )
        }
      />
      {!hotel ? (
        <p className="rounded-2xl bg-marigold-soft p-5">No hotels in {plan.destination.city} in hotels.json.</p>
      ) : (
        <div className="grid overflow-hidden rounded-[22px] border border-line bg-white shadow-lift md:grid-cols-[300px_1fr]">
          <HotelVisual hotel={hotel} image={plan.destination.image_url} />
          <div className="p-6 sm:p-7">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 className="text-2xl">{hotel.name}</h3>
                <div className="mt-1.5 flex items-center gap-2 text-sm text-slate">
                  <Stars count={hotel.stars} /> {titleCase(hotel.tier)} <span className="text-mist">{hotel.hotel_id}</span>
                </div>
              </div>
              <div className="text-right">
                <p className="font-display text-2xl font-semibold">{inr(hotel.price_per_night)}</p>
                <p className="text-sm text-slate">per room per night</p>
                <SourceBadge kind="dataset" className="mt-1.5" />
              </div>
            </div>
            <div className="mt-5"><Amenities list={hotel.amenities} /></div>
            <div className="mt-5 rounded-xl bg-lagoon-soft/60 p-4 text-[15px]">
              <p className="font-medium text-[#0a6b62]">Why the agent recommends it</p>
              <p className="mt-1 text-ink/80">{hotel.reason}</p>
            </div>
            <p className="mt-4 text-sm text-slate">
              Stay total: <span className="font-semibold text-ink">{inr(hotel.total_stay_cost)}</span>
              {!hotel.within_budget && <span className="ml-2 text-alert">Above the nightly cap</span>}
            </p>
          </div>
        </div>
      )}
      <AnimatePresence>
        {compare && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-5 flex justify-end">
              <label className="flex items-center gap-2 text-sm text-slate">
                Sort by
                <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1 text-ink">
                  <option value="score">Agent score</option>
                  <option value="price">Price</option>
                  <option value="stars">Star rating</option>
                </select>
              </label>
            </div>
            <ul className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {others.map((h) => (
                <li key={h.hotel_id} className={`rounded-2xl border bg-white p-5 ${h.hotel_id === hotel?.hotel_id ? "border-lagoon" : "border-line"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{h.name}</p>
                      <Stars count={h.stars} size={12} />
                    </div>
                    <p className="font-semibold">{inr(h.price_per_night)}</p>
                  </div>
                  <p className="mt-3 text-sm text-slate">{h.reason}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {h.hotel_id === hotel?.hotel_id && <span className="rounded-full bg-lagoon px-2.5 py-0.5 text-xs text-white">Selected</span>}
                    {!h.within_budget && <span className="rounded-full bg-alert-soft px-2.5 py-0.5 text-xs text-alert">Over nightly cap</span>}
                    {h.amenities.map((a) => <span key={a} className="rounded-full bg-cloud px-2.5 py-0.5 text-xs">{a}</span>)}
                  </div>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
