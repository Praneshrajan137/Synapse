import { SpatialErrorBoundary } from "@ds/compounds";
import { useFirehoseStore } from "@state/firehose.store";
import { Suspense, lazy } from "react";
import { MapDataTable } from "./MapDataTable";

// The spatial canvas (deck.gl layers, MapLibre, pmtiles) is one lazily loaded
// module, and nothing LivingMap imports eagerly reaches deck.gl, so the deck and
// map chunks stay out of the entry's static import graph (FE-INV-014,
// FE-INV-025). The non-spatial equivalent below stays eager (Req 10.4).
const LivingMapCanvas = lazy(() =>
  import("./LivingMapCanvas").then((m) => ({ default: m.LivingMapCanvas })),
);

interface LivingMapProps {
  readonly stores: ReadonlyArray<{ id: string; lat: number; lon: number }>;
}

export function LivingMap({ stores }: LivingMapProps) {
  const routes = useFirehoseStore((s) => s.routes.items);
  const demand = useFirehoseStore((s) => s.demand.items);

  return (
    <div>
      {/* The spatial canvas: a boundary catches a failed chunk/render (error +
          retry, never a blank canvas — Req 7.5); Suspense covers loading. */}
      <SpatialErrorBoundary label="living map" height={460}>
        <Suspense
          fallback={
            <div
              className="syn-card syn-skeleton flex h-[460px] items-center justify-center text-sm text-ink-muted"
              aria-busy="true"
            >
              Loading map…
            </div>
          }
        >
          <LivingMapCanvas stores={stores} routes={routes} demand={demand} />
        </Suspense>
      </SpatialErrorBoundary>

      {/* Non-spatial equivalent — keyboard/SR-reachable table of the same data
          (Req 7.4). Rendered outside the boundary so it survives a viz failure. */}
      <MapDataTable stores={stores} routes={routes} demand={demand} />
    </div>
  );
}
