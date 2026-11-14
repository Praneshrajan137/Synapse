/**
 * Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
 *
 * Validates: Requirements 8.4
 *
 * R8.4 wants the Effectiveness_Ratchet to behave like a gate rather than like
 * decoration: when a run measures a worse console, the ratchet must FAIL and must NAME
 * what got worse. The audit's finding was the opposite in effect — `measuredRows` was
 * empty, so `compareScorecard` performed zero per-job comparisons and a degradation had
 * nothing to trip. This file attacks the comparator directly, with generated
 * degradations, so "the ratchet is sensitive" stops being an assumption about a code
 * path nobody exercised.
 *
 * ── What is universally quantified ──────────────────────────────────────────
 *
 * Over a generated baseline `EffectivenessScorecard` (one measured row per declared
 * Job_To_Be_Done from `scorecardRowsArb`, plus a run-level `interruptionPrecision`), a
 * generated `RatchetTolerance` (the shipped {@link DEFAULT_RATCHET_TOLERANCE} or a
 * drawn one, so no clause depends on today's constants), and a generated degradation /
 * improvement magnitude, EVERY `RatchetMetric` and EVERY `RatchetSubject` is exercised
 * on every run:
 *
 *   • the metric set is derived from `METRIC_FACETS`, an exhaustive
 *     `Record<RatchetMetric, MetricFacet>`. A fifth metric added to `RatchetMetric` is
 *     a TypeScript error here (a missing property) rather than a silent coverage gap,
 *     and once its facet exists every clause below picks it up automatically.
 *   • the subject set is `JOB_ORDER` plus the run-level `"interruption-precision"` —
 *     the whole `RatchetSubject` union. The sensitivity clauses LOOP over metric ×
 *     subject rather than sampling one, so "no metric and no subject goes unreported"
 *     is checked exhaustively per run, not statistically.
 *
 * ── Why these facets suffice ────────────────────────────────────────────────
 *
 * `compareScorecard` decides one thing per (subject, metric) pair: did the value move
 * in the WORSENING direction, and did it move by MORE than that metric's tolerance. So
 * the property needs the two directions right and the two sides of the threshold
 * covered, per metric:
 *
 *   • direction — `steps`, `latencyMs` and `errorRate` are better-when-LOWER, so
 *     worsening means UP; `interruptionPrecision` (the North Star) is
 *     better-when-HIGHER, so worsening means DOWN. Each facet owns its own sign, and
 *     the improvement clause proves a move the other way is never named a regression.
 *   • tolerance — mirrored from the source, per metric, not assumed: `steps` and
 *     `latencyMs` use a RELATIVE band (`baseline · (1 + pct)`), `errorRate` an ABSOLUTE
 *     rise (`baseline + abs`), `interruptionPrecision` an ABSOLUTE fall
 *     (`baseline − abs`). Beyond-threshold must be reported; within-threshold must not,
 *     while still forfeiting `canAdvanceBaseline` (Req 4.5).
 *   • identity — a scorecard compared against itself, and against a re-emitted copy
 *     whose row order differs, yields no regressions at all.
 *
 * A guard clause proves the generator space is non-trivial: every constructed
 * degradation really is strictly beyond its metric's threshold and strictly worse than
 * baseline, every constructed value stays inside the metric's domain, and the
 * within-tolerance band is non-degenerate (some generated change genuinely worsened a
 * metric without tripping the ratchet). Nothing here can pass vacuously.
 *
 * ── Recorded observations about `compareScorecard` (not fixed here) ──────────
 *
 * 1. R8.4's literal mutation — "adds one navigation step to each Job_To_Be_Done path"
 *    — is INVISIBLE to the shipped tolerance whenever a baseline row carries
 *    `steps >= 20`, because `stepsPct` is RELATIVE: `21 > 20 * 1.05` is false. The
 *    committed baseline records `steps: 20` for all five jobs, so a +1-step mutant
 *    passes today. That is a tolerance-policy gap (an absolute floor such as
 *    "one step OR 5%, whichever is smaller" would close it), not a defect in the
 *    comparator's stated semantics, so this file quantifies over degradations strictly
 *    beyond the declared tolerance and records the gap here rather than asserting
 *    against the documented contract.
 * 2. `interruptionPrecision` is compared ONLY when both scorecards carry a value, so a
 *    fresh scorecard that lost the measurement (`null`) silently skips the North-Star
 *    comparison. Deliberate per Req 13.3; the honest-emission side is R8.5 / task 11.5.
 * 3. A job present in the baseline but ABSENT from the fresh scorecard is skipped, not
 *    named — the audit's zero-comparison finding. R8.3 requires naming it; that clause
 *    belongs to Property 32 (task 11.3) and is deliberately not duplicated here.
 *
 * ── The k-leg median rule (ADR-059, operator decision S13.2=a) ───────────────
 *
 * The CI gate no longer compares one run with one run: it calls `compareLegMedians` over k = 5
 * harness legs, and judges latency by `med_f - med_b > max(p * med_b, 3 * 1.4826 * MAD_b)`,
 * with `med_b` and `MAD_b` from the BASELINE's samples only. The facets above still drive
 * `compareScorecard`, whose steps / errorRate / interruptionPrecision code is the core both
 * comparators share. The facets below drive the median rule against an oracle written apart
 * from the module (`oracleMedian`, `oracleMad`, `oracleAllowance`, with the decision's literals
 * 3 and 1.4826), and each can fail:
 *
 *   • a guard pins k = 5, 3, 1.4826 and `latencyPct` = 0.10 (widening it is forbidden), and
 *     checks the module's median and MAD against the oracle at both parities;
 *   • a median rise beyond the band regresses the row, naming both medians, and a rise of at
 *     most the band does not;
 *   • a pooled MAD would hide a shift the baseline's own MAD flags: the facet asserts that the
 *     rejected pooled rule holds the row AND that the shipped rule regresses it;
 *   • two arbitrarily slow legs of five cannot regress a row whose other three hold, and three
 *     slow legs do (what the median absorbs, and where it stops);
 *   • a zero-wide band (p = 0, identical samples) holds an equal median and regresses any rise;
 *   • steps, errorRate and interruption precision are judged on k legs exactly as on one run;
 *   • legs that agree on everything but latency pool into one sample per leg, and a leg that
 *     disagrees on steps, errorRate, a row's seed or harness version, or interruption precision
 *     is a named failure, never a value to take the median of.
 */

