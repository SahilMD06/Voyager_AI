import { Compass } from "lucide-react";
import { useNavigate } from "react-router-dom";
import Button from "../components/ui/Button.jsx";

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-xl px-5 pt-40 text-center">
      <Compass className="mx-auto text-sky" size={44} />
      <h1 className="mt-4 text-3xl">This page went off the map</h1>
      <p className="mt-2 text-slate">The link may be old. Head home or start a new plan.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Button onClick={() => navigate("/")}>Go home</Button>
        <Button variant="outline" onClick={() => navigate("/plan")}>Plan a trip</Button>
      </div>
    </div>
  );
}
