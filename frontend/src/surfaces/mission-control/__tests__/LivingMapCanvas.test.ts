import type { DemandForecast } from "@domain/demand-forecast";
import type { RoutePlan } from "@domain/route-plan";
import { describe, expect, it, vi } from "vitest";
import { demandPointsAt, livingMapLayers } from "../LivingMapCanvas";

// What the probe factories hand back: the layer id plus the exact data
// container it was built from, so container identity can be asserted.
interface LayerProbe {
  readonly id: string;
  readonly data: unknown;
}

// No deck.gl layer or WebGL context is built under jsdom: the factories become
// probes, and the city map the canvas would mount is inert. What is under test
// is which layers the builder asks deck.gl to aggregate, and with what data.
vi.mock("@viz/deck-gl/layers", () => ({
  storeLayer: (data: unknown): LayerProbe => ({ id: "dark-stores", data }),
  routeArcLayer: (data: unknown): LayerProbe => ({ id: "route-arcs", data }),
  demandHeatmapLayer: (data: unknown): LayerProbe => ({ id: "demand-heatmap", data }),
}));
vi.mock("@viz/maplibre/CityMap", () => ({ CityMap: (): null => null }));

const STORES: ReadonlyArray<{ id: string; lat: number; lon: number }> = [
  { id: "store-1", lat: 12.97, lon: 77.59 },
];

function demandAt(storeId: string, horizon: number): DemandForecast {
  return {
    sku_id: "sku-1",
    store_id: storeId,
    forecast_timestamp: "2026-06-06T00:00:00.000Z",
    horizons: { "15min": horizon },
    lower_90: { "15min": horizon - 2 },
    upper_90: { "15min": horizon + 2 },
    confidence: 0.87,
    drift_detected: false,
  };
}

function route(): RoutePlan {
  return {
    route_id: "22222222-2222-4222-8222-222222222222",
    rider_id: "rider-1",
    store_id: "store-1",
    stops: [{ lat: 12.97, lon: 77.59 }],
    total_distance_km: 3.2,
    total_time_min: 14,
  };
}

/** Reads a built layer back as the probe the mocked factory returned. */
function asProbe(layer: unknown): LayerProbe {
  if (typeof layer === "object" && layer !== null && "id" in layer && "data" in layer) {
    const { id, data } = layer;
    if (typeof id === "string") return { id, data };
  }
  throw new Error(`not a layer probe: ${JSON.stringify(layer)}`);
}

function layerIds(layers: ReadonlyArray<unknown>): string[] {
  return layers.map((layer) => asProbe(layer).id);
}

function layerData(layers: ReadonlyArray<unknown>, id: string): unknown {
  return layers.map(asProbe).find((layer) => layer.id === id)?.data;
}

// An empty heatmap still runs a weightsTextureSize² max-weight pass on every
// aggregation, which stalled the page under CI's software WebGL; and deck.gl
// re-aggregates whenever it is handed a new data container.
describe("livingMapLayers", () => {
  it("asks deck.gl for no heatmap while there is no demand to aggregate", () => {
    const layers = livingMapLayers(STORES, [], demandPointsAt(STORES, []));
    expect(layerIds(layers)).toEqual(["dark-stores", "route-arcs"]);
  });

  it("asks for no heatmap when the only demand is at a store the map cannot place", () => {
    const points = demandPointsAt(STORES, [demandAt("store-elsewhere", 12)]);
    expect(layerIds(livingMapLayers(STORES, [], points))).toEqual(["dark-stores", "route-arcs"]);
  });

  it("hands the heatmap the very demand-point container it is given, whatever the routes", () => {
    const points = demandPointsAt(STORES, [demandAt("store-1", 12)]);
    const before = layerData(livingMapLayers(STORES, [], points), "demand-heatmap");
    expect(before).toEqual([{ lat: 12.97, lon: 77.59, weight: 12 }]);

    const rebuilt = livingMapLayers(STORES, [route()], points);
    expect(layerData(rebuilt, "route-arcs")).toHaveLength(1);

    // The arc layer was rebuilt from the new routes; the heatmap was handed the
    // very same container, so deck.gl sees no data change and does not re-aggregate.
    expect(layerData(rebuilt, "demand-heatmap")).toBe(before);
  });
});
