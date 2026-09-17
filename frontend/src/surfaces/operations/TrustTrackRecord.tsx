import { DataPathNotice, OperatorIdentity } from "@ds/compounds";
import { cn } from "@lib/cn";
import {
  AWAITING_SCORED_OUTCOMES,
  DEFAULT_WINDOW_LABEL,
  MIN_SCORED,
  type ScoredOutcome,
  aggregateTrack,
} from "@lib/trust-track-record";
import { useState } from "react";
import { surfaceDataPath } from "../data-paths";

/**
 * Trust_Track_Record surface (Req 11) — the authenticated operator's own
 * longitudinal view of their past judgments and how they turned out, so trust
 * is calibrated by evidence over time rather than by memory.
 *
 * Codebase reality (design finding #7): there is NO per-operator longitudinal
 * `decision_outcomes` endpoint today, so `outcomes` defaults to empty and the
 * surface renders the honest "awaiting scored outcomes" empty state (Req 11.5)
 * rather than a fabricated or zeroed record. When a per-operator feed is wired
 * later it flows in through the `outcomes` prop with no change to this surface.
 *
 * R13.6: "awaiting scored outcomes" alone is not enough. It reads as "the feed
 * exists and has produced nothing yet", which is not what is true - no feed
 * exists. The registered data path (`operations.trust-track-record`,
 * `endpoint: null`) supplies the missing half: a `[data-data-path="absent"]`
 * notice stating that nothing is fetched for this panel, so the disclosure line
 * below - `n=0 scored` - is legible as structural rather than as a measurement.
 *
 * Honesty channels (INV-CLR-011 — colour can drain, the words never lie):
 *   • the three outcome states confirmed / diverged / unknown are each rendered
 *     with a distinct non-colour glyph (✓ / ✕ / ?) and word, and `unknown` is
 *     NEVER folded into `confirmed` (Req 11.3);
 *   • low-confidence-approved judgments are broken out as distinct confirmed vs
 *     diverged counts — "12 approved → 10 confirmed, 2 diverged" (Req 11.2);
 *   • sample size, evaluation window, and an "as of" timestamp are always
 *     disclosed, and a thin sample (< MIN_SCORED) is flagged provisional
 *     (Req 11.4);
 *   • Synthetic decisions are excluded by default and a labelled toggle adds
 *     exactly those records (Req 11.6).
 */
interface TrustTrackRecordProps {
  /** Scored outcomes already scoped to the evaluation window. Defaults to empty
   *  because no per-operator longitudinal endpoint exists yet (Req 11.5). */
  readonly outcomes?: readonly ScoredOutcome[];
  /** The "as of" timestamp to disclose (Req 11.4). Injected for determinism;
   *  defaults to now. */
  readonly nowIso?: string;
  /** Human-readable evaluation-window disclosure (Req 11.4). */
  readonly windowLabel?: string;
}

export function TrustTrackRecord({
  outcomes = [],
  nowIso,
  windowLabel = DEFAULT_WINDOW_LABEL,
}: TrustTrackRecordProps) {
  const [includeSynthetic, setIncludeSynthetic] = useState(false);
  const asOf = nowIso ?? new Date().toISOString();
  const track = aggregateTrack(outcomes, includeSynthetic, asOf, windowLabel);

  const mixTotal = Math.max(1, track.sampleSize);
  // R13.6. `endpoint: null` in the registry, so this always resolves to
  // "absent" - there is no signal that could make it read otherwise.
  const dataPath = surfaceDataPath("operations.trust-track-record", {
    degraded: null,
    synthetic: null,
  });

  return (
    <section className="syn-card space-y-3 p-4" aria-label="Operator trust track record">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-ink">My track record</h2>
          <OperatorIdentity />
        </div>
        <button
          type="button"
          onClick={() => setIncludeSynthetic((s) => !s)}
          aria-pressed={includeSynthetic}
          aria-label="Include synthetic decisions"
          className={cn(
            "rounded-md border px-2 py-1 text-2xs font-medium transition-colors duration-fast",
            "focus-visible:outline-none focus-visible:shadow-focus",
            includeSynthetic
              ? "border-state-synthetic/50 text-state-synthetic"
              : "border-border text-ink-muted hover:text-ink",
          )}
        >
          {includeSynthetic ? "Including synthetic" : "Real only"}
        </button>
      </div>

      <DataPathNotice state={dataPath} />

      {track.awaiting ? (
        // Req 11.5 — no scored outcomes → say so, never a zeroed track record.
        <p className="text-xs text-ink-subtle">{AWAITING_SCORED_OUTCOMES}</p>
      ) : (
        <div className="space-y-3">
          {/* Tri-state outcome mix (Req 11.3): unknown is its own drained band,
              never folded into confirmed. */}
          <div className="space-y-1">
            <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface">
              <div
                className="h-full bg-signal-success/70"
                style={{ width: `${(track.confirmed / mixTotal) * 100}%` }}
                title={`confirmed: ${track.confirmed}`}
              />
              <div
                className="h-full bg-signal-danger/70"
                style={{ width: `${(track.diverged / mixTotal) * 100}%` }}
                title={`diverged: ${track.diverged}`}
              />
              <div
                className="h-full bg-state-degraded"
                style={{ width: `${(track.unknown / mixTotal) * 100}%` }}
                title={`unknown: ${track.unknown}`}
              />
            </div>
            <div className="flex flex-wrap gap-x-3 text-2xs text-ink-muted">
              <span className="text-signal-success">✓ {track.confirmed} confirmed</span>
              <span className="text-signal-danger">✕ {track.diverged} diverged</span>
              <span className="text-state-degraded">? {track.unknown} unknown</span>
            </div>
          </div>

          {/* Low-confidence approvals broken out as distinct confirmed vs
              diverged counts (Req 11.2): "12 approved → 10 confirmed, 2 diverged". */}
          <div className="space-y-1">
            <div className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">
              Low-confidence approvals
            </div>
            {track.lowConfidenceApproved === 0 ? (
              <p className="text-xs text-ink-subtle">none in window</p>
            ) : (
              <p className="text-xs text-ink-muted">
                <span className="font-mono text-ink">{track.lowConfidenceApproved}</span> approved
                {" → "}
                <span className="text-signal-success">
                  ✓ {track.lowConfidenceApprovedConfirmed} confirmed
                </span>
                {", "}
                <span className="text-signal-danger">
                  ✕ {track.lowConfidenceApprovedDiverged} diverged
                </span>
                {track.lowConfidenceApprovedUnknown > 0 && (
                  <>
                    {", "}
                    <span className="text-state-degraded">
                      ? {track.lowConfidenceApprovedUnknown} unknown
                    </span>
                  </>
                )}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Disclosure line is ALWAYS present (Req 11.4): sample size, window, and
          "as of" — a thin sample reads as provisional, never as a calibrated
          record. */}
      <p className="text-2xs text-ink-subtle">
        n={track.sampleSize} scored · {track.windowLabel} · as of {track.asOf}
        {track.awaiting ? (
          <span className="text-signal-warning"> · {AWAITING_SCORED_OUTCOMES.toLowerCase()}</span>
        ) : (
          track.provisional && (
            <span className="text-signal-warning">
              {" "}
              · provisional — thin sample (n&lt;{MIN_SCORED})
            </span>
          )
        )}
      </p>
    </section>
  );
}
