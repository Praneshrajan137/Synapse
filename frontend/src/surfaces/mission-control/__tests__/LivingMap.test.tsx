import type { DemandForecast } from "@domain/demand-forecast";
import type { RoutePlan } from "@domain/route-plan";
import { useFirehoseStore } from "@state/firehose.store";
import { act, render, screen, waitFor } from "@testing-library/react";
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
// probes and the city map records the layer list it is given. Which layers are
// asked for is the pure builder's claim (LivingMapCanvas.test.ts); what is under
// test here is the rendering around it — what LivingMap shows eagerly, what it
// leaves to the lazy canvas, and which data container reaches deck.gl.
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

// deck.gl re-aggregates whenever it is handed a new data container, and the
// canvas that builds the layers is a separate, lazily loaded chunk.
describe("LivingMap", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
    rendered.layerLists.length = 0;
  });

  it("renders the non-spatial table eagerly and the spatial canvas lazily", async () => {
    // A fresh module graph, so the canvas chunk certainly has not resolved yet:
    // `lazy()` caches a resolved chunk for the life of the module that made it.
    vi.resetModules();
    const fresh = await import("../LivingMap");
    render(<fresh.LivingMap stores={STORES} />);

    // First paint: the Suspense fallback holds the canvas's place, and the
    // keyboard/SR-reachable table of the same data is already there (Req 10.4).
    expect(screen.getByText("Loading map…")).toBeInTheDocument();
    expect(screen.getByText(/^Map data as a table/)).toBeInTheDocument();
    expect(rendered.layerLists).toHaveLength(0);

    // Then the canvas chunk arrives and mounts the map inside the boundary.
    await waitFor(() => expect(rendered.layerLists.length).toBeGreaterThan(0));
    expect(screen.queryByText("Loading map…")).not.toBeInTheDocument();
    expect(screen.getByText(/^Map data as a table/)).toBeInTheDocument();
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
