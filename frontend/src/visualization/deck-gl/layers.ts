import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { ArcLayer, IconLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { RoutePlan } from "@domain/route-plan";

// Deck.gl layer factories. Pure constructors — the surface assembles
// what it needs from the firehose store. No I/O here; FE-INV-020 holds.

export interface StorePoint {
  readonly id: string;
  readonly lat: number;
  readonly lon: number;
  readonly orders_per_min?: number;
  readonly saturation?: number;
}

export function storeLayer(stores: ReadonlyArray<StorePoint>) {
  return new ScatterplotLayer<StorePoint>({
    id: "dark-stores",
    data: stores as StorePoint[],
    pickable: true,
    radiusUnits: "pixels",
    getPosition: (s) => [s.lon, s.lat],
    getRadius: (s) => 5 + Math.min(15, (s.orders_per_min ?? 0) * 0.5),
    getFillColor: (s) => {
      const sat = s.saturation ?? 0;
      if (sat > 0.9) return [239, 68, 68, 220]; // risk
      if (sat > 0.7) return [234, 179, 8, 220]; // warn
      return [56, 189, 248, 220]; // info
    },
  });
}

export function routeArcLayer(routes: ReadonlyArray<RoutePlan>) {
  const arcs = routes.flatMap((route) => {
    const stops = route.stops as ReadonlyArray<Record<string, unknown>>;
    if (stops.length < 2) return [];
    return stops.slice(1).map((stop, idx) => {
      const prev = stops[idx];
      return {
        id: `${route.route_id}-${idx}`,
        source: [Number(prev?.lon ?? 0), Number(prev?.lat ?? 0)],
        target: [Number(stop.lon ?? 0), Number(stop.lat ?? 0)],
        riskColor: (route.freshness_violations ?? 0) > 0 ? 1 : 0,
      };
    });
  });
  return new ArcLayer<{
    id: string;
    source: [number, number];
    target: [number, number];
    riskColor: number;
  }>({
    id: "route-arcs",
    data: arcs,
    getSourcePosition: (d) => d.source,
    getTargetPosition: (d) => d.target,
    getSourceColor: (d) => (d.riskColor ? [239, 68, 68, 200] : [129, 140, 248, 200]),
    getTargetColor: (d) => (d.riskColor ? [251, 113, 133, 200] : [56, 189, 248, 200]),
    getWidth: 2,
  });
}

export interface RiderPoint {
  readonly id: string;
  readonly lat: number;
  readonly lon: number;
}

const RIDER_ICON_ATLAS = {
  rider: { x: 0, y: 0, width: 32, height: 32, mask: true },
};

export function riderLayer(riders: ReadonlyArray<RiderPoint>) {
  return new IconLayer<RiderPoint>({
    id: "riders",
    data: riders as RiderPoint[],
    iconAtlas: "/icons/rider.png", // P4 may swap to inline SVG
    iconMapping: RIDER_ICON_ATLAS,
    getIcon: () => "rider",
    sizeUnits: "pixels",
    getSize: 18,
    getPosition: (r) => [r.lon, r.lat],
    getColor: [148, 163, 184, 220],
  });
}

export interface DemandPoint {
  readonly lat: number;
  readonly lon: number;
  readonly weight: number;
}

export function demandHeatmapLayer(points: ReadonlyArray<DemandPoint>) {
  return new HeatmapLayer<DemandPoint>({
    id: "demand-heatmap",
    data: points as DemandPoint[],
    getPosition: (p) => [p.lon, p.lat],
    getWeight: (p) => p.weight,
    radiusPixels: 60,
    intensity: 1.2,
    threshold: 0.05,
  });
}