import {
  checkLegArrival,
  compareLegMedians,
  compareScorecard,
  DEFAULT_RATCHET_TOLERANCE,
  EFFECTIVENESS_LEG_COUNT,
  type KSampleMeasurement,
  type KSampleRow,
  LATENCY_NOISE_MULTIPLIER,
  type LatencyJudgement,
  type LegDisagreementMetric,
  type LegRatchetResult,
  type LegScorecard,
  MAD_NORMAL_CONSISTENCY,
  median,
  medianAbsoluteDeviation,
  poolLegs,
  type PoolVerdict,
  type RatchetMetric,
  type RatchetRegression,
  type RatchetResult,
  type RatchetSubject,
  type RatchetTolerance,
} from "@lib/effectiveness-ratchet";
import {
  buildScorecard,
  EFFECTIVENESS_HARNESS_SEED,
  EFFECTIVENESS_HARNESS_VERSION,
  type EffectivenessScorecard,
  JOB_ORDER,
  type JobToBeDone,
  type ScorecardRow,
} from "@lib/effectiveness-scorecard";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { jobArb, scorecardRowsArb } from "../arbitraries";

// ---------------------------------------------------------------------------
// Tolerance semantics, mirrored from `@lib/effectiveness-ratchet`
// ---------------------------------------------------------------------------

/** `steps` / `latencyMs`: better-when-lower under a RELATIVE tolerance. */
const relativeRiseThreshold = (baseline: number, pct: number): number => baseline * (1 + pct);

/** `errorRate`: better-when-lower under an ABSOLUTE tolerance. */
const absoluteRiseThreshold = (baseline: number, abs: number): number => baseline + abs;

/** `interruptionPrecision`: better-when-higher under an ABSOLUTE tolerance. */
const absoluteFallThreshold = (baseline: number, abs: number): number => baseline - abs;

/** Worsening for a better-when-lower metric: the value went UP. */
const worseWhenHigher = (baseline: number, observed: number): boolean => observed > baseline;

/** Worsening for a better-when-higher metric: the value went DOWN. */
const worseWhenLower = (baseline: number, observed: number): boolean => observed < baseline;

// ---------------------------------------------------------------------------
// Scorecard accessors and rebuilders (no index access, no non-null assertions)
// ---------------------------------------------------------------------------

/** The measured row for `job`; the generated baseline always carries all five. */
function rowOf(card: EffectivenessScorecard, job: JobToBeDone): ScorecardRow {
  const row = card.rows.find((candidate) => candidate.job === job);
  if (row === undefined) {
    throw new Error(`the generated baseline carries no row for job ${job}`);
  }
  return row;
}

/** The run-level North-Star value; the generated baseline always carries one. */
function precisionOf(card: EffectivenessScorecard): number {
  const value = card.interruptionPrecision;
  if (value === null) {
    throw new Error("the generated baseline carries no interruptionPrecision");
  }
  return value;
}

/** `card` re-emitted with `rows` (re-sorted into `JOB_ORDER` by the real emitter). */
function withRows(
  card: EffectivenessScorecard,
  rows: readonly ScorecardRow[],
): EffectivenessScorecard {
  return buildScorecard({
    rows,
    seed: card.seed,
    harnessVersion: card.harnessVersion,
    interruptionPrecision: card.interruptionPrecision,
  });
}

/** `card` with only `job`'s row rewritten — every other measurement held exactly. */
function patchRow(
  card: EffectivenessScorecard,
  job: JobToBeDone,
  patch: (row: ScorecardRow) => ScorecardRow,
): EffectivenessScorecard {
  return withRows(
    card,
    card.rows.map((row) => (row.job === job ? patch(row) : row)),
  );
}

/** `card` with only the run-level `interruptionPrecision` rewritten. */
function withPrecision(card: EffectivenessScorecard, observed: number): EffectivenessScorecard {
  return buildScorecard({
    rows: card.rows,
    seed: card.seed,
    harnessVersion: card.harnessVersion,
    interruptionPrecision: observed,
  });
}

// ---------------------------------------------------------------------------
// The exhaustive metric table
// ---------------------------------------------------------------------------

/** The closed domain a metric's values must stay inside (`max: null` = unbounded). */
interface MetricDomain {
  readonly min: number;
  readonly max: number | null;
}

/**
 * Everything the property needs to degrade, improve, and locate ONE ratcheted metric.
 *
 * One facet per `RatchetMetric`, held in an exhaustive
 * `Record<RatchetMetric, MetricFacet>`: adding a fifth metric to the union without a
 * facet is a compile error, which is why quantifying over `RATCHET_METRICS` cannot
 * silently stop covering the metric set.
 */
interface MetricFacet {
  /** The metric this facet drives; must equal its key in {@link METRIC_FACETS}. */
  readonly metric: RatchetMetric;
  /** `true` for a per-job row metric, `false` for the run-level North Star. */
  readonly perJob: boolean;
  /** The subject a regression in this metric is attributed to. */
  readonly subjectFor: (job: JobToBeDone) => RatchetSubject;
  /** The baseline value this metric is ratcheted against. */
  readonly valueOf: (card: EffectivenessScorecard, job: JobToBeDone) => number;
  /** The strict regression threshold, computed exactly as the comparator does. */
  readonly threshold: (baseline: number, tol: RatchetTolerance) => number;
  /** `true` iff `observed` moved in this metric's WORSENING direction. */
  readonly isWorse: (baseline: number, observed: number) => boolean;
  /** A value strictly BEYOND the threshold in the worsening direction, in-domain. */
  readonly beyondTolerance: (baseline: number, tol: RatchetTolerance, margin: number) => number;
  /** A value that worsens by at most the tolerance — never past the threshold. */
  readonly withinTolerance: (baseline: number, tol: RatchetTolerance, fraction: number) => number;
  /** A value strictly BETTER than `baseline`, in-domain. */
  readonly better: (baseline: number, amount: number) => number;
  /** `card` with this metric's value at `job` replaced by `observed`. */
  readonly withValue: (
    card: EffectivenessScorecard,
    job: JobToBeDone,
    observed: number,
  ) => EffectivenessScorecard;
  /** The domain the metric's values live in, so no construction leaves the schema. */
  readonly domain: MetricDomain;
}

/**
 * One facet per ratcheted metric. The `beyondTolerance` constructions are deliberately
 * threshold-relative (never "baseline + 1"), so they stay strictly beyond tolerance for
 * ANY drawn tolerance, including the degenerate zero-tolerance case.
 */
