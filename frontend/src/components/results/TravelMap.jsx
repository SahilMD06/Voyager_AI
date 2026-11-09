import L from "leaflet";
import { Info } from "lucide-react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { titleCase } from "../../utils/format";
import SectionHeading from "../ui/SectionHeading.jsx";

// Custom SVG pin (avoids Leaflet's default image paths, which break in Vite).
const pin = L.divIcon({
  className: "",
  html: `<svg width="36" height="46" viewBox="0 0 36 46" xmlns="http://www.w3.org/2000/svg"><path d="M18 45s15-15.4 15-27A15 15 0 0 0 3 18c0 11.6 15 27 15 27z" fill="#0E2240"/><circle cx="18" cy="18" r="6.5" fill="#0F9C8F"/></svg>`,
  iconSize: [36, 46],
  iconAnchor: [18, 45],
  popupAnchor: [0, -40],
});

export default function TravelMap({ plan }) {
  const { latitude, longitude, resolved_location, city } = plan.destination;
  const scheduled = plan.days.flatMap((d) =>
    [...d.morning, ...d.afternoon, ...d.evening].filter((a) => a.place).map((a) => ({ ...a.place, day: d.day })),
  );
  return (
    <section>
      <SectionHeading id="map" title="Map" intro={`Pinned at ${resolved_location || city}, located with Open-Meteo geocoding.`} />
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div className="h-[380px] overflow-hidden rounded-[20px] border border-line bg-cloud shadow-lift">
          {latitude != null ? (
            <MapContainer center={[latitude, longitude]} zoom={11} scrollWheelZoom={false} className="h-full w-full">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <Marker position={[latitude, longitude]} icon={pin}>
                <Popup>
                  <strong>{city}</strong>
                  <br />
                  {resolved_location}
                  <br />
                  {scheduled.length} attraction(s) on your itinerary
                </Popup>
              </Marker>
            </MapContainer>
          ) : (
            <div className="grid h-full place-items-center p-6 text-center text-slate">
              The destination couldn't be geocoded, so no map is shown.
            </div>
          )}
        </div>
        <div className="rounded-[20px] border border-line bg-white p-5">
          <p className="flex items-start gap-2 rounded-xl bg-sky-soft/60 p-3 text-sm text-ink/80">
            <Info size={16} className="mt-0.5 shrink-0 text-sky" />
            places.json has no coordinates for individual attractions, so only the city is pinned.
            No locations were guessed.
          </p>
          <ul className="mt-4 divide-y divide-line">
            {scheduled.map((p) => (
              <li key={p.place_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <span>
                  <span className="font-medium">{p.name}</span>
                  <span className="block text-slate">{titleCase(p.category)}, rated {p.rating}</span>
                </span>
                <span className="shrink-0 rounded-full bg-cloud px-2.5 py-0.5 text-xs font-medium">Day {p.day}</span>
              </li>
            ))}
            {scheduled.length === 0 && <li className="py-3 text-sm text-mist">No dataset attractions scheduled.</li>}
          </ul>
        </div>
      </div>
    </section>
  );
}
