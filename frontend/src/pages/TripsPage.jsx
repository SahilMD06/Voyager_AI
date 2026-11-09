import { CalendarDays, MapPin } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/ui/Button.jsx";
import { useTrip } from "../hooks/useTrip.jsx";
import { dateFull, inr } from "../utils/format";

export default function TripsPage() {
  const { plans } = useTrip();
  const navigate = useNavigate();
  const list = Object.values(plans).sort((a, b) => (b.generated_at > a.generated_at ? 1 : -1));
  return (
    <div className="mx-auto max-w-5xl px-5 pt-28 lg:px-8">
      <h1 className="text-4xl">My trips</h1>
      <p className="mt-2 text-slate">
        {list.length ? `${list.length} plan${list.length === 1 ? "" : "s"} saved in this browser (up to 8).` : "Plans you create are saved in this browser."}
      </p>
      {list.length === 0 ? (
        <div className="mt-10 rounded-[22px] border border-dashed border-line bg-white p-10 text-center">
          <MapPin className="mx-auto text-sky" size={32} />
          <p className="mt-3 text-lg font-medium">No trips yet</p>
          <p className="mt-1 text-slate">Plan your first trip and it will appear here.</p>
          <Button className="mt-6" onClick={() => navigate("/plan")}>Plan a trip</Button>
        </div>
      ) : (
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {list.map((p) => (
            <li key={p.plan_id}>
              <Link to={`/trip/${p.plan_id}`} className="block overflow-hidden rounded-[20px] border border-line bg-white shadow-lift transition hover:-translate-y-0.5 hover:shadow-float">
                <div className="relative h-32 bg-ink">
                  {p.destination.image_url && <img src={p.destination.image_url} alt="" className="h-full w-full object-cover opacity-70" />}
                  <span className="absolute bottom-3 left-4 font-display text-2xl font-semibold text-white">{p.destination.city}</span>
                </div>
                <div className="p-5">
                  <p className="font-semibold">{p.trip_title}</p>
                  <p className="mt-1 flex items-center gap-1.5 text-sm text-slate"><CalendarDays size={14} /> {dateFull(p.request.departure_date)} to {dateFull(p.request.return_date)}</p>
                  <p className="mt-2 text-sm">From {p.request.origin}, {p.request.travelers} traveller(s), est. <span className="font-semibold">{inr(p.budget.grand_total)}</span></p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
