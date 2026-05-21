/**
 * SYNAPSE Atlas Console — Living City map.
 *
 * Deck.gl + MapLibre composition (ADR-012). Layers:
 *   - Dark stores (IconLayer over a static seed; ScatterplotLayer
 *     fallback in S4).
 *   - Riders (ScatterplotLayer over `synapse.routing.plan` payloads).
 *   - Routes (ArcLayer for active legs).
 *   - Freshness heatmap (ScatterplotLayer with size-by-hours-to-expiry
 *     tinted via the safety palette; HeatmapLayer swap in S6).
 *   - Disruption pins (IconLayer with critical-tier marker).
 *
 * The map mounts MapLibre with the OpenFreeMap demo tiles
 * (https://demotiles.maplibre.org/style.json) — no Mapbox token (I-1).
 * The CSP `connect-src` already allows the demo tile origin.
 *
 * 100K-marker target (plan §5.1) is a Deck.gl strength; the surface
 * stays within the 280 KB-gz route budget by route-splitting the map
 * vendor chunk (see vite.config.ts manualChunks).
 */
import DeckGL from "@deck.gl/react";
import { ArcLayer, IconLayer, ScatterplotLayer } from "@deck.gl/layers";
import { Map as MapLibreMap } from "maplibre-gl";
import { memo, useEffect, useMemo, useRef } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

import { cn } from "@shared/ui/cn";

import type { TailEvent } from "../model/event";

export interface CityCenter {
  readonly longitude: number;
  readonly latitude: number;
  readonly zoom: number;
}

const CITY_CENTERS: Record<string, CityCenter> = {
  bengaluru: { longitude: 77.5946, latitude: 12.9716, zoom: 11 },
  mumbai: { longitude: 72.8777, latitude: 19.076, zoom: 11 },
};

// Synthetic dark-store seed. In S5/S6 these come from the Neo4j knowledge
// graph; for S4 the operator just needs a believable map. Shape mirrors the
// Sprint 6 city configs in `infrastructure/`.
const DARK_STORES: Record<string, ReadonlyArray<{ id: string; longitude: number; latitude: number }>> = {
  bengaluru: [
    { id: "store-blr-12", longitude: 77.59, latitude: 12.97 },
    { id: "store-blr-15", longitude: 77.62, latitude: 12.93 },
    { id: "store-blr-18", longitude: 77.55, latitude: 12.95 },
    { id: "store-blr-22", longitude: 77.64, latitude: 13.0 },
    { id: "store-blr-30", longitude: 77.58, latitude: 13.02 },
  ],
  mumbai: [
    { id: "store-mum-04", longitude: 72.86, latitude: 19.08 },
    { id: "store-mum-09", longitude: 72.91, latitude: 19.05 },
    { id: "store-mum-13", longitude: 72.83, latitude: 19.12 },
  ],
};

interface RidersFrame {
  readonly rider_id?: string;
  readonly position?: { readonly lng: number; readonly lat: number };
}

interface RouteFrame {
  readonly route_id?: string;
  readonly legs?: ReadonlyArray<{
    readonly from_lng?: number;
    readonly from_lat?: number;
    readonly to_lng?: number;
    readonly to_lat?: number;
    readonly from?: string;
    readonly to?: string;
  }>;
}

interface FreshnessFrame {
  readonly store_id?: string;
  readonly hours_to_expiry?: number;
}

interface DisruptionFrame {
  readonly kind?: string;
  readonly severity?: number;
  readonly position?: { readonly lng: number; readonly lat: number };
}

export interface LivingMapProps {
  readonly cityId: string;
  readonly events: readonly TailEvent[];
  readonly className?: string;
  readonly showFreshness?: boolean;
  readonly showRoutes?: boolean;
}