const METRIC_FACETS: Record<RatchetMetric, MetricFacet> = {
  steps: {
    metric: "steps",
    perJob: true,
    subjectFor: (job) => job,
    valueOf: (card, job) => rowOf(card, job).steps,
    threshold: (baseline, tol) => relativeRiseThreshold(baseline, tol.stepsPct),
    isWorse: worseWhenHigher,
    // Integral, and strictly above the relative band: floor(t) + 1 > t always.
    beyondTolerance: (baseline, tol, margin) =>
      Math.floor(relativeRiseThreshold(baseline, tol.stepsPct)) + 1 + Math.round(margin * 4),
    withinTolerance: (baseline, tol, fraction) =>
      baseline + fraction * (relativeRiseThreshold(baseline, tol.stepsPct) - baseline),
    better: (baseline, amount) => Math.max(0, baseline - 1 - Math.round(amount * 4)),
    withValue: (card, job, observed) => patchRow(card, job, (row) => ({ ...row, steps: observed })),
    domain: { min: 0, max: null },
  },
  latencyMs: {
    metric: "latencyMs",
    perJob: true,
    subjectFor: (job) => job,
    valueOf: (card, job) => rowOf(card, job).latencyMs,
    threshold: (baseline, tol) => relativeRiseThreshold(baseline, tol.latencyPct),
    isWorse: worseWhenHigher,
    beyondTolerance: (baseline, tol, margin) =>
      Math.ceil(relativeRiseThreshold(baseline, tol.latencyPct) + 1 + margin * baseline),
    withinTolerance: (baseline, tol, fraction) =>
      baseline + fraction * (relativeRiseThreshold(baseline, tol.latencyPct) - baseline),
    better: (baseline, amount) => Math.max(0, baseline - 1 - Math.round(amount * baseline * 0.5)),
    withValue: (card, job, observed) =>
      patchRow(card, job, (row) => ({ ...row, latencyMs: observed })),
    domain: { min: 0, max: null },
  },
  errorRate: {
    metric: "errorRate",
    perJob: true,
    subjectFor: (job) => job,
    valueOf: (card, job) => rowOf(card, job).errorRate,
    // ABSOLUTE, because a fractional tolerance on a baseline of 0 could never trip.
    threshold: (baseline, tol) => absoluteRiseThreshold(baseline, tol.errorRateAbs),
    isWorse: worseWhenHigher,
    beyondTolerance: (baseline, tol, margin) =>
      absoluteRiseThreshold(baseline, tol.errorRateAbs) + margin * 0.2,
    withinTolerance: (baseline, tol, fraction) => baseline + fraction * tol.errorRateAbs,
    better: (baseline, amount) => Math.max(0, baseline - (0.01 + amount * 0.09)),
    withValue: (card, job, observed) =>
      patchRow(card, job, (row) => ({ ...row, errorRate: observed })),
    domain: { min: 0, max: 1 },
  },
  interruptionPrecision: {
    metric: "interruptionPrecision",
    perJob: false,
    subjectFor: () => "interruption-precision",
    valueOf: (card) => precisionOf(card),
    // HIGHER is better: the North Star regresses by FALLING past an absolute band.
    threshold: (baseline, tol) => absoluteFallThreshold(baseline, tol.interruptionPrecisionAbs),
    isWorse: worseWhenLower,
    beyondTolerance: (baseline, tol, margin) =>
      absoluteFallThreshold(baseline, tol.interruptionPrecisionAbs) - margin * 0.2,
    withinTolerance: (baseline, tol, fraction) =>
      baseline - fraction * tol.interruptionPrecisionAbs,
    better: (baseline, amount) => Math.min(1, baseline + 0.01 + amount * 0.04),
    withValue: (card, _job, observed) => withPrecision(card, observed),
    domain: { min: 0, max: 1 },
  },
};

/**
 * The ratcheted metric set, DERIVED from the exhaustive facet table rather than
 * hand-listed, so a new `RatchetMetric` is covered by every clause below the moment its
 * facet exists (and is a compile error until it does).
 */
const RATCHET_METRICS: readonly RatchetMetric[] = Object.keys(METRIC_FACETS).filter(
  (key): key is RatchetMetric => key in METRIC_FACETS,
);

/** Every subject a regression can name: the five declared jobs + the run-level metric. */
const SUBJECT_UNIVERSE: readonly RatchetSubject[] = [...JOB_ORDER, "interruption-precision"];

/** The jobs a metric must be exercised over: all of them, or one for a run-level metric. */
function jobsUnder(facet: MetricFacet): readonly JobToBeDone[] {
  return facet.perJob ? JOB_ORDER : JOB_ORDER.slice(0, 1);
}

/** A stable identity for a named regression: which subject, which metric. */
function regressionKey(reg: RatchetRegression): string {
  return `${reg.job}::${reg.metric}`;
}

/** The regressions naming exactly this subject and this metric. */
function namedRegressions(
  result: RatchetResult,
  subject: RatchetSubject,
  metric: RatchetMetric,
): readonly RatchetRegression[] {
  return result.regressions.filter((reg) => reg.job === subject && reg.metric === metric);
}

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

/**
 * Bands a drawn `errorRate` into `[0.1, 0.5]`. The comparator's `errorRate` tolerance is
 * ABSOLUTE, so a degradation needs headroom ABOVE the baseline (to stay `<= 1`) and an
 * improvement needs headroom BELOW it (to stay `>= 0`). A drawn `1.0` has no room above
 * and a drawn `0.0` none below, which would make those clauses inexpressible rather
 * than false.
 */
const bandErrorRate = (drawn: number): number => 0.1 + drawn * 0.4;

/**
 * A baseline scorecard: one measured row per declared job (reusing `scorecardRowsArb`)
 * plus a run-level `interruptionPrecision` in `[0.5, 0.95]` — banded for the same
 * two-sided-headroom reason as `errorRate`, since the North Star falls to regress and
 * rises to improve.
 */
const baselineArb: fc.Arbitrary<EffectivenessScorecard> = fc
  .tuple(scorecardRowsArb, fc.double({ min: 0.5, max: 0.95, noNaN: true }))
  .map(([rows, interruptionPrecision]) =>
    buildScorecard({
      rows: rows.map((row) => ({ ...row, errorRate: bandErrorRate(row.errorRate) })),
      interruptionPrecision,
    }),
  );

/**
 * The shipped tolerance, or a drawn one. Quantifying over the tolerance is what keeps
 * the property about the ratchet's SEMANTICS rather than about today's constants: the
 * drawn ranges include the degenerate zero-tolerance case, where any worsening at all
 * must be reported.
 */
const toleranceArb: fc.Arbitrary<RatchetTolerance> = fc.oneof(
  fc.constant(DEFAULT_RATCHET_TOLERANCE),
  fc.record<RatchetTolerance>({
    stepsPct: fc.double({ min: 0, max: 0.5, noNaN: true }),
    latencyPct: fc.double({ min: 0, max: 0.5, noNaN: true }),
    errorRateAbs: fc.double({ min: 0, max: 0.1, noNaN: true }),
    interruptionPrecisionAbs: fc.double({ min: 0, max: 0.1, noNaN: true }),
  }),
);

