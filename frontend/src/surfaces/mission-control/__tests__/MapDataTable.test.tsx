import type { DemandForecast } from "@domain/demand-forecast";
import type { RoutePlan } from "@domain/route-plan";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MapDataTable } from "../MapDataTable";

const STORES = [
  { id: "store-blr-001", lat: 12.93, lon: 77.62 },
  { id: "store-blr-002", lat: 12.9, lon: 77.6 },
];

const ROUTES: RoutePlan[] = [
  {
    route_id: "11111111-1111-4111-8111-111111111111",
    rider_id: "rider-1",
    store_id: "store-blr-001",
    stops: [{ stop_id: "s1" }, { stop_id: "s2" }],
    total_distance_km: 4.2,
    total_time_min: 18,
  },
];

const DEMAND: DemandForecast[] = [
  {
    sku_id: "sku-1",
    store_id: "store-blr-001",
    forecast_timestamp: "2026-06-06T00:00:00.000Z",
    horizons: { "15min": 12, "1h": 28 },
    lower_90: { "15min": 9 },
    upper_90: { "15min": 15 },
    confidence: 0.9,
    drift_detected: false,
  },
];

// Req 7.4: the deck.gl map must have a keyboard/SR-reachable non-spatial twin.
describe("MapDataTable", () => {
  it("summarises store / route / demand counts in the disclosure summary", () => {
    render(<MapDataTable stores={STORES} routes={ROUTES} demand={DEMAND} />);
    expect(screen.getByText(/2 stores · 1 routes · 1 demand markers/i)).toBeInTheDocument();
  });

  it("renders the same spatial data as text tables", () => {
    render(<MapDataTable stores={STORES} routes={ROUTES} demand={DEMAND} />);
    const storesSection = screen.getByRole("region", { name: "Dark stores" });
    expect(within(storesSection).getByText("store-blr-001")).toBeInTheDocument();
    expect(within(storesSection).getByText("12.9300")).toBeInTheDocument();

    const routesSection = screen.getByRole("region", { name: "Active routes" });
    expect(within(routesSection).getByText("store-blr-001")).toBeInTheDocument();
    expect(within(routesSection).getByText("4.2")).toBeInTheDocument();

    const demandSection = screen.getByRole("region", { name: "Demand markers" });
    expect(within(demandSection).getByText("sku-1")).toBeInTheDocument();
    expect(within(demandSection).getByText("12")).toBeInTheDocument();
  });

  it("distinguishes empty sections from populated ones", () => {
    render(<MapDataTable stores={[]} routes={[]} demand={[]} />);
    expect(screen.getByText(/no stores in view/i)).toBeInTheDocument();
    expect(screen.getByText(/no active routes/i)).toBeInTheDocument();
    expect(screen.getByText(/no demand signal yet/i)).toBeInTheDocument();
  });
});
