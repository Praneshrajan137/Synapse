import type { City } from "@domain/primitives";
import { DataPathNotice, KPITile } from "@ds/compounds";
import { useCalibration } from "@hooks/use-calibration";
import { cn } from "@lib/cn";
import { useState } from "react";
import { surfaceDataPath } from "../data-paths";
import { ReliabilityCurve } from "./ReliabilityCurve";
import {
  AWAITING_SCORED_OUTCOMES,
  NO_VALUE_MARKER,
  formatMetric,
  hasScoredEvidence,
  isProvisional,
  outcomeMix,
} from "./logic";

interface CalibrationPanelProps {
  readonly city?: City;
}

/**
 * "Are the confidences calibrated to reality?" — the reliability curve + Brier
 * over the scored outcomes (ADR-047). Defaults to REAL decisions only
 * (FE-INV-044); always discloses n + as_of + window (FE-INV-043) so a thin
 * sample reads as thin, never a confident-looking curve on no evidence.
 *
 * R3.5: `n_scored ?? 0` used to make a FAILED calibration read indistinguishable
 * from a genuinely unscored window - both drew "n=0 scored · awaiting scored
 * outcomes". They are different facts: one says the pipeline did not answer, the
 * other says it answered with nothing. The data-path notice states which, and
 * the disclosure line renders the explicit no-value marker instead of a 0 when
 * the read did not answer. R4.3: the synthetic toggle already segments
 * decision-sourced synthetic rows; the notice carries that state as the
 * panel-level label.
 */
export function CalibrationPanel({ city }: CalibrationPanelProps) {
  const [includeSynthetic, setIncludeSynthetic] = useState(false);
  const q = useCalibration({ includeSynthetic, ...(city ? { city } : {}) });
  const data = q.data;
  const known = data !== undefined;

  const dataPath = surfaceDataPath("operations.calibration", {
    degraded: q.isError ? true : known ? false : null,
    // The aggregate is synthetic-sourced exactly when the operator has opted
    // synthetic decisions back in; with no answered read we cannot claim either.
    synthetic: known ? includeSynthetic : null,
  });

  const brier = data?.brier_score;
  const nScored = data?.n_scored ?? 0;
  // FE-INV-043 (Req 4.4): fewer than 30 scored outcomes reads as provisional.
  // Only meaningful once the read answered - an unanswered read is not a thin
  // sample, it is no sample.
  const provisional = known && isProvisional(nScored);
  // FE-INV-043 (Req 4.5): no scored evidence → "awaiting scored outcomes".
  const awaiting = known && !hasScoredEvidence(nScored);

  // Tri-state outcome mix (FE-INV-041): confirmed / diverged / unknown.
  // `unknown` is rendered with the chroma-drained honesty marker — NEVER
  // folded into confirmed (the derivation lives in the tested pure helper).
  const nUnknown = data?.n_unknown ?? 0;
  const mix = outcomeMix(data?.bins ?? [], data?.n_scored ?? 0, nUnknown);
  const { confirmed: confirmedN, diverged: divergedN } = mix;
  const mixTotal = Math.max(1, mix.total);

  return (
    <section className="syn-card space-y-3 p-4" aria-label="Confidence calibration">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Calibration</h2>
        <button
          type="button"
          onClick={() => setIncludeSynthetic((s) => !s)}
          aria-pressed={includeSynthetic}
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

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
        <ReliabilityCurve bins={data?.bins ?? []} />
        <div className="space-y-3">
          <KPITile
            label="Brier score"
            value={formatMetric(brier)}
            tone={brier === null || brier === undefined ? "neutral" : brier > 0.25 ? "warn" : "ok"}
          />
          <p className="text-2xs text-ink-muted">
            Lower is better. <span className="text-ink-subtle">null = no scored evidence yet.</span>
          </p>
        </div>
      </div>

      {/* Tri-state outcome mix (FE-INV-041): unknown is its own drained band. */}
      <div className="space-y-1">
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface">
          <div
            className="h-full bg-signal-success/70"
            style={{ width: `${(confirmedN / mixTotal) * 100}%` }}
            title={`confirmed: ${confirmedN}`}
          />
          <div
            className="h-full bg-signal-danger/70"
            style={{ width: `${(divergedN / mixTotal) * 100}%` }}
            title={`diverged: ${divergedN}`}
          />
          <div
            className="h-full bg-state-degraded"
            style={{ width: `${(nUnknown / mixTotal) * 100}%` }}
            title={`unknown: ${nUnknown}`}
          />
        </div>
        <div className="flex flex-wrap gap-x-3 text-2xs text-ink-muted">
          <span className="text-signal-success">✓ {confirmedN} confirmed</span>
          <span className="text-signal-danger">✕ {divergedN} diverged</span>
          <span className="text-state-degraded">? {nUnknown} unknown</span>
        </div>
      </div>

      {/* FE-INV-043: statistical-power disclosure is ALWAYS present. An
          unanswered read discloses the no-value marker, NOT a zero: "n=0 scored"
          is a measurement and "n=— scored" is the absence of one (Req 4.6). */}
      <p className="text-2xs text-ink-subtle">
        n={known ? data.n_scored : NO_VALUE_MARKER} scored ·{" "}
        {known ? data.n_unknown : NO_VALUE_MARKER} unknown ·{" "}
        {known ? data.window_hours : NO_VALUE_MARKER}h window · as of{" "}
        {data?.as_of ?? NO_VALUE_MARKER}
        {!known ? (
          <span className="text-state-degraded"> · calibration read did not answer</span>
        ) : awaiting ? (
          <span className="text-signal-warning"> · {AWAITING_SCORED_OUTCOMES.toLowerCase()}</span>
        ) : (
          provisional && (
            <span className="text-signal-warning"> · provisional — thin sample (n&lt;30)</span>
          )
        )}
      </p>
    </section>
  );
}