/** A baseline, a tolerance, and the three normalized magnitudes the clauses need. */
interface RatchetCase {
  readonly baseline: EffectivenessScorecard;
  readonly tol: RatchetTolerance;
  /** How far BEYOND the tolerance a degradation is pushed. */
  readonly margin: number;
  /** What fraction OF the tolerance a within-band change consumes (never all of it). */
  readonly fraction: number;
  /** How large an improvement is. */
  readonly improvement: number;
}

const ratchetCaseArb: fc.Arbitrary<RatchetCase> = fc.record<RatchetCase>({
  baseline: baselineArb,
  tol: toleranceArb,
  margin: fc.double({ min: 0.1, max: 1, noNaN: true }),
  fraction: fc.double({ min: 0.1, max: 0.9, noNaN: true }),
  improvement: fc.double({ min: 0.1, max: 1, noNaN: true }),
});

/** One degraded comparison: what was changed, to what, and the resulting scorecard. */
interface DegradedComparison {
  readonly subject: RatchetSubject;
  readonly metric: RatchetMetric;
  readonly baselineValue: number;
  readonly observed: number;
  readonly fresh: EffectivenessScorecard;
}

/** Degrades exactly one metric of exactly one subject, strictly beyond tolerance. */
function degradeBeyondTolerance(
  baseline: EffectivenessScorecard,
  facet: MetricFacet,
  job: JobToBeDone,
  tol: RatchetTolerance,
  margin: number,
): DegradedComparison {
  const baselineValue = facet.valueOf(baseline, job);
  const observed = facet.beyondTolerance(baselineValue, tol, margin);
  return {
    subject: facet.subjectFor(job),
    metric: facet.metric,
    baselineValue,
    observed,
    fresh: facet.withValue(baseline, job, observed),
  };
}

// ---------------------------------------------------------------------------
// The k-leg median rule (ADR-059) -- an oracle written apart from the module
// ---------------------------------------------------------------------------

/** k, the number of legs the CI gate judges together. */
const K = EFFECTIVENESS_LEG_COUNT;

/** How many slow legs per row the median of k absorbs: fewer than half. */
const ABSORBED_SLOW_LEGS = Math.floor((K - 1) / 2);

/** Leg positions 0..k-1; leg n sits at position n - 1. */
const LEG_POSITIONS: readonly number[] = Array.from({ length: K }, (_, position) => position);

/** The 1-based legs, in order. */
const LEG_INDICES: readonly number[] = LEG_POSITIONS.map((position) => position + 1);

/** A commit the legs below name. Its value is incidental here; Property 32 draws it. */
const MEASURED_COMMIT = "0123456789abcdef0123456789abcdef01234567";

/** The median by sorting a copy: the middle value, or the mean of the two middle values. */
function oracleMedian(values: readonly number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const upper = sorted[Math.floor(sorted.length / 2)];
  const lower = sorted[Math.ceil(sorted.length / 2) - 1];
  if (upper === undefined || lower === undefined) {
    throw new Error("the oracle median of an empty set is undefined");
  }
  return (lower + upper) / 2;
}

/** The median absolute deviation about the oracle median. */
function oracleMad(values: readonly number[]): number {
  const centre = oracleMedian(values);
  return oracleMedian(values.map((value) => Math.abs(value - centre)));
}

/** S13.2=a's band, from the BASELINE's samples only, written with the decision's literals. */
function oracleAllowance(baseline: readonly number[], p: number): number {
  return Math.max(p * oracleMedian(baseline), 3 * 1.4826 * oracleMad(baseline));
}

/**
 * The pooled-MAD rule ADR-059 rejects: the noise width taken over the baseline's AND the fresh
 * samples about their joint median. Written here only so a facet can show it decides differently.
 */
function pooledRuleRegresses(
  baseline: readonly number[],
  fresh: readonly number[],
  p: number,
): boolean {
  const pooledMad = oracleMad([...baseline, ...fresh]);
  const allowance = Math.max(p * oracleMedian(baseline), 3 * 1.4826 * pooledMad);
  return oracleMedian(fresh) - oracleMedian(baseline) > allowance;
}

/** The item at `at`, throwing rather than asserting non-null (`noUncheckedIndexedAccess`). */
function itemAt<T>(items: readonly T[], at: number, what: string): T {
  const item = items[at];
  if (item === undefined) {
    throw new Error(`generator drift: no ${what} at ${at}`);
  }
  return item;
}

/**
 * k latencies for one row, in milliseconds at the harness's tenth-of-a-millisecond resolution
 * (finding 88 read values such as 85.3 and 2.9 ms). A centre, a spread and a per-leg jitter, so
 * the draw reaches a noise-dominated band (a wide spread) and a relative-dominated one (spread
 * 0, where MAD_b is 0).
 */
const kSamplesArb: fc.Arbitrary<readonly number[]> = fc
  .tuple(
    fc.integer({ min: 10, max: 1_000_000 }),
    fc.integer({ min: 0, max: 5_000 }),
    fc.array(fc.integer({ min: -100, max: 100 }), { minLength: K, maxLength: K }),
  )
  .map(([centre, spread, jitter]) =>
    jitter.map((share) => Math.max(0, centre + Math.round((spread * share) / 100)) / 10),
  );

/** A row as the median rule reads it, from one generated row and its k samples. */
function kRow(row: ScorecardRow, samples: readonly number[]): KSampleRow {
  return {
    job: row.job,
    steps: row.steps,
    errorRate: row.errorRate,
    latencySamples: samples.map((latencyMs) => ({ latencyMs })),
  };
}

/**
 * A k-sample baseline: one row per declared job with k drawn samples each, `errorRate` banded
 * as `baselineArb` bands it, and a run-level interruption precision.
 */
const kBaselineArb: fc.Arbitrary<KSampleMeasurement> = fc
  .tuple(
    scorecardRowsArb,
    fc.array(kSamplesArb, { minLength: JOB_ORDER.length, maxLength: JOB_ORDER.length }),
    fc.double({ min: 0.5, max: 0.95, noNaN: true }),
  )
  .map(([rows, samples, interruptionPrecision]) => ({
    rows: rows.map((row, at) =>
      kRow({ ...row, errorRate: bandErrorRate(row.errorRate) }, itemAt(samples, at, "sample set")),
    ),
    interruptionPrecision,
  }));

