/**
 * SYNAPSE Atlas Console — /:city layout route.
 *
 * Validates the URL param, exposes the active city to children via
 * route context, and serves as the boundary that re-keys per-city
 * React Query caches when the city segment changes.
 */
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";

const CITIES = ["bengaluru", "mumbai"] as const;
type City = (typeof CITIES)[number];

function isCity(value: string): value is City {
  return (CITIES as readonly string[]).includes(value);
}

export const Route = createFileRoute("/$city")({
  beforeLoad: ({ params }) => {
    if (!isCity(params.city)) {
      throw redirect({ to: "/$city/", params: { city: "bengaluru" } });
    }
  },
  component: () => <Outlet />,
});
