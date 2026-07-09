import type { DemandForecast } from "@domain/demand-forecast";
import type { RoutePlan } from "@domain/route-plan";

interface StorePoint {
  readonly id: string;
  readonly lat: number;
  readonly lon: number;
}

interface MapDataTableProps {
  readonly stores: ReadonlyArray<StorePoint>;
  readonly routes: ReadonlyArray<RoutePlan>;
  readonly demand: ReadonlyArray<DemandForecast>;
}

/**
 * Non-spatial equivalent of the living map (Req 7.4).
 *
 * The deck.gl / MapLibre canvas is opaque to assistive tech and unreachable by
 * keyboard, so this component exposes the exact same data — dark stores, active
 * routes, and per-store demand — as keyboard-focusable, screen-reader-navigable
 * tables. It lives inside a `<details>` disclosure so it is always in the DOM
 * (SR-reachable, keyboard-operable via the `<summary>`) without crowding the
 * spatial view. Never color-only: every row is text.
 */
export function MapDataTable({ stores, routes, demand }: MapDataTableProps) {
  return (
    <details className="syn-card mt-2 p-0">
      <summary className="cursor-pointer select-none rounded-md px-3 py-2 text-xs font-medium text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:shadow-focus">
        Map data as a table ({stores.length} stores · {routes.length} routes · {demand.length}{" "}
        demand markers)
      </summary>

      <div className="space-y-4 px-3 pb-3 pt-1">
        <section aria-label="Dark stores">
          <h3 className="mb-1 text-2xs font-semibold uppercase tracking-wide text-ink-subtle">
            Dark stores ({stores.length})
          </h3>
          {stores.length === 0 ? (
            <p className="text-2xs text-ink-subtle">No stores in view.</p>
          ) : (
            <table className="w-full text-left text-2xs">
              <thead>
                <tr className="text-ink-subtle">
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Store
                  </th>
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Latitude
                  </th>
                  <th scope="col" className="py-0.5 font-medium">
                    Longitude
                  </th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums text-ink-muted">
                {stores.map((s) => (
                  <tr key={s.id}>
                    <th scope="row" className="py-0.5 pr-3 font-normal text-ink">
                      {s.id}
                    </th>
                    <td className="py-0.5 pr-3">{s.lat.toFixed(4)}</td>
                    <td className="py-0.5">{s.lon.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section aria-label="Active routes">
          <h3 className="mb-1 text-2xs font-semibold uppercase tracking-wide text-ink-subtle">
            Active routes ({routes.length})
          </h3>
          {routes.length === 0 ? (
            <p className="text-2xs text-ink-subtle">No active routes.</p>
          ) : (
            <table className="w-full text-left text-2xs">
              <thead>
                <tr className="text-ink-subtle">
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Route
                  </th>
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Store
                  </th>
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Stops
                  </th>
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Distance (km)
                  </th>
                  <th scope="col" className="py-0.5 font-medium">
                    Time (min)
                  </th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums text-ink-muted">
                {routes.map((r) => (
                  <tr key={r.route_id}>
                    <th scope="row" className="py-0.5 pr-3 font-normal text-ink">
                      {r.route_id.slice(0, 8)}
                    </th>
                    <td className="py-0.5 pr-3">{r.store_id}</td>
                    <td className="py-0.5 pr-3">{r.stops.length}</td>
                    <td className="py-0.5 pr-3">{r.total_distance_km.toFixed(1)}</td>
                    <td className="py-0.5">{r.total_time_min.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section aria-label="Demand markers">
          <h3 className="mb-1 text-2xs font-semibold uppercase tracking-wide text-ink-subtle">
            Demand markers ({demand.length})
          </h3>
          {demand.length === 0 ? (
            <p className="text-2xs text-ink-subtle">No demand signal yet.</p>
          ) : (
            <table className="w-full text-left text-2xs">
              <thead>
                <tr className="text-ink-subtle">
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    Store
                  </th>
                  <th scope="col" className="py-0.5 pr-3 font-medium">
                    SKU
                  </th>
                  <th scope="col" className="py-0.5 font-medium">
                    15-min forecast
                  </th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums text-ink-muted">
                {demand.map((d) => (
                  <tr key={`${d.store_id}-${d.sku_id}`}>
                    <th scope="row" className="py-0.5 pr-3 font-normal text-ink">
                      {d.store_id}
                    </th>
                    <td className="py-0.5 pr-3">{d.sku_id}</td>
                    <td className="py-0.5">{(d.horizons["15min"] ?? 0).toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </details>
  );
}
