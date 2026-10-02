import type { DemandForecast } from "@domain/demand-forecast";
import type { RoutePlan } from "@domain/route-plan";
import { useFirehoseStore } from "@state/firehose.store";
import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LivingMap } from "../LivingMap";

// What the probe factories hand the map: the layer id plus the exact data
// container it was built from, so container identity can be asserted.
interface LayerProbe {
  readonly id: string;
  readonly data: unknown;
}

const rendered = vi.hoisted((): { layerLists: Array<ReadonlyArray<LayerProbe>> } => ({
  layerLists: [],
}));

// No deck.gl layer or WebGL context is built under jsdom: the factories become
// probes and the lazy map records the layer list it is given. What is under
// test is which layers LivingMap asks deck.gl to aggregate, and with what data.
vi.mock("@viz/deck-gl/layers", () => ({
  storeLayer: (data: unknown): LayerProbe => ({ id: "dark-stores", data }),
  routeArcLayer: (data: unknown): LayerProbe => ({ id: "route-arcs", data }),
  demandHeatmapLayer: (data: unknown): LayerProbe => ({ id: "demand-heatmap", data }),
}));
vi.mock("@viz/maplibre/CityMap", () => ({
  CityMap: ({ layers }: { readonly layers: ReadonlyArray<LayerProbe> }) => {
    rendered.layerLists.push(layers);
    return null;
  },
}));

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

function latestLayers(): ReadonlyArray<LayerProbe> {
  return rendered.layerLists.at(-1) ?? [];
}

function layerData(id: string): unknown {
  return latestLayers().find((layer) => layer.id === id)?.data;
}

// An empty heatmap still runs a weightsTextureSize² max-weight pass on every
// aggregation, which stalled the page under CI's software WebGL; and deck.gl
// re-aggregates whenever it is handed a new data container.
describe("LivingMap", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
    rendered.layerLists.length = 0;
  });

  it("asks deck.gl for no heatmap while there is no demand to aggregate", async () => {
    render(<LivingMap stores={STORES} />);
    await waitFor(() => expect(rendered.layerLists.length).toBeGreaterThan(0));
    expect(latestLayers().map((layer) => layer.id)).toEqual(["dark-stores", "route-arcs"]);
  });

  it("asks for no heatmap when the only demand is at a store the map cannot place", async () => {
    useFirehoseStore.getState().appendDemand(demandAt("store-elsewhere", 12), 1);
    render(<LivingMap stores={STORES} />);
    await waitFor(() => expect(rendered.layerLists.length).toBeGreaterThan(0));
    expect(latestLayers().map((layer) => layer.id)).toEqual(["dark-stores", "route-arcs"]);
  });

  it("keeps the heatmap's data container across a route-only update", async () => {
    useFirehoseStore.getState().appendDemand(demandAt("store-1", 12), 1);
    render(<LivingMap stores={STORES} />);
    await waitFor(() => expect(layerData("demand-heatmap")).toBeDefined());
    const before = layerData("demand-heatmap");
    expect(before).toEqual([{ lat: 12.97, lon: 77.59, weight: 12 }]);

    act(() => {
      useFirehoseStore.getState().appendRoute(route(), 1);
    });
    await waitFor(() => expect(layerData("route-arcs")).toHaveLength(1));

    // The arc layer was rebuilt from the new routes; the heatmap was handed the
    // very same container, so deck.gl sees no data change and does not re-aggregate.
    expect(layerData("demand-heatmap")).toBe(before);
  });
});
