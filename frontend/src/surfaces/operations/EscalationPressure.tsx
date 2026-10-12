import type { City } from "@domain/primitives";
import { DataPathNotice, KPITile } from "@ds/compounds";
import { useEscalationAnalytics } from "@hooks/use-escalation-analytics";
import { cn } from "@lib/cn";
import { Link } from "react-router-dom";
import { surfaceDataPath } from "../data-paths";
import { NO_VALUE_MARKER } from "./logic";

/**
 * Escalation pressure (ADR-047): how many escalations, how fast they were
 * resolved, the override-action mix, and the dominant reasons — the
 * "where must I intervene, and did my intervention help" read. Links to the
 * Cockpit where the operator acts.
 *
 * R3.5: this panel used to render `d?.total ?? 0` and `d?.pending ?? 0`. On a
 * failed or in-flight analytics read that draws "0 escalations, 0 pending" — a
 * value derived from a read that produced nothing, rendered as the healthiest
 * possible number. Every count now falls back to the explicit no-value marker
 * and the panel declares its data-path state, so a degraded read is never
 * legible as a calm one.
 */

function fmtMs(ms: number | null): string {
  if (ms === null) return NO_VALUE_MARKER;
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

/** A count that exists, or the explicit absence marker — never a 0 stand-in. */
function fmtCount(n: number | null | undefined): string {
  return n === null || n === undefined || !Number.isFinite(n) ? NO_VALUE_MARKER : String(n);
}

const ACTION_TONE: Record<string, string> = {
  approved: "bg-signal-success/70",
  rejected: "bg-signal-danger/70",
  modified: "bg-signal-warning/70",
  none: "bg-border",
};

export function EscalationPressure({ city }: { city: City }) {
  const q = useEscalationAnalytics({ city });
  const d = q.data;

  // I-7: `degraded` is a tri-state, not a boolean. A failed read is degraded; a
  // read that has not answered yet is `null` (unknown), which the resolver
  // refuses to call "live". Only an answered read can resolve to live.
  const dataPath = surfaceDataPath("operations.escalation-pressure", {
    degraded: q.isError ? true : d === undefined ? null : false,
    synthetic: null,
  });
  const known = d !== undefined;

  const mix = d?.override_actions ?? null;
  const mixTotal =
    mix === null ? 1 : Math.max(1, mix.approved + mix.rejected + mix.modified + mix.none);

  return (
    <section className="syn-card space-y-3 p-4" aria-label="Escalation pressure">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Escalation pressure</h2>
        <Link
          to="/cockpit"
          className="text-2xs font-medium text-accent hover:underline focus-visible:outline-none focus-visible:shadow-focus"
        >
          Open Cockpit →
        </Link>
      </div>

      <DataPathNotice state={dataPath} />

      <div className="grid grid-cols-3 gap-3">
        <KPITile label="Escalations" value={fmtCount(d?.total)} />
        <KPITile
          label="Pending"
          value={fmtCount(d?.pending)}
          tone={(d?.pending ?? 0) > 0 ? "warn" : "neutral"}
        />
        <KPITile label="Resolve p50" value={fmtMs(d?.resolution_time_ms.p50 ?? null)} />
      </div>

      {/* Override-action mix — every action labelled, never colour-only (INV-CLR-011).
          With no answered read there is no mix to draw: the bar is omitted rather
          than rendered as four zero-width segments over a full-width track. */}
      <div className="space-y-1">
        <div className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">
          Override mix · {d?.window_hours ?? NO_VALUE_MARKER}h
        </div>
        {mix === null ? (
          <p className="text-xs text-ink-subtle">
            {known ? "no override mix reported" : "no override mix — the read has not answered"}
          </p>
        ) : (
          <>
            <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface">
              {(["approved", "rejected", "modified", "none"] as const).map((k) => (
                <div
                  key={k}
                  className={cn("h-full", ACTION_TONE[k])}
                  style={{ width: `${(mix[k] / mixTotal) * 100}%` }}
                  title={`${k}: ${mix[k]}`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-2xs text-ink-muted">
              <span>✓ {mix.approved} approved</span>
              <span>✕ {mix.rejected} rejected</span>
              <span>± {mix.modified} modified</span>
              <span>· {mix.none} pending</span>
            </div>
          </>
        )}
      </div>

      {/* Top escalation reasons. "None in window" and "the read did not answer"
          are different facts and read differently (Req 10.8). */}
      <div className="space-y-1">
        <div className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">Top reasons</div>
        {!known ? (
          <p className="text-xs text-state-degraded">
            unknown — the escalation analytics read did not answer
          </p>
        ) : d.top_reasons.length === 0 ? (
          <p className="text-xs text-ink-subtle">no escalations in window</p>
        ) : (
          <ul className="space-y-0.5">
            {d.top_reasons.slice(0, 5).map((r) => (
              <li key={r.reason} className="flex justify-between gap-2 text-xs">
                <span className="truncate text-ink-muted">{r.reason}</span>
                <span className="font-mono tabular-nums text-ink">{r.count}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
