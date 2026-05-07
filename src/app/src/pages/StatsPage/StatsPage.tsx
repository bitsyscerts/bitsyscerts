import { Navigate } from "react-router-dom";

/**
 * Legacy stats route — redirects to the Dashboard (/).
 * The `/stats` URL is kept as a compatibility alias.
 */
export function StatsPage() {
  return <Navigate to="/" replace />;
}
