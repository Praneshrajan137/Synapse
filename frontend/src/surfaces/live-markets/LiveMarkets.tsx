import type { DemandForecast } from "@domain/demand-forecast";
import type { FreshnessAlert } from "@domain/freshness-alert";
import type { PricingUpdate } from "@domain/pricing-update";
import { ConfidenceChip, ConnectionPill, DataPathNotice, PageHeader } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useFirehose } from "@hooks/use-firehose";
import { cn } from "@lib/cn";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { surfaceDataPath } from "../data-paths";

/**
 * Live Markets — viewer surface streaming the Pricing Oracle's price moves and
 * the Freshness Guardian's shelf-life alerts in real time off the multiplexed
 * firehose (channels `pricing` + `freshness`).
 *
 * Domain honesty: the I-6 hard cap pins essential-SKU multipliers at 1.3×. When
 * an update is `is_essential` and at/over the cap we render the multiplier with
 * a "(cap)" marker and surface `essential_cap_enforced` as a lock badge — the
 * guardrail is visible to the operator, not buried in the payload.
 *
 * R3.5, and the honest limit of it on this surface. This is the console's main
 * view of the FLAGSHIP agent's output (Demand Prophet forecasts), and while no
 * checkpoint is published that pipeline reports `degraded=true` in its
 * provenance. These three firehose payloads carry no provenance block at all -
 * `DemandForecastSchema`, `PricingUpdateSchema` and `FreshnessAlertSchema` have
 * no `degraded` and no `is_synthetic` field - so the console CANNOT render the
 * flag: it does not arrive. Under I-7 the answer is not to omit the question but
 * to state that it is unanswerable here, which is what the "read state unknown"
 * notice does. Absence of a degradation flag is not evidence of a live model.
 * The gap is upstream, in `proto/domain/{demand_forecast,pricing_update,
 * freshness_alert}.schema.json`; closing it turns these notices affirmative with
 * no change to this surface.
 */

/** Newest-first view: firehose buffers are append-ordered (FE-INV-017). */
function newestFirst<T>(items: ReadonlyArray<T>): ReadonlyArray<T> {
  return [...items].reverse();
}

function daysToExpiryClass(days: number): string {
  if (days <= 1) return "text-confidence-risk";
  if (days <= 3) return "text-confidence-warn";
  return "text-ink";
}

function PricingRow({ row }: { readonly row: PricingUpdate }) {
  const cappedEssential = row.is_essential && row.multiplier >= 1.3;
  return (
    <tr className="hover:bg-surface-raised/50">
      <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink-muted">
        {fmt.relativeTime(row.timestamp)}
      </td>
      <td className="px-3 py-2 font-mono text-2xs text-ink">{fmt.shortId(row.sku_id)}</td>
      <td className="px-3 py-2 text-xs text-ink-muted">{row.category}</td>
      <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink">
        <span className="text-ink-subtle">{fmt.inr(row.base_price)}</span>
        <span className="px-1 text-ink-subtle" aria-hidden>
          →
        </span>
        <span>{fmt.inr(row.final_price)}</span>
      </td>
      <td
        className={cn(
          "px-3 py-2 font-mono text-2xs tabular-nums",
          cappedEssential ? "text-confidence-warn" : "text-ink",
        )}
      >
        {row.multiplier.toFixed(2)}×{cappedEssential ? " (cap)" : ""}
      </td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-1">
          {row.is_essential ? (
            <Badge tone="warning">Essential</Badge>
          ) : (
            <Badge tone="neutral">Standard</Badge>
          )}
          {row.essential_cap_enforced ? (
            <Badge tone="warning" title="I-6 essential cap enforced (1.3×)">
              🔒 Cap
            </Badge>
          ) : null}
        </div>
      </td>
      <td className="px-3 py-2">
        <span className="font-mono text-2xs text-ink-subtle">{row.elasticity_source}</span>
      </td>
      <td className="px-3 py-2">
        <ConfidenceChip value={row.confidence} />
      </td>
    </tr>
  );
}

