import type { LayersList } from "@deck.gl/core";
import type { DemandForecast } from "@domain/demand-forecast";
import type { RoutePlan } from "@domain/route-plan";
import {
  type DemandPoint,
  type StorePoint,
  demandHeatmapLayer,
  routeArcLayer,
  storeLayer,
} from "@viz/deck-gl/layers";
import { CityMap } from "@viz/maplibre/CityMap";
import { useMemo } from "react";

// The living map's spatial canvas. Everything that needs deck.gl, MapLibre or
// pmtiles sits behind this one module, which LivingMap loads with `lazy()`, so
// no eager import reaches deck.gl and `deck-*.js` is fetched with this chunk
// instead of being modulepreloaded with the entry (FE-INV-014, FE-INV-025).

/**
 * The demand weights the heatmap aggregates, one per forecast, positioned at the
 * parent store. The 15-minute horizon is the freshest signal worth visualising;
 * a forecast for a store the map cannot place contributes nothing.
 */
export function demandPointsAt(
  stores: ReadonlyArray<StorePoint>,
  demand: ReadonlyArray<DemandForecast>,
): ReadonlyArray<DemandPoint> {
  return demand.flatMap((d) => {
    const horizon = d.horizons["15min"] ?? 0;
    const parent = stores.find((s) => s.id === d.store_id);
    if (!parent) return [];
    return [{ lat: parent.lat, lon: parent.lon, weight: horizon }];
  });
}

/**
 * The deck.gl layer list for the living map; a pure function of its inputs.
 *
 * The heatmap is mounted only when there is demand to aggregate. An empty
 * heatmap draws nothing (its fragment shader discards zero-weight pixels), yet
 * every aggregation still runs a fixed max-weight pass of weightsTextureSize²
 * points (4,194,304 at the default 2048). Under CI's software rasterizer the
 * page stopped responding for 8-30 s from the first such pass.
 *
 * The heatmap is handed `demandPoints` as given, never a copy: deck.gl diffs
 * `data` by reference and a new container re-runs the whole GPU aggregation, so
 * the caller's memo of those points decides when the heatmap re-aggregates.
 */
export function livingMapLayers(
  stores: ReadonlyArray<StorePoint>,
  routes: ReadonlyArray<RoutePlan>,
  demandPoints: ReadonlyArray<DemandPoint>,
): LayersList {
  return [
    storeLayer(stores),
    routeArcLayer(routes),
    ...(demandPoints.length > 0 ? [demandHeatmapLayer(demandPoints)] : []),
  ];
}

interface LivingMapCanvasProps {
  readonly stores: ReadonlyArray<StorePoint>;
  readonly routes: ReadonlyArray<RoutePlan>;
  readonly demand: ReadonlyArray<DemandForecast>;
}

/** The lazily loaded spatial canvas: memoised deck.gl layers over the city map. */
export function LivingMapCanvas({ stores, routes, demand }: LivingMapCanvasProps) {
  // The heatmap's inputs are the stores and the demand signal only, so its
  // points get their own memo: a routing message must not hand deck.gl a new
  // heatmap data container.
  const demandPoints = useMemo(() => demandPointsAt(stores, demand), [stores, demand]);
  const layers = useMemo(
    () => livingMapLayers(stores, routes, demandPoints),
    [stores, routes, demandPoints],
  );
  return <CityMap layers={layers} height={460} />;
}
