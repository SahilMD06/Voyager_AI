import { AnimatePresence, MotionConfig } from "framer-motion";
import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import MainLayout from "./layouts/MainLayout.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import PlannerPage from "./pages/PlannerPage.jsx";
import PlanningPage from "./pages/PlanningPage.jsx";
import TripsPage from "./pages/TripsPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";
import Skeleton from "./components/ui/Skeleton.jsx";

// The dashboard pulls in charts and maps, so it loads on demand.
const ResultsPage = lazy(() => import("./pages/ResultsPage.jsx"));

function PageFallback() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 px-5 pt-28 lg:px-8">
      <Skeleton className="h-64" />
      <Skeleton className="h-40" />
      <Skeleton className="h-40" />
    </div>
  );
}

export default function App() {
  const location = useLocation();
  return (
    <MotionConfig reducedMotion="user">
      <Toaster position="top-center" richColors closeButton />
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route element={<MainLayout />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/plan" element={<PlannerPage />} />
            <Route path="/planning" element={<PlanningPage />} />
            <Route path="/trip/:planId" element={<Suspense fallback={<PageFallback />}><ResultsPage /></Suspense>} />
            <Route path="/trips" element={<TripsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AnimatePresence>
    </MotionConfig>
  );
}