/** An interruption precision that may be absent, as either side of a comparison may carry it. */
const nullablePrecisionArb: fc.Arbitrary<number | null> = fc.oneof(
  fc.constant<number | null>(null),
  fc.double({ min: 0, max: 1, noNaN: true }),
);

/** The k latencies of `job`'s row, in leg order. */
function samplesOf(measurement: KSampleMeasurement, job: JobToBeDone): readonly number[] {
  const row = measurement.rows.find((candidate) => candidate.job === job);
  if (row === undefined) {
    throw new Error(`the generated measurement carries no row for ${job}`);
  }
  return row.latencySamples.map((sample) => sample.latencyMs);
}

/** `measurement` with `job`'s k samples replaced; every other measurement held exactly. */
function withSamples(
  measurement: KSampleMeasurement,
  job: JobToBeDone,
  samples: readonly number[],
): KSampleMeasurement {
  return {
    ...measurement,
    rows: measurement.rows.map((row) =>
      row.job === job
        ? { ...row, latencySamples: samples.map((latencyMs) => ({ latencyMs })) }
        : row,
    ),
  };
}

/** The median rule's judgement of `job`'s row. */
function judgementFor(result: LegRatchetResult, job: JobToBeDone): LatencyJudgement {
  const judgement = result.latency.find((candidate) => candidate.job === job);
  if (judgement === undefined) {
    throw new Error(`the comparison judged no latency for ${job}`);
  }
  return judgement;
}

/** `measurement` as one run, each row's latency its oracle median: Property 5's shape. */
function asSingleRun(measurement: KSampleMeasurement): EffectivenessScorecard {
  return buildScorecard({
    rows: measurement.rows.map((row) => ({
      job: row.job,
      steps: row.steps,
      latencyMs: oracleMedian(row.latencySamples.map((sample) => sample.latencyMs)),
      errorRate: row.errorRate,
    })),
    interruptionPrecision: measurement.interruptionPrecision,
  });
}

/** k legs measuring `measurement`: leg n reports sample n of every row and agrees on the rest. */
function legsOf(measurement: KSampleMeasurement): readonly LegScorecard[] {
  return LEG_POSITIONS.map(
    (position): LegScorecard => ({
      leg: { index: position + 1, count: K, commitSha: MEASURED_COMMIT },
      harnessVersion: EFFECTIVENESS_HARNESS_VERSION,
      seed: EFFECTIVENESS_HARNESS_SEED,
      rows: measurement.rows.map((row, at) => ({
        job: row.job,
        steps: row.steps,
        latencyMs: itemAt(row.latencySamples, position, "sample").latencyMs,
        errorRate: row.errorRate,
        harnessVersion: EFFECTIVENESS_HARNESS_VERSION,
        seed: EFFECTIVENESS_HARNESS_SEED + 101 * (at + 1),
        capturedAt: new Date(Date.UTC(2026, 10, 1, 12, 0, 0, position)).toISOString(),
      })),
      interruptionPrecision: measurement.interruptionPrecision,
    }),
  );
}

/** The legs pooled, after an arrival the generator guarantees. */
function pooledLegs(legs: readonly LegScorecard[]): PoolVerdict {
  const arrival = checkLegArrival(legs, K);
  if (arrival.outcome !== "arrived") {
    throw new Error("generator drift: k generated legs did not prove arrival");
  }
  return poolLegs(arrival);
}

/** The metrics a single leg can diverge on; `row` (a missing row) is Property 32's subject. */
type Divergence = Exclude<LegDisagreementMetric, "row">;

/** `scorecard` with one deterministic metric of `job` (or of the run) moved off the others. */
function diverge(scorecard: LegScorecard, job: JobToBeDone, metric: Divergence): LegScorecard {
  if (metric === "interruptionPrecision") {
    const value = scorecard.interruptionPrecision;
    const moved = value === null ? 0.5 : value <= 0.5 ? value + 0.25 : value - 0.25;
    return { ...scorecard, interruptionPrecision: moved };
  }
  // A const with the narrowed type, so the closure below sees the narrowing on any compiler.
  const rowMetric: Exclude<Divergence, "interruptionPrecision"> = metric;
  return {
    ...scorecard,
    rows: scorecard.rows.map((row) => {
      if (row.job !== job) return row;
      switch (rowMetric) {
        case "steps":
          return { ...row, steps: row.steps + 1 };
        case "errorRate":
          return {
            ...row,
            errorRate: row.errorRate <= 0.5 ? row.errorRate + 0.25 : row.errorRate - 0.25,
          };
        case "seed":
          return { ...row, seed: row.seed + 1 };
        case "harnessVersion":
          return { ...row, harnessVersion: `${row.harnessVersion}+diverged` };
      }
    }),
  };
}

