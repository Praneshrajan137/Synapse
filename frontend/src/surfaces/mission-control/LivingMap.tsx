import { SpatialErrorBoundary } from "@ds/compounds";
import { useFirehoseStore } from "@state/firehose.store";
import { demandHeatmapLayer, routeArcLayer, storeLayer } from "@viz/deck-gl/layers";
import { Suspense, lazy, useMemo } from "react";
import { MapDataTable } from "./MapDataTable";

// CityMap pulls in maplibre + deck.gl + pmtiles — lazy-load it so the
// initial bundle stays inside FE-INV-014's 180KB gz budget.
const CityMap = lazy(() => import("@viz/maplibre/CityMap").then((m) => ({ default: m.CityMap })));

interface LivingMapProps {
  readonly stores: ReadonlyArray<{ id: string; lat: number; lon: number }>;
}

export function LivingMap({ stores }: LivingMapProps) {
  const routes = useFirehoseStore((s) => s.routes.items);
  const demand = useFirehoseStore((s) => s.demand.items);

  const layers = useMemo(
    () => [
      storeLayer(stores),
      routeArcLayer(routes),
      demandHeatmapLayer(
        demand.flatMap((d) => {
          // Position the demand weight at the parent store — fallback to
          // a neutral location if we can't resolve. The 15min horizon is
          // the freshest signal worth visualising on the map.
          const horizon = d.horizons["15min"] ?? 0;
          const parent = stores.find((s) => s.id === d.store_id);
          if (!parent) return [];
          return [{ lat: parent.lat, lon: parent.lon, weight: horizon }];
        }),
      ),
    ],
    [stores, routes, demand],
  );

  return (
    <div>
      {/* The spatial canvas: a boundary catches a failed chunk/render (error +
          retry, never a blank canvas — Req 7.5); Suspense covers loading. */}
      <SpatialErrorBoundary label="living map" height={460}>
        <Suspense
          fallback={
            <div
              className="syn-card syn-skeleton flex h-[420px] items-center justify-center text-sm text-ink-muted"
              aria-busy="true"
            >
              Loading map…
            </div>
          }
        >
          <CityMap layers={layers} height={460} />
        </Suspense>
      </SpatialErrorBoundary>

      {/* Non-spatial equivalent — keyboard/SR-reachable table of the same data
          (Req 7.4). Rendered outside the boundary so it survives a viz failure. */}
      <MapDataTable stores={stores} routes={routes} demand={demand} />
    </div>
  );
}
