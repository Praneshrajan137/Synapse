/**
 * Effectiveness_Ratchet — the pure, I/O-free comparator (design "D. lib —
 * Effectiveness_Scorecard emitter + ratchet comparator (Req 4, Req 13)").
 *
 * The Effectiveness_Ratchet is the UI analog of the backend's `uplift_truth`
 * gate: a change that makes an operator slower, more error-prone, or that erodes
 * the North-Star Interruption_Precision must fail CI the way a code regression
 * does (Req 4.3). This module owns ONLY the comparison — it takes a committed
 * baseline scorecard and a fresh one and returns a pass/fail verdict plus the
 * named regressions. It performs no file I/O; the CI invocation script
 * (`spec/effectiveness/run-ratchet.ts`) loads the artifacts and calls
 * {@link compareScorecard}. Keeping the comparator pure makes it fully
 * property-testable (task 4.3, Property 5) and makes the gate deterministic and
 * non-flaky (Req 4.4, 20.3).
 *
 * ── Metric directions and tolerance (Req 4.3, 4.4, 13.3) ────────────────────
 * Three per-job metrics and one run-level metric are ratcheted:
 *
 *   • `steps`     — affordance activations to the terminal outcome. LOWER is
 *                   better; a relative tolerance (`stepsPct`) allows small,
 *                   noise-level increases before a regression is declared.
 *   • `latencyMs` — time-to-complete. LOWER is better; relative tolerance
 *                   (`latencyPct`).
 *   • `errorRate` — dead-ends ÷ attempts, in [0, 1]. LOWER is better; an
 *                   ABSOLUTE tolerance (`errorRateAbs`) because a fractional
 *                   tolerance on a baseline of 0 could never trip.
 *   • `interruptionPrecision` — the North-Star warranted-fraction, in [0, 1].
 *                   HIGHER is better; an ABSOLUTE tolerance
 *                   (`interruptionPrecisionAbs`). Participates as a ratcheted
 *                   metric named on regression (Req 13.3). Because the field is
 *                   reserved (`null` until task 15 wires the measurement), it is
 *                   compared ONLY when BOTH baseline and fresh carry a value;
 *                   otherwise it is neutral (neither a regression nor a
 *                   worsening), so a `null` baseline never fails the gate.
 *
 * A metric REGRESSES iff it moves in the worsening direction by MORE than its
 * tolerance relative to the baseline (Req 4.3); every regression names its job
 * and metric with both values so CI can point at the exact cause. The verdict
 * `passed` is true iff there are no regressions (Property 5).
 *
 * `canAdvanceBaseline` is set exactly when EVERY comparable metric improved or
 * held — i.e. no metric moved in the worsening direction AT ALL, even within
 * tolerance (Req 4.5). This is strictly stronger than `passed`: a within-
 * tolerance regression still passes the gate but does NOT permit advancing the
 * committed baseline, so the ratchet only ever moves monotonically toward
 * better measurements.
 */

import type {
  EffectivenessScorecard,
  JobToBeDone,
  ScorecardRow,
} from "@lib/effectiveness-scorecard";

/**
 * The explicit regression tolerance for each ratcheted metric (Req 4.4). A
 * metric must move in its worsening direction by more than this amount relative
 * to the baseline before the ratchet declares a regression.
 */
export interface RatchetTolerance {
  /** Allowed relative increase in `steps` before regression, e.g. 0.05 = 5%. */
  readonly stepsPct: number;
  /** Allowed relative increase in `latencyMs` before regression. */
  readonly latencyPct: number;
  /** Allowed absolute increase in `errorRate` (0–1) before regression. */
  readonly errorRateAbs: number;
  /** Allowed absolute decrease in `interruptionPrecision` (0–1) before regression (Req 13.3). */
  readonly interruptionPrecisionAbs: number;
}

/**
 * The default, explicitly-defined tolerance used by the CI gate (Req 4.4).
 * Chosen so that seeded, deterministic harness noise never trips the gate while
 * a genuine efficiency or precision regression does:
 *
 *   • `stepsPct` 5% — a real extra click on a golden path exceeds this.
 *   • `latencyPct` 10% — timing has more run-to-run variance than step counts.
 *   • `errorRateAbs` 0.02 — any newly-introduced dead-end moves the rate well past this.
 *   • `interruptionPrecisionAbs` 0.02 — guards the North-Star from silent erosion.
 */
export const DEFAULT_RATCHET_TOLERANCE: RatchetTolerance = {
  stepsPct: 0.05,
  latencyPct: 0.1,
  errorRateAbs: 0.02,
  interruptionPrecisionAbs: 0.02,
};