describe("Property 33: the ratchet is sensitive to any degradation", () => {
  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("guards that the metric table is exhaustive and covers every ratchet subject", () => {
    expect(JOB_ORDER.length).toBeGreaterThan(0);
    // The metric list is the facet table's own key set — no hand-listed second source.
    expect(RATCHET_METRICS.length).toBe(Object.keys(METRIC_FACETS).length);
    expect(RATCHET_METRICS.length).toBeGreaterThanOrEqual(4);
    for (const metric of RATCHET_METRICS) {
      expect(METRIC_FACETS[metric].metric).toBe(metric);
    }

    // Every RatchetSubject — all five jobs plus the run-level metric — is reachable
    // from some facet, so the sensitivity clauses leave no subject unexercised.
    const covered = new Set<RatchetSubject>();
    for (const metric of RATCHET_METRICS) {
      const facet = METRIC_FACETS[metric];
      for (const job of jobsUnder(facet)) {
        covered.add(facet.subjectFor(job));
      }
    }
    expect(covered).toEqual(new Set(SUBJECT_UNIVERSE));
    expect(SUBJECT_UNIVERSE.length).toBe(JOB_ORDER.length + 1);
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("guards that generated degradations really exceed tolerance and stay in domain", () => {
    let beyondCount = 0;
    let strictlyWorseWithinTolerance = 0;

    fc.assert(
      fc.property(ratchetCaseArb, ({ baseline, tol, margin, fraction, improvement }) => {
        for (const metric of RATCHET_METRICS) {
          const facet = METRIC_FACETS[metric];
          for (const job of jobsUnder(facet)) {
            const baselineValue = facet.valueOf(baseline, job);
            const threshold = facet.threshold(baselineValue, tol);
            const beyond = facet.beyondTolerance(baselineValue, tol, margin);
            const within = facet.withinTolerance(baselineValue, tol, fraction);
            const better = facet.better(baselineValue, improvement);

            // The degradation is strictly past the threshold AND strictly worse than
            // baseline — the sensitivity clause cannot be satisfied vacuously.
            expect(facet.isWorse(threshold, beyond)).toBe(true);
            expect(facet.isWorse(baselineValue, beyond)).toBe(true);
            beyondCount += 1;

            // The within-band value never crosses the threshold.
            expect(facet.isWorse(threshold, within)).toBe(false);
            if (facet.isWorse(baselineValue, within)) {
              strictlyWorseWithinTolerance += 1;
            }

            // The improvement is a real move the OTHER way.
            expect(facet.isWorse(baselineValue, better)).toBe(false);
            expect(facet.isWorse(better, baselineValue)).toBe(true);

            // Nothing constructed leaves the metric's domain, so every generated
            // scorecard is one the emitter could actually have written.
            for (const value of [beyond, within, better]) {
              expect(Number.isFinite(value)).toBe(true);
              expect(value).toBeGreaterThanOrEqual(facet.domain.min);
              if (facet.domain.max !== null) {
                expect(value).toBeLessThanOrEqual(facet.domain.max);
              }
            }
          }
        }
      }),
    );

    expect(beyondCount).toBeGreaterThan(0);
    // The tolerance band is not degenerate: some generated change genuinely worsened a
    // metric without tripping the ratchet, so the within-tolerance clause has content.
    expect(strictlyWorseWithinTolerance).toBeGreaterThan(0);
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("reports a beyond-tolerance degradation of any metric of any subject, naming both", () => {
    fc.assert(
      fc.property(ratchetCaseArb, ({ baseline, tol, margin }) => {
        for (const metric of RATCHET_METRICS) {
          const facet = METRIC_FACETS[metric];
          for (const job of jobsUnder(facet)) {
            const degraded = degradeBeyondTolerance(baseline, facet, job, tol, margin);
            const result = compareScorecard(baseline, degraded.fresh, tol);

            // R8.4: the gate FAILS, and the baseline may not advance.
            expect(result.passed).toBe(false);
            expect(result.canAdvanceBaseline).toBe(false);

            // Exactly one metric of one subject moved, so exactly one named regression:
            // nothing is missed, and nothing unrelated is falsely accused.
            expect(result.regressions).toHaveLength(1);
            const named = namedRegressions(result, degraded.subject, metric);
            expect(named).toHaveLength(1);
            for (const reg of named) {
              expect(reg.baseline).toBe(degraded.baselineValue);
              expect(reg.observed).toBe(degraded.observed);
            }
          }
        }
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("names exactly the degraded subjects when every subject of a metric degrades", () => {
    fc.assert(
      fc.property(ratchetCaseArb, ({ baseline, tol, margin }) => {
        for (const metric of RATCHET_METRICS) {
          const facet = METRIC_FACETS[metric];
          const expectedKeys = new Set<string>();
          let fresh = baseline;

          for (const job of jobsUnder(facet)) {
            const baselineValue = facet.valueOf(baseline, job);
            const observed = facet.beyondTolerance(baselineValue, tol, margin);
            fresh = facet.withValue(fresh, job, observed);
            expectedKeys.add(`${facet.subjectFor(job)}::${metric}`);
          }

          const result = compareScorecard(baseline, fresh, tol);
          expect(result.passed).toBe(false);
          expect(result.canAdvanceBaseline).toBe(false);
          // Exactly the degraded subjects, no more and no fewer.
          expect(new Set(result.regressions.map(regressionKey))).toEqual(expectedKeys);
          expect(result.regressions).toHaveLength(expectedKeys.size);

          if (facet.perJob) {
            // R8.4 / Property 33: one comparison per declared Job_To_Be_Done — the
            // audit's zero-comparison ratchet would report none of these.
            expect(expectedKeys.size).toBe(JOB_ORDER.length);
          }
        }
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("never reports an improvement as a regression, and lets the baseline advance", () => {
    fc.assert(
      fc.property(ratchetCaseArb, ({ baseline, tol, improvement }) => {
        for (const metric of RATCHET_METRICS) {
          const facet = METRIC_FACETS[metric];
          for (const job of jobsUnder(facet)) {
            const baselineValue = facet.valueOf(baseline, job);
            const observed = facet.better(baselineValue, improvement);
            const fresh = facet.withValue(baseline, job, observed);
            const result = compareScorecard(baseline, fresh, tol);

            // The move really is in the better direction for THIS metric's sign
            // (lower steps/latency/error-rate, higher interruption precision).
            expect(facet.isWorse(baselineValue, observed)).toBe(false);
            expect(result.regressions).toHaveLength(0);
            expect(result.passed).toBe(true);
            // Req 4.5: everything else held, so the ratchet may advance monotonically.
            expect(result.canAdvanceBaseline).toBe(true);
          }
        }
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("respects the tolerance: a within-band worsening passes but forfeits the advance", () => {
    fc.assert(
      fc.property(ratchetCaseArb, jobArb, ({ baseline, tol, fraction }, job) => {
        for (const metric of RATCHET_METRICS) {
          const facet = METRIC_FACETS[metric];
          const baselineValue = facet.valueOf(baseline, job);
          const observed = facet.withinTolerance(baselineValue, tol, fraction);
          const fresh = facet.withValue(baseline, job, observed);
          const result = compareScorecard(baseline, fresh, tol);

          // Req 4.4: within tolerance is not a regression — the gate is a floor, not a
          // tripwire on noise.
          expect(result.regressions).toHaveLength(0);
          expect(namedRegressions(result, facet.subjectFor(job), metric)).toHaveLength(0);
          expect(result.passed).toBe(true);
          // Req 4.5: but a worsening WITHIN tolerance still blocks the baseline advance,
          // so the committed baseline only ever moves toward better measurements.
          expect(result.canAdvanceBaseline).toBe(!facet.isWorse(baselineValue, observed));
        }
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("reports no regression when a scorecard is compared against itself", () => {
    fc.assert(
      fc.property(ratchetCaseArb, ({ baseline, tol }) => {
        const identity = compareScorecard(baseline, baseline, tol);
        expect(identity.regressions).toHaveLength(0);
        expect(identity.passed).toBe(true);
        expect(identity.canAdvanceBaseline).toBe(true);

        // A re-emitted copy of the same measurement, rows in a different order, is
        // still identical to compare: sensitivity comes from the VALUES, not from
        // incidental artifact shape.
        const reEmitted = withRows(baseline, [...baseline.rows].reverse());
        const copy = compareScorecard(baseline, reEmitted, tol);
        expect(copy.regressions).toHaveLength(0);
        expect(copy.passed).toBe(true);
        expect(copy.canAdvanceBaseline).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("guards that the median rule carries the decision's constants and an independent oracle's statistics", () => {
    // Operator decision S13.2=a (ADR-059): five legs, three MAD-scaled noise widths, the
    // normal-consistency factor 1.4826, and the committed relative tolerance UNCHANGED at 10%.
    // A widened `latencyPct` fails here before it can soften the gate.
    expect(EFFECTIVENESS_LEG_COUNT).toBe(5);
    expect(LATENCY_NOISE_MULTIPLIER).toBe(3);
    expect(MAD_NORMAL_CONSISTENCY).toBe(1.4826);
    expect(DEFAULT_RATCHET_TOLERANCE.latencyPct).toBe(0.1);
    expect(ABSORBED_SLOW_LEGS).toBe(2);

    const tenthsArb = fc.integer({ min: 0, max: 2_000_000 }).map((tenths) => tenths / 10);
    fc.assert(
      fc.property(fc.array(tenthsArb, { minLength: 1, maxLength: 12 }), (values) => {
        // Both parities: an even count takes the mean of its two middle values.
        expect(median(values)).toBe(oracleMedian(values));
        expect(medianAbsoluteDeviation(values)).toBe(oracleMad(values));
        expect(median([...values].reverse())).toBe(median(values));
      }),
    );

    // A median of nothing is not a measurement, and neither is one over a non-finite value.
    expect(() => median([])).toThrow(RangeError);
    expect(() => median([1, Number.NaN])).toThrow(RangeError);
    expect(() => median([Number.POSITIVE_INFINITY])).toThrow(RangeError);
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("regresses a row whose median latency rises beyond max(p * med_b, 3 * 1.4826 * MAD_b), naming both medians", () => {
    fc.assert(
      fc.property(
        kBaselineArb,
        toleranceArb,
        jobArb,
        fc.double({ min: 0.1, max: 2, noNaN: true }),
        (baseline, tol, job, margin) => {
          const before = samplesOf(baseline, job);
          const shift = oracleAllowance(before, tol.latencyPct) * (1 + margin) + 0.5;
          const after = before.map((value) => value + shift);
          const result = compareLegMedians(baseline, withSamples(baseline, job, after), tol);

          expect(result.passed).toBe(false);
          expect(result.canAdvanceBaseline).toBe(false);
          // One row's latency moved, so exactly one regression is named, with both medians.
          expect(result.regressions).toEqual([
            {
              job,
              metric: "latencyMs",
              baseline: oracleMedian(before),
              observed: oracleMedian(after),
            },
          ]);
          const judgement = judgementFor(result, job);
          expect(judgement.regressed).toBe(true);
          expect(judgement.baselineMad).toBe(oracleMad(before));
          expect(judgement.relativeAllowance).toBe(tol.latencyPct * oracleMedian(before));
          expect(judgement.noiseAllowance).toBe(3 * 1.4826 * oracleMad(before));
          expect(judgement.allowance).toBe(oracleAllowance(before, tol.latencyPct));
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("holds a row whose median latency rises by no more than the allowance", () => {
    fc.assert(
      fc.property(
        kBaselineArb,
        toleranceArb,
        jobArb,
        fc.double({ min: 0, max: 0.95, noNaN: true }),
        (baseline, tol, job, fraction) => {
          const before = samplesOf(baseline, job);
          const shift = oracleAllowance(before, tol.latencyPct) * fraction;
          const after = before.map((value) => value + shift);
          const result = compareLegMedians(baseline, withSamples(baseline, job, after), tol);

          // Inside the band is not a regression: the gate is a floor on measured noise.
          expect(result.regressions).toEqual([]);
          expect(result.passed).toBe(true);
          expect(judgementFor(result, job).regressed).toBe(false);
          // Req 4.5: a rise inside the band still forfeits the advance; no rise keeps it.
          expect(result.canAdvanceBaseline).toBe(!(oracleMedian(after) > oracleMedian(before)));
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("regresses a shift that a pooled MAD would absorb, because MAD_b is the baseline's own", () => {
    fc.assert(
      fc.property(kBaselineArb, toleranceArb, jobArb, (baseline, tol, job) => {
        const before = samplesOf(baseline, job);
        const range = Math.max(...before) - Math.min(...before);
        // At least three baseline ranges: pooled with the shifted samples, the MAD then grows
        // with the shift itself, to at least a third of it.
        const shift = Math.max(2 * range, oracleAllowance(before, tol.latencyPct)) * 1.5 + 1;
        const after = before.map((value) => value + shift);

        // The case discriminates: the rejected pooled rule HOLDS this row...
        expect(pooledRuleRegresses(before, after, tol.latencyPct)).toBe(false);
        // ...and the shipped rule REGRESSES it, judging against the baseline's own spread.
        const result = compareLegMedians(baseline, withSamples(baseline, job, after), tol);
        expect(result.regressions.map(regressionKey)).toEqual([`${job}::latencyMs`]);
        const judgement = judgementFor(result, job);
        expect(judgement.baselineMad).toBe(oracleMad(before));
        expect(judgement.baselineMad).toBeLessThan(oracleMad([...before, ...after]));
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("lets two arbitrarily slow legs of five pass a row whose other three hold, and regresses three slow legs", () => {
    fc.assert(
      fc.property(
        kBaselineArb,
        toleranceArb,
        jobArb,
        fc.shuffledSubarray([...LEG_POSITIONS], {
          minLength: ABSORBED_SLOW_LEGS,
          maxLength: ABSORBED_SLOW_LEGS,
        }),
        fc.shuffledSubarray([...LEG_POSITIONS], {
          minLength: ABSORBED_SLOW_LEGS + 1,
          maxLength: ABSORBED_SLOW_LEGS + 1,
        }),
        (baseline, tol, job, slowPair, slowTrio) => {
          const before = samplesOf(baseline, job);
          const centre = oracleMedian(before);
          const allowance = oracleAllowance(before, tol.latencyPct);

          // Fewer than half the legs slow: the other legs hold the median, however slow the two.
          const outliers = LEG_POSITIONS.map((position) =>
            slowPair.includes(position) ? centre + allowance + 1_000_000 : centre,
          );
          const held = compareLegMedians(baseline, withSamples(baseline, job, outliers), tol);
          expect(held.regressions).toEqual([]);
          expect(judgementFor(held, job).freshMedian).toBe(centre);

          // A majority slow beyond the band: the median moves with them, and the row regresses.
          const majority = LEG_POSITIONS.map((position) =>
            slowTrio.includes(position) ? centre + allowance * 1.1 + 0.5 : 0,
          );
          const regressed = compareLegMedians(baseline, withSamples(baseline, job, majority), tol);
          expect(regressed.regressions.map(regressionKey)).toEqual([`${job}::latencyMs`]);
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("holds a zero-allowance row at an equal median and regresses it at any rise", () => {
    fc.assert(
      fc.property(
        kBaselineArb,
        jobArb,
        fc.integer({ min: 1, max: 1_000_000 }),
        (baseline, job, tenths) => {
          // p = 0 and identical baseline samples (MAD_b = 0): the band is exactly zero wide, so
          // the comparison sits on the boundary `med_f - med_b > 0` itself.
          const tol: RatchetTolerance = { ...DEFAULT_RATCHET_TOLERANCE, latencyPct: 0 };
          const flat = LEG_POSITIONS.map(() => tenths / 10);
          const pinned = withSamples(baseline, job, flat);

          const same = compareLegMedians(pinned, pinned, tol);
          expect(judgementFor(same, job).allowance).toBe(0);
          expect(same.regressions).toEqual([]);
          expect(same.canAdvanceBaseline).toBe(true);

          const risen = withSamples(
            pinned,
            job,
            flat.map((value) => value + 0.1),
          );
          const rose = compareLegMedians(pinned, risen, tol);
          expect(rose.regressions.map(regressionKey)).toEqual([`${job}::latencyMs`]);
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("judges steps, errorRate and interruption precision on k legs exactly as on one run", () => {
    const pairArb = fc.record({
      drawn: kBaselineArb,
      stepDelta: fc.array(fc.integer({ min: -5, max: 10 }), {
        minLength: JOB_ORDER.length,
        maxLength: JOB_ORDER.length,
      }),
      errorDelta: fc.array(fc.double({ min: -0.3, max: 0.3, noNaN: true }), {
        minLength: JOB_ORDER.length,
        maxLength: JOB_ORDER.length,
      }),
      baseIp: nullablePrecisionArb,
      freshIp: nullablePrecisionArb,
      tol: toleranceArb,
    });
    fc.assert(
      fc.property(pairArb, ({ drawn, stepDelta, errorDelta, baseIp, freshIp, tol }) => {
        const baseline: KSampleMeasurement = { ...drawn, interruptionPrecision: baseIp };
        // The same latency samples on both sides: latency holds, only the exact metrics move.
        const fresh: KSampleMeasurement = {
          rows: baseline.rows.map((row, at) => ({
            ...row,
            steps: Math.max(0, row.steps + itemAt(stepDelta, at, "step delta")),
            errorRate: Math.min(
              1,
              Math.max(0, row.errorRate + itemAt(errorDelta, at, "error delta")),
            ),
          })),
          interruptionPrecision: freshIp,
        };

        // ADR-059 keeps their rules exactly: the k-leg comparator and the one-run comparator
        // name the same regressions, in the same order, and agree on the advance.
        const onLegs = compareLegMedians(baseline, fresh, tol);
        const onOneRun = compareScorecard(asSingleRun(baseline), asSingleRun(fresh), tol);
        expect(onLegs.regressions).toEqual(onOneRun.regressions);
        expect(onLegs.passed).toBe(onOneRun.passed);
        expect(onLegs.canAdvanceBaseline).toBe(onOneRun.canAdvanceBaseline);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("pools k legs that differ only in latency into one sample per leg, in leg order", () => {
    fc.assert(
      fc.property(kBaselineArb, (measurement) => {
        const verdict = pooledLegs(legsOf(measurement));

        // Latency is the noisy metric: legs that differ ONLY in latency are not a disagreement.
        expect(verdict.outcome).toBe("pooled");
        if (verdict.outcome !== "pooled") return;
        expect(verdict.measurement.legCount).toBe(K);
        expect(verdict.measurement.commitSha).toBe(MEASURED_COMMIT);
        expect(verdict.measurement.rows.map((row) => row.job)).toEqual([...JOB_ORDER]);
        for (const row of verdict.measurement.rows) {
          expect(row.latencySamples.map((sample) => sample.leg)).toEqual([...LEG_INDICES]);
          expect(row.latencySamples.map((sample) => sample.latencyMs)).toEqual(
            samplesOf(measurement, row.job),
          );
          const source = measurement.rows.find((candidate) => candidate.job === row.job);
          expect(row.steps).toBe(source?.steps);
          expect(row.errorRate).toBe(source?.errorRate);
        }
        // The pooled measurement IS the rule's fresh side: against its own source, nothing moved.
        const result = compareLegMedians(
          measurement,
          verdict.measurement,
          DEFAULT_RATCHET_TOLERANCE,
        );
        expect(result.regressions).toEqual([]);
        expect(result.canAdvanceBaseline).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("fails legs that disagree on steps, errorRate, a row's seed or harness version, or interruption precision", () => {
    const divergenceArb = fc.constantFrom<Divergence>(
      "steps",
      "errorRate",
      "seed",
      "harnessVersion",
      "interruptionPrecision",
    );
    fc.assert(
      fc.property(
        kBaselineArb,
        jobArb,
        fc.integer({ min: 0, max: K - 1 }),
        divergenceArb,
        (measurement, job, position, metric) => {
          const legs = legsOf(measurement).map((scorecard, at) =>
            at === position ? diverge(scorecard, job, metric) : scorecard,
          );
          const verdict = pooledLegs(legs);

          // The harness claims these are deterministic, so one leg disagreeing is a failure,
          // never a value to take the median of.
          expect(verdict.outcome).toBe("disagreed");
          if (verdict.outcome !== "disagreed") return;
          const subject: RatchetSubject =
            metric === "interruptionPrecision" ? "interruption-precision" : job;
          expect(verdict.disagreements.map((entry) => `${entry.subject}::${entry.metric}`)).toEqual(
            [`${subject}::${metric}`],
          );

          // Every leg's value is reported, and the diverging leg's differs from all the others.
          const values = verdict.disagreements.flatMap((entry) => entry.values);
          expect(values.map((entry) => entry.leg)).toEqual([...LEG_INDICES]);
          const odd = values.find((entry) => entry.leg === position + 1);
          for (const entry of values) {
            if (entry.leg !== position + 1) expect(entry.value).not.toBe(odd?.value);
          }
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 33: The ratchet is sensitive to any degradation
  it("finds no regression when a k-sample measurement is compared against itself", () => {
    fc.assert(
      fc.property(kBaselineArb, toleranceArb, (measurement, tol) => {
        const identity = compareLegMedians(measurement, measurement, tol);
        expect(identity.regressions).toEqual([]);
        expect(identity.passed).toBe(true);
        expect(identity.canAdvanceBaseline).toBe(true);
        expect(identity.latency).toHaveLength(JOB_ORDER.length);
      }),
    );
  });
});