function FreshnessRow({ row }: { readonly row: FreshnessAlert }) {
  return (
    <tr className="hover:bg-surface-raised/50">
      <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink-muted">
        {fmt.relativeTime(row.timestamp)}
      </td>
      <td className="px-3 py-2 font-mono text-2xs text-ink">{fmt.shortId(row.sku_id)}</td>
      <td className="px-3 py-2 font-mono text-2xs text-ink-muted">{row.store_id}</td>
      <td
        className={cn(
          "px-3 py-2 font-mono text-2xs tabular-nums",
          daysToExpiryClass(row.days_to_expiry),
        )}
      >
        {row.days_to_expiry.toFixed(1)}d
      </td>
      <td className="px-3 py-2">
        <ConfidenceChip
          value={row.quality_score}
          ariaLabel={`Quality score ${Math.round(row.quality_score * 100)} percent`}
        />
      </td>
      <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink">
        {row.markdown_applied ? `−${row.markdown_pct}%` : "—"}
      </td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-1">
          {row.fssai_compliant ? (
            <Badge tone="success">FSSAI ✓</Badge>
          ) : (
            <Badge tone="danger">FSSAI ✗</Badge>
          )}
          {row.rebalance_recommended && row.target_store_id ? (
            <Badge tone="neutral">Rebalance → {row.target_store_id}</Badge>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

const DEMAND_HORIZONS = ["15min", "1h", "6h", "24h", "7d"] as const;

function DemandRow({ row }: { readonly row: DemandForecast }) {
  return (
    <tr className="hover:bg-surface-raised/50">
      <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink-muted">
        {fmt.relativeTime(row.forecast_timestamp)}
      </td>
      <td className="px-3 py-2 font-mono text-2xs text-ink">{fmt.shortId(row.sku_id)}</td>
      <td className="px-3 py-2 font-mono text-2xs text-ink-muted">{row.store_id}</td>
      {DEMAND_HORIZONS.map((h) => {
        const point = row.horizons[h];
        const lo = row.lower_90[h];
        const hi = row.upper_90[h];
        return (
          <td key={h} className="px-3 py-2 font-mono text-2xs tabular-nums text-ink">
            {point != null ? Math.round(point) : "—"}
            {lo != null && hi != null && (
              <div className="text-ink-subtle" title="90% conformal interval">
                {Math.round(lo)}–{Math.round(hi)}
              </div>
            )}
          </td>
        );
      })}
      <td className="px-3 py-2">
        {row.drift_detected ? (
          <Badge tone="warning" title="Distribution drift detected — forecast under review">
            Drift
          </Badge>
        ) : (
          <Badge tone="neutral">Stable</Badge>
        )}
      </td>
      <td className="px-3 py-2">
        <ConfidenceChip value={row.confidence} />
      </td>
    </tr>
  );
}

export function LiveMarkets() {
  const { state } = useFirehose({ topics: ["pricing", "freshness", "demand"] });
  const pricing = useFirehoseStore((s) => s.pricing.items);
  const freshness = useFirehoseStore((s) => s.freshness.items);
  const demand = useFirehoseStore((s) => s.demand.items);

  const pricingRows = newestFirst(pricing);
  const freshnessRows = newestFirst(freshness);
  const demandRows = newestFirst(demand);

  // Both signals are `null` because these payloads carry neither. The resolver
  // is fail-closed, so that resolves to "read state unknown" and never to
  // "live" - which is the whole point: the flagship agent's degradation cannot
  // be shown from a payload that does not carry it, and pretending otherwise
  // would render a degraded model's output as a healthy one.
  const streamPath = surfaceDataPath("live-markets.agent-streams", {
    degraded: null,
    synthetic: null,
  });

  return (
    <section className="space-y-4">
      <PageHeader
        title="Live Markets"
        subtitle="Streams the Pricing Oracle's price moves, the Freshness Guardian's shelf-life alerts, and the Demand Prophet's multi-horizon forecasts in real time off the firehose."
        status={<ConnectionPill state={state} />}
      />

      <DataPathNotice state={streamPath} className="syn-card px-3 py-2" />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="syn-card overflow-hidden" aria-label="Recent pricing updates">
          <header className="flex items-center justify-between border-border border-b bg-surface-raised px-3 py-2">
            <h2 className="font-semibold text-ink text-sm">Pricing Oracle</h2>
            <span className="font-mono text-2xs tabular-nums text-ink-muted">
              {pricingRows.length}
            </span>
          </header>
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-raised text-2xs text-ink-muted uppercase tracking-wide">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Time
                </th>
                <th scope="col" className="px-3 py-2">
                  SKU
                </th>
                <th scope="col" className="px-3 py-2">
                  Category
                </th>
                <th scope="col" className="px-3 py-2">
                  Price
                </th>
                <th scope="col" className="px-3 py-2">
                  Mult.
                </th>
                <th scope="col" className="px-3 py-2">
                  Type
                </th>
                <th scope="col" className="px-3 py-2">
                  Elasticity
                </th>
                <th scope="col" className="px-3 py-2">
                  Conf.
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {pricingRows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-ink-muted">
                    Waiting for live pricing events…
                  </td>
                </tr>
              ) : (
                pricingRows.map((row) => <PricingRow key={row.pricing_id} row={row} />)
              )}
            </tbody>
          </table>
        </section>

        <section className="syn-card overflow-hidden" aria-label="Recent freshness alerts">
          <header className="flex items-center justify-between border-border border-b bg-surface-raised px-3 py-2">
            <h2 className="font-semibold text-ink text-sm">Freshness Guardian</h2>
            <span className="font-mono text-2xs tabular-nums text-ink-muted">
              {freshnessRows.length}
            </span>
          </header>
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-raised text-2xs text-ink-muted uppercase tracking-wide">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Time
                </th>
                <th scope="col" className="px-3 py-2">
                  SKU
                </th>
                <th scope="col" className="px-3 py-2">
                  Store
                </th>
                <th scope="col" className="px-3 py-2">
                  Expiry
                </th>
                <th scope="col" className="px-3 py-2">
                  Quality
                </th>
                <th scope="col" className="px-3 py-2">
                  Markdown
                </th>
                <th scope="col" className="px-3 py-2">
                  FSSAI
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {freshnessRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-ink-muted">
                    Waiting for live freshness events…
                  </td>
                </tr>
              ) : (
                freshnessRows.map((row) => <FreshnessRow key={row.alert_id} row={row} />)
              )}
            </tbody>
          </table>
        </section>
      </div>

      <section className="syn-card overflow-hidden" aria-label="Recent demand forecasts">
        <header className="flex items-center justify-between border-border border-b bg-surface-raised px-3 py-2">
          <h2 className="font-semibold text-ink text-sm">Demand Prophet</h2>
          <span className="font-mono text-2xs tabular-nums text-ink-muted">
            {demandRows.length}
          </span>
        </header>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-raised text-2xs text-ink-muted uppercase tracking-wide">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Time
                </th>
                <th scope="col" className="px-3 py-2">
                  SKU
                </th>
                <th scope="col" className="px-3 py-2">
                  Store
                </th>
                {DEMAND_HORIZONS.map((h) => (
                  <th key={h} scope="col" className="px-3 py-2">
                    {h}
                  </th>
                ))}
                <th scope="col" className="px-3 py-2">
                  Drift
                </th>
                <th scope="col" className="px-3 py-2">
                  Conf.
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {demandRows.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-ink-muted">
                    Waiting for live demand forecasts… (point forecast with the 90% conformal band
                    beneath)
                  </td>
                </tr>
              ) : (
                demandRows.map((row) => (
                  <DemandRow
                    key={`${row.sku_id}-${row.store_id}-${row.forecast_timestamp}`}
                    row={row}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