/** The metric names the ratchet reports on. */
export type RatchetMetric = "steps" | "latencyMs" | "errorRate" | "interruptionPrecision";

/** The subject a regression is attributed to: a Job_To_Be_Done or the run-level metric. */
export type RatchetSubject = JobToBeDone | "interruption-precision";

/** A single named regression: which job/metric regressed, and by how much. */
export interface RatchetRegression {
  readonly job: RatchetSubject;
  readonly metric: RatchetMetric;
  readonly baseline: number;
  readonly observed: number;
}

/** The verdict of a scorecard comparison. */
export interface RatchetResult {
  /** True iff there are no regressions beyond tolerance (Req 4.3). */
  readonly passed: boolean;
  /** Every metric that regressed beyond tolerance, each naming its job + metric. */
  readonly regressions: readonly RatchetRegression[];
  /** Set iff every comparable metric improved or held — permits a monotonic baseline advance (Req 4.5). */
  readonly canAdvanceBaseline: boolean;
}

/** The outcome of comparing a single metric against its baseline. */
interface MetricVerdict {
  /** The observed value moved in the worsening direction by any amount. */
  readonly worse: boolean;
  /** The observed value worsened by MORE than the tolerance → a regression. */
  readonly regressed: boolean;
}

/** Compare a lower-is-better metric under a relative (fractional) tolerance. */
function lowerBetterRelative(baseline: number, observed: number, pct: number): MetricVerdict {
  return { worse: observed > baseline, regressed: observed > baseline * (1 + pct) };
}

/** Compare a lower-is-better metric under an absolute tolerance. */
function lowerBetterAbsolute(baseline: number, observed: number, abs: number): MetricVerdict {
  return { worse: observed > baseline, regressed: observed > baseline + abs };
}

/** Compare a higher-is-better metric under an absolute tolerance. */
function higherBetterAbsolute(baseline: number, observed: number, abs: number): MetricVerdict {
  return { worse: observed < baseline, regressed: observed < baseline - abs };
}

/**
 * Pure comparator (Req 4.3–4.5, 13.3). Returns `passed` iff no job's steps,
 * latency, or error-rate — and no Interruption_Precision value — regresses
 * beyond `tol` relative to `baseline`; every regression names its job and
 * metric; and `canAdvanceBaseline` is set exactly when every comparable metric
 * improved or held (Property 5).
 *
 * Jobs are matched by name: a fresh row is compared only against a baseline row
 * for the same Job_To_Be_Done. A fresh job with no baseline counterpart (a newly
 * measured job) has nothing to ratchet against and is skipped.
 */
export function compareScorecard(
  baseline: EffectivenessScorecard,
  fresh: EffectivenessScorecard,
  tol: RatchetTolerance,
): RatchetResult {
  const baselineByJob = new Map<JobToBeDone, ScorecardRow>(
    baseline.rows.map((row) => [row.job, row]),
  );

  const regressions: RatchetRegression[] = [];
  let anyWorse = false;

  const record = (
    job: RatchetSubject,
    metric: RatchetMetric,
    baselineVal: number,
    observedVal: number,
    verdict: MetricVerdict,
  ): void => {
    if (verdict.worse) anyWorse = true;
    if (verdict.regressed) {
      regressions.push({ job, metric, baseline: baselineVal, observed: observedVal });
    }
  };

  for (const observed of fresh.rows) {
    const base = baselineByJob.get(observed.job);
    if (base === undefined) continue;

    record(
      observed.job,
      "steps",
      base.steps,
      observed.steps,
      lowerBetterRelative(base.steps, observed.steps, tol.stepsPct),
    );
    record(
      observed.job,
      "latencyMs",
      base.latencyMs,
      observed.latencyMs,
      lowerBetterRelative(base.latencyMs, observed.latencyMs, tol.latencyPct),
    );
    record(
      observed.job,
      "errorRate",
      base.errorRate,
      observed.errorRate,
      lowerBetterAbsolute(base.errorRate, observed.errorRate, tol.errorRateAbs),
    );
  }

  // Interruption_Precision participates only when both scorecards carry a value
  // (Req 13.3); a reserved `null` baseline never fails the gate.
  const baseIp = baseline.interruptionPrecision;
  const freshIp = fresh.interruptionPrecision;
  if (baseIp !== null && freshIp !== null) {
    record(
      "interruption-precision",
      "interruptionPrecision",
      baseIp,
      freshIp,
      higherBetterAbsolute(baseIp, freshIp, tol.interruptionPrecisionAbs),
    );
  }

  return {
    passed: regressions.length === 0,
    regressions,
    canAdvanceBaseline: !anyWorse,
  };
}