export const LivingMap = memo(function LivingMap({
  cityId,
  events,
  className,
  showFreshness = true,
  showRoutes = true,
}: LivingMapProps) {
  const center = CITY_CENTERS[cityId] ?? CITY_CENTERS["bengaluru"]!;

  // ---- Layer extraction from the merged event tail. -----------------------
  const stores = DARK_STORES[cityId] ?? DARK_STORES["bengaluru"]!;
  const storeIndex = useMemo(() => {
    const m = new Map<string, { longitude: number; latitude: number }>();
    for (const s of stores) m.set(s.id, { longitude: s.longitude, latitude: s.latitude });
    return m;
  }, [stores]);

  const riderPositions = useMemo(() => {
    const out: { rider_id: string; longitude: number; latitude: number }[] = [];
    for (const e of events) {
      if (e.topic !== "synapse.routing.plan") continue;
      const f = e.body as RidersFrame;
      if (f.position) {
        out.push({
          rider_id: f.rider_id ?? "rider",
          longitude: f.position.lng,
          latitude: f.position.lat,
        });
      }
    }
    return out;
  }, [events]);

  const routeArcs = useMemo(() => {
    const out: {
      from: [number, number];
      to: [number, number];
    }[] = [];
    for (const e of events) {
      if (e.topic !== "synapse.routing.plan") continue;
      const f = e.body as RouteFrame;
      for (const leg of f.legs ?? []) {
        const fromLng = leg.from_lng ?? storeIndex.get(leg.from ?? "")?.longitude;
        const fromLat = leg.from_lat ?? storeIndex.get(leg.from ?? "")?.latitude;
        const toLng = leg.to_lng;
        const toLat = leg.to_lat;
        if (
          typeof fromLng === "number" &&
          typeof fromLat === "number" &&
          typeof toLng === "number" &&
          typeof toLat === "number"
        ) {
          out.push({ from: [fromLng, fromLat], to: [toLng, toLat] });
        }
      }
    }
    return out;
  }, [events, storeIndex]);

  const freshnessPoints = useMemo(() => {
    const out: { longitude: number; latitude: number; severity: number }[] = [];
    for (const e of events) {
      if (e.topic !== "synapse.freshness.alert") continue;
      const f = e.body as FreshnessFrame;
      const store = f.store_id ? storeIndex.get(f.store_id) : undefined;
      if (!store) continue;
      const severity = clamp01(1 - (f.hours_to_expiry ?? 12) / 12);
      out.push({ ...store, severity });
    }
    return out;
  }, [events, storeIndex]);

  const disruptions = useMemo(() => {
    const out: { longitude: number; latitude: number; kind: string; severity: number }[] = [];
    for (const e of events) {
      if (e.topic !== "synapse.disruption.alert") continue;
      const f = e.body as DisruptionFrame;
      if (!f.position) continue;
      out.push({
        longitude: f.position.lng,
        latitude: f.position.lat,
        kind: f.kind ?? "disruption",
        severity: clamp01(f.severity ?? 0.5),
      });
    }
    return out;
  }, [events]);

  const layers = [
    new ScatterplotLayer({
      id: "dark-stores",
      data: stores,
      getPosition: (d: (typeof stores)[number]) => [d.longitude, d.latitude],
      getRadius: 60,
      radiusUnits: "meters",
      stroked: true,
      filled: true,
      getFillColor: [96, 165, 250, 220], // tier-2/blue
      getLineColor: [248, 250, 252, 255],
      lineWidthMinPixels: 1,
      pickable: true,
    }),
    new ScatterplotLayer({
      id: "riders",
      data: riderPositions,
      getPosition: (d: (typeof riderPositions)[number]) => [d.longitude, d.latitude],
      getRadius: 24,
      radiusUnits: "meters",
      getFillColor: [74, 222, 128, 220], // tier-1/green
      pickable: true,
      visible: riderPositions.length > 0,
    }),
    showRoutes
      ? new ArcLayer({
          id: "routes",
          data: routeArcs,
          getSourcePosition: (d: (typeof routeArcs)[number]) => d.from,
          getTargetPosition: (d: (typeof routeArcs)[number]) => d.to,
          getSourceColor: [96, 165, 250, 200],
          getTargetColor: [251, 191, 36, 200],
          getWidth: 2,
        })
      : null,
    showFreshness
      ? new ScatterplotLayer({
          id: "freshness-heatmap",
          data: freshnessPoints,
          getPosition: (d: (typeof freshnessPoints)[number]) => [d.longitude, d.latitude],
          getRadius: (d: (typeof freshnessPoints)[number]) => 80 + d.severity * 240,
          radiusUnits: "meters",
          getFillColor: (d: (typeof freshnessPoints)[number]) => [
            254,
            // Lerp warn → critical (oranges into reds) by severity.
            Math.round(202 - d.severity * 80),
            116,
            Math.round(120 + d.severity * 100),
          ],
          stroked: false,
          pickable: false,
        })
      : null,
    new IconLayer({
      id: "disruptions",
      data: disruptions,
      getPosition: (d: (typeof disruptions)[number]) => [d.longitude, d.latitude],
      getSize: 28,
      getColor: [248, 113, 113, 240], // tier-4/red
      pickable: true,
      // We use a tiny built-in icon atlas; a real sprite ships in S6.
      iconAtlas:
        "data:image/svg+xml;utf8," +
        encodeURIComponent(
          '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><circle cx="16" cy="16" r="10" fill="white" stroke="black" stroke-width="2"/></svg>',
        ),
      iconMapping: { marker: { x: 0, y: 0, width: 32, height: 32, mask: false } },
      getIcon: () => "marker",
    }),
  ].filter(Boolean) as readonly object[];

  // MapLibre instance is created imperatively so Deck.gl can overlay it.
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    if (mapRef.current) return;
    mapRef.current = new MapLibreMap({
      container: containerRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [center.longitude, center.latitude],
      zoom: center.zoom,
      attributionControl: { compact: true },
    });
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [center]);

  // Sync MapLibre's view to the city change without re-creating the map.
  useEffect(() => {
    mapRef.current?.flyTo({ center: [center.longitude, center.latitude], zoom: center.zoom });
  }, [center]);

  return (
    <div
      role="region"
      aria-label="Living City map"
      className={cn("relative h-[440px] overflow-hidden rounded-md border border-border", className)}
    >
      <div ref={containerRef} className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0">
        <DeckGL
          initialViewState={{ ...center, pitch: 0, bearing: 0 }}
          controller={false}
          layers={layers}
        />
      </div>
    </div>
  );
});

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
