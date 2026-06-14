import { ConfidenceChip } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useFirehoseStore } from "@state/firehose.store";
import { useState } from "react";

/**
 * Surfaces the most-recent disruption alert from the firehose. Sprint 17: the
 * banner is now an expandable disclosure — collapsed it is the one-line alert,
 * expanded it reveals the full Disruption Shield anatomy (the anomaly-detector
 * ensemble, the retrieved playbook, and the Monte-Carlo impact) that the
 * DisruptionAlert payload always carried but the UI never showed. Dismisses
 * automatically when the underlying ring buffer cycles past it.
 */
export function DisruptionBanner() {
  const items = useFirehoseStore((s) => s.disruptions.items);
  const latest = items[items.length - 1];
  const [open, setOpen] = useState(false);
  if (!latest) return null;

  const scores = latest.anomaly_scores;
  const mc = latest.monte_carlo_impact;

  return (
    <div role="alert" className="syn-card-raised border-l-4 border-confidence-risk px-4 py-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-2 text-left focus-visible:shadow-focus focus-visible:outline-none"
      >
        <Badge tone="danger">Disruption</Badge>
        <span className="text-sm font-semibold text-ink">
          {latest.disruption_type ?? "supply-chain anomaly"}
        </span>
        <Badge tone="warning">Level {latest.alert_level}/10</Badge>
        <span className="text-xs text-ink-muted">
          {latest.affected_nodes.length} affected node
          {latest.affected_nodes.length === 1 ? "" : "s"}
        </span>
        <ConfidenceChip value={latest.confidence} />
        {items.length > 1 && (
          <span className="text-2xs text-ink-subtle">+{items.length - 1} more recent</span>
        )}
        <span className="ml-auto text-2xs text-ink-subtle">{open ? "Hide ▲" : "Details ▼"}</span>
      </button>

      {!open && (
        <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{latest.reasoning_chain}</p>
      )}

      {open && (
        <div className="mt-3 space-y-3 text-xs">
          <div>
            <h4 className="text-2xs uppercase tracking-wide text-ink-subtle">Reasoning</h4>
            <p className="mt-0.5 text-ink-muted">{latest.reasoning_chain}</p>
          </div>

          <div>
            <h4 className="text-2xs uppercase tracking-wide text-ink-subtle">Anomaly ensemble</h4>
            <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
              {(
                [
                  ["Isolation forest", scores.isolation_forest],
                  ["LSTM autoencoder", scores.lstm_autoencoder],
                  ["GNN structural", scores.gnn_structural],
                  ["Ensemble", scores.ensemble_weighted],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt className="text-ink-subtle">{label}</dt>
                  <dd className="font-mono tabular-nums text-ink">{value.toFixed(3)}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-2xs uppercase tracking-wide text-ink-subtle">Playbook</h4>
            <Badge tone="neutral">{latest.playbook_id}</Badge>
            {latest.playbook_actions && (
              <span className="text-ink-muted">{latest.playbook_actions}</span>
            )}
          </div>

          {mc && (
            <div>
              <h4 className="text-2xs uppercase tracking-wide text-ink-subtle">
                Monte-Carlo impact
              </h4>
              <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
                {mc.scenarios_run != null && (
                  <div>
                    <dt className="text-ink-subtle">Scenarios</dt>
                    <dd className="font-mono tabular-nums text-ink">{mc.scenarios_run}</dd>
                  </div>
                )}
                {mc.expected_kpi_degradation_pct != null && (
                  <div>
                    <dt className="text-ink-subtle">Expected KPI loss</dt>
                    <dd className="font-mono tabular-nums text-ink">
                      {mc.expected_kpi_degradation_pct.toFixed(1)}%
                    </dd>
                  </div>
                )}
                {mc.p95_degradation_pct != null && (
                  <div>
                    <dt className="text-ink-subtle">p95 KPI loss</dt>
                    <dd className="font-mono tabular-nums text-confidence-warn">
                      {mc.p95_degradation_pct.toFixed(1)}%
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          <div>
            <h4 className="text-2xs uppercase tracking-wide text-ink-subtle">Affected nodes</h4>
            <div className="mt-1 flex flex-wrap gap-1">
              {latest.affected_nodes.slice(0, 24).map((n) => (
                <span
                  key={n}
                  className="rounded bg-surface px-1.5 py-0.5 font-mono text-2xs text-ink-muted"
                >
                  {n}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
