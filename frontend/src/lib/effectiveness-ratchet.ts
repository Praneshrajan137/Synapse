/**
 * Effectiveness_Ratchet -- the pure, I/O-free comparator (design "D. lib --
 * Effectiveness_Scorecard emitter + ratchet comparator (Req 4, Req 13)"; ADR-059).
 *
 * The Effectiveness_Ratchet is the UI analog of the backend's `uplift_truth` gate: a change
 * that makes an operator slower, more error-prone, or that erodes the North-Star
 * Interruption_Precision must fail CI the way a code regression does (Req 4.3). This module
 * owns ONLY the comparison and performs no file I/O. `spec/effectiveness/run-ratchet.ts`
 * loads the artifacts and calls in, which keeps every rule here property-testable
 * (Properties 5, 32 and 33).
 *
 * ## Two comparators over one set of per-metric rules
 *
 *   * {@link compareLegMedians} is what the CI gate calls. It compares a pooled measurement of
 *     k harness legs against a committed baseline that carries k latency samples per row
 *     (ADR-059, operator decision S13.2=a).
 *   * {@link compareScorecard} compares one scorecard with one scorecard. No CI step calls it.
 *     It is kept because Property 5 (`src/lib/__tests__/effectiveness-ratchet.property.test.ts`)
 *     pins its semantics, and because both comparators run one private core, so Property 5
 *     still constrains the `steps`, `errorRate` and `interruptionPrecision` code the gate uses.
 *
 * ## The rules (Req 4.3, 4.4, 4.5, 13.3)
 *
 *   * `steps`: lower is better. Regresses when it rises by more than `stepsPct` of the baseline.
 *   * `errorRate`: dead-ends / attempts, in [0, 1], lower is better. Regresses when it rises by
 *     more than `errorRateAbs`. The tolerance is absolute because a relative one on a baseline
 *     of 0 could never trip.
 *   * `interruptionPrecision`: the North-Star warranted fraction, in [0, 1], higher is better.
 *     Regresses when it falls by more than `interruptionPrecisionAbs`. Compared only when both
 *     sides carry a value, so a `null` on either side is neutral (Req 13.3).
 *   * `latencyMs`: lower is better, and the two comparators differ here.
 *       - One scorecard: regresses when `observed > baseline * (1 + latencyPct)`.
 *       - k legs: regresses when `med_f - med_b > max(p * med_b, 3 * 1.4826 * MAD_b)`. `med_f`
 *         is the median of the k fresh samples. `med_b` and `MAD_b` are the median and the
 *         median absolute deviation of the BASELINE's k samples only, never pooled with the
 *         fresh ones. `p` is `latencyPct`.
 *
 * Each regression names its job and metric with both values, and `passed` is true iff there is
 * none. `canAdvanceBaseline` is set exactly when no compared metric moved in its worsening
 * direction at all, even within tolerance (Req 4.5). That is strictly stronger than `passed`,
 * so the baseline only ever moves toward better measurements.
 *
 * ## Why latency is judged on the median of k legs (ADR-059)
 *
 * The harness is seeded, so `steps`, `errorRate` and `interruptionPrecision` repeat exactly
 * from run to run. Millisecond latency does not. The strict A/A of finding 88 (Frontend CI run
 * 38298457463) moved two of five JTBD latencies by more than 10% at one sha and one seed, so
 * one run's latency cannot carry a 10% comparison. With k legs the baseline brings its own
 * measured spread (`MAD_b`), and the band is the wider of the committed relative tolerance and
 * three MAD-scaled noise widths. The three exact metrics must be IDENTICAL in every leg
 * ({@link poolLegs}). A disagreement is a failure, because the harness claims determinism for
 * them, and a median would hide it.
 *
 * ## What the k-leg rule cannot see
 *
 * It never takes a median over fewer than k legs, two commits or two harness versions
 * ({@link checkLegArrival}). It cannot see a slowdown shared by every leg of a run that stays
 * inside the relative term, because `MAD_b` measures the spread between the legs of ONE run,
 * not between runs. With k = 5 it lets up to two slow legs per row pass by construction, and a
 * MAD from five samples can understate the spread. ADR-059 records these limits and the A/A
 * predictions (AK1-AK4) a run can falsify.
 */

import {
  type EffectivenessScorecard,
  JOB_ORDER,
  type JobToBeDone,
  type ScorecardRow,
} from "@lib/effectiveness-scorecard";

// ---------------------------------------------------------------------------
// Tolerance and the shapes a comparison reports
// ---------------------------------------------------------------------------

/**
 * The explicit regression tolerance for each ratcheted metric (Req 4.4). A metric must move in
 * its worsening direction by more than this amount relative to the baseline before the ratchet
 * declares a regression.
 */
export interface RatchetTolerance {
  /** Allowed relative increase in `steps` before regression, e.g. 0.05 = 5%. */
  readonly stepsPct: number;
  /**
   * Allowed relative increase in `latencyMs`. On k legs it is `p`, the relative floor of the
   * median band; the noise term comes from the baseline's measured spread, not from here.
   */
  readonly latencyPct: number;
  /** Allowed absolute increase in `errorRate` (0-1) before regression. */
  readonly errorRateAbs: number;
  /** Allowed absolute decrease in `interruptionPrecision` (0-1) before regression (Req 13.3). */
  readonly interruptionPrecisionAbs: number;
}

/**
 * The tolerance the CI gate uses (Req 4.4):
 *
 *   * `stepsPct` 5% -- a real extra click on a golden path exceeds this.
 *   * `latencyPct` 10% -- the relative floor of the k-leg latency band. ADR-059 keeps it at 10%
 *     and adds the MAD term from measured noise; widening it is forbidden.
 *   * `errorRateAbs` 0.02 -- any newly introduced dead-end moves the rate well past this.
 *   * `interruptionPrecisionAbs` 0.02 -- guards the North-Star from silent erosion.
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
  /** Set iff every comparable metric improved or held: permits a monotonic baseline advance (Req 4.5). */
  readonly canAdvanceBaseline: boolean;
}

/** The outcome of comparing a single metric against its baseline. */
interface MetricVerdict {
  /** The observed value moved in the worsening direction by any amount. */
  readonly worse: boolean;
  /** The observed value worsened by MORE than the tolerance: a regression. */
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

// ---------------------------------------------------------------------------
// The core both comparators run
// ---------------------------------------------------------------------------

/** What every compared row carries, whatever shape its latency takes. */
interface ComparedRow {
  readonly job: JobToBeDone;
  readonly steps: number;
  readonly errorRate: number;
}

/** One row's latency comparison: the two values a regression names, and the verdict. */
interface LatencyComparison {
  readonly baseline: number;
  readonly observed: number;
  readonly verdict: MetricVerdict;
}

/**
 * The comparison both comparators run. Rows are matched by job, and a fresh job with no
 * baseline counterpart is skipped: it has nothing to ratchet against, and the CI script counts
 * the comparisons it needs separately (R8.3). The caller supplies only the latency rule, so
 * `steps`, `errorRate` and `interruptionPrecision` are judged by one code path.
 */
function ratchetRows<R extends ComparedRow>(
  baselineRows: readonly R[],
  freshRows: readonly R[],
  baselineIp: number | null,
  freshIp: number | null,
  tol: RatchetTolerance,
  latency: (base: R, observed: R) => LatencyComparison,
): RatchetResult {
  const baselineByJob = new Map<JobToBeDone, R>(baselineRows.map((row) => [row.job, row]));

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

  for (const observed of freshRows) {
    const base = baselineByJob.get(observed.job);
    if (base === undefined) continue;

    record(
      observed.job,
      "steps",
      base.steps,
      observed.steps,
      lowerBetterRelative(base.steps, observed.steps, tol.stepsPct),
    );
    const time = latency(base, observed);
    record(observed.job, "latencyMs", time.baseline, time.observed, time.verdict);
    record(
      observed.job,
      "errorRate",
      base.errorRate,
      observed.errorRate,
      lowerBetterAbsolute(base.errorRate, observed.errorRate, tol.errorRateAbs),
    );
  }

  // Interruption_Precision participates only when both sides carry a value (Req 13.3); a
  // reserved `null` baseline never fails the gate.
  if (baselineIp !== null && freshIp !== null) {
    record(
      "interruption-precision",
      "interruptionPrecision",
      baselineIp,
      freshIp,
      higherBetterAbsolute(baselineIp, freshIp, tol.interruptionPrecisionAbs),
    );
  }

  return {
    passed: regressions.length === 0,
    regressions,
    canAdvanceBaseline: !anyWorse,
  };
}

/**
 * Compares one scorecard with one scorecard (Req 4.3-4.5, 13.3; Property 5). Latency regresses
 * when `observed > baseline * (1 + latencyPct)`. The CI gate does not call this: one run's
 * millisecond latency sits inside its own noise (ADR-059), so {@link compareLegMedians} is the
 * gate's comparator. Both run {@link ratchetRows}.
 */
export function compareScorecard(
  baseline: EffectivenessScorecard,
  fresh: EffectivenessScorecard,
  tol: RatchetTolerance,
): RatchetResult {
  return ratchetRows<ScorecardRow>(
    baseline.rows,
    fresh.rows,
    baseline.interruptionPrecision,
    fresh.interruptionPrecision,
    tol,
    (base, observed) => ({
      baseline: base.latencyMs,
      observed: observed.latencyMs,
      verdict: lowerBetterRelative(base.latencyMs, observed.latencyMs, tol.latencyPct),
    }),
  );
}

// ---------------------------------------------------------------------------
// k legs and the median rule (ADR-059)
// ---------------------------------------------------------------------------

/**
 * k: how many harness legs the CI gate judges together (ADR-059, decision S13.2=a). The
 * `e2e-harness` matrix in `.github/workflows/frontend.yml` runs this many. Each leg's seal
 * refuses a matrix of another size and {@link checkLegArrival} refuses any other number of
 * scorecards, so the matrix and this constant cannot drift apart silently.
 */
export const EFFECTIVENESS_LEG_COUNT = 5;

/**
 * The factor that turns a median absolute deviation into an estimate of a normal
 * distribution's standard deviation (1 over the 0.75 quantile of the standard normal). It sets
 * the scale of the noise term. Nothing here assumes the latencies are normal, and the band's
 * false-positive rate is not derived: ADR-059's AK3 is one A/A trial that can refute the band,
 * not a measured rate.
 */
export const MAD_NORMAL_CONSISTENCY = 1.4826;

/** How many MAD-scaled noise widths a row's median latency may rise before it regresses. */
export const LATENCY_NOISE_MULTIPLIER = 3;

/** A 40-character lowercase hexadecimal git object name, the form `github.sha` takes. */
const COMMIT_SHA = /^[0-9a-f]{40}$/;

/** Whether `value` names a commit the way `github.sha` does. */
export function isCommitSha(value: string): boolean {
  return COMMIT_SHA.test(value);
}

/**
 * The median of a sample set: its middle value, or the mean of its two middle values when the
 * count is even. Throws a `RangeError` on an empty set or a non-finite value, because a median
 * of nothing is not a measurement. The CI script reports a throw as a crash, which fails it.
 */
export function median(values: readonly number[]): number {
  if (values.length === 0) {
    throw new RangeError("the median of an empty sample set is undefined");
  }
  if (!values.every((value) => Number.isFinite(value))) {
    throw new RangeError("the median of a sample set holding a non-finite value is undefined");
  }
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  const upper = sorted[middle];
  const lower = sorted.length % 2 === 0 ? sorted[middle - 1] : upper;
  if (upper === undefined || lower === undefined) {
    throw new RangeError("the median index fell outside the sample set");
  }
  return (lower + upper) / 2;
}

/** The median absolute deviation about the median: the spread the noise term is scaled from. */
export function medianAbsoluteDeviation(values: readonly number[]): number {
  const center = median(values);
  return median(values.map((value) => Math.abs(value - center)));
}

/** One latency measurement, as the median rule reads it. */
export interface LatencyReading {
  readonly latencyMs: number;
}

/** One leg's latency for one row of a k-leg measurement. */
export interface LatencySample extends LatencyReading {
  /** The 1-based leg that measured it. */
  readonly leg: number;
  /** ISO-8601 UTC instant at which that leg captured the row. */
  readonly capturedAt: string;
}

/** Everything the median rule reports about one row (ADR-059). */
export interface LatencyJudgement {
  readonly job: JobToBeDone;
  /** `med_b`: the median of the baseline's samples. */
  readonly baselineMedian: number;
  /** `MAD_b`: the median absolute deviation of the baseline's samples, never pooled. */
  readonly baselineMad: number;
  /** `p * med_b`. */
  readonly relativeAllowance: number;
  /** `3 * 1.4826 * MAD_b`. */
  readonly noiseAllowance: number;
  /** `max(relativeAllowance, noiseAllowance)`: how far `med_f` may rise above `med_b`. */
  readonly allowance: number;
  /** `med_f`: the median of the fresh samples. */
  readonly freshMedian: number;
  /** `med_f - med_b > allowance`. */
  readonly regressed: boolean;
}

/**
 * The median rule for one row (ADR-059). `med_b` and `MAD_b` are computed from
 * `baselineSamples` alone: pooling the fresh samples into the MAD would widen the band by the
 * very shift the rule exists to detect (ADR-059, "Rejected alternatives").
 */
export function judgeLatency(
  job: JobToBeDone,
  baselineSamples: readonly LatencyReading[],
  freshSamples: readonly LatencyReading[],
  latencyPct: number,
): LatencyJudgement {
  const baselineValues = baselineSamples.map((sample) => sample.latencyMs);
  const baselineMedian = median(baselineValues);
  const baselineMad = medianAbsoluteDeviation(baselineValues);
  const freshMedian = median(freshSamples.map((sample) => sample.latencyMs));
  const relativeAllowance = latencyPct * baselineMedian;
  const noiseAllowance = LATENCY_NOISE_MULTIPLIER * MAD_NORMAL_CONSISTENCY * baselineMad;
  const allowance = Math.max(relativeAllowance, noiseAllowance);
  return {
    job,
    baselineMedian,
    baselineMad,
    relativeAllowance,
    noiseAllowance,
    allowance,
    freshMedian,
    regressed: freshMedian - baselineMedian > allowance,
  };
}

/** Which leg of the k-leg matrix produced a scorecard, and at which commit (ADR-059). */
export interface LegStamp {
  /** The leg's 1-based index in the matrix, 1..k (`matrix.leg`). */
  readonly index: number;
  /** k as the workflow ran it (`strategy.job-total`). */
  readonly count: number;
  /** The commit the leg checked out and measured (`github.sha`). */
  readonly commitSha: string;
}

/** One leg's row: the four metrics plus the stamps the emitter writes on every row. */
export interface LegRow extends ScorecardRow {
  readonly harnessVersion: string;
  readonly seed: number;
  readonly capturedAt: string;
}

/** One leg's complete scorecard, reduced to what the arrival proof and the rule read. */
export interface LegScorecard {
  readonly leg: LegStamp;
  readonly harnessVersion: string;
  readonly seed: number;
  readonly rows: readonly LegRow[];
  readonly interruptionPrecision: number | null;
}

/**
 * What is wrong with a leg stamp under a design of `legCount` legs; empty when it fits. One
 * rule for both places that judge a stamp: the leg's seal and the arrival proof.
 */
export function legStampProblems(stamp: LegStamp, legCount: number): readonly string[] {
  const problems: string[] = [];
  if (!Number.isInteger(stamp.index) || stamp.index < 1 || stamp.index > legCount) {
    problems.push(`leg index ${stamp.index} is not an integer in 1..${legCount}`);
  }
  if (stamp.count !== legCount) {
    problems.push(`the matrix ran ${stamp.count} leg(s) and this gate judges ${legCount}`);
  }
  if (!isCommitSha(stamp.commitSha)) {
    problems.push(`commit "${stamp.commitSha}" is not a 40-character lowercase hex sha`);
  }
  return problems;
}

/** Why k scorecards do not prove that k legs arrived (ADR-059). */
export type ArrivalFailureKind =
  | "leg-count"
  | "leg-stamp"
  | "duplicate-leg"
  | "missing-leg"
  | "mixed-commit"
  | "mixed-harness";

/** One named reason the arrival proof refused. */
export interface ArrivalFailure {
  readonly kind: ArrivalFailureKind;
  /** `leg <n>`, or `legs` for a finding about the whole set. */
  readonly subject: string;
  readonly detail: string;
}

/** The arrival proof's verdict: the k legs in index order, or every reason it refused. */
export type ArrivalVerdict =
  | {
      readonly outcome: "arrived";
      /** Exactly k scorecards, one per leg, sorted by leg index. */
      readonly legs: readonly LegScorecard[];
      readonly commitSha: string;
      readonly harnessVersion: string;
      readonly seed: number;
    }
  | { readonly outcome: "refused"; readonly failures: readonly ArrivalFailure[] };

/** An arrival the proof accepted: the only input {@link poolLegs} takes. */
export type ArrivedLegs = Extract<ArrivalVerdict, { readonly outcome: "arrived" }>;

function distinctValues<T>(values: readonly T[]): T[] {
  return [...new Set(values)];
}

/**
 * The arrival proof (ADR-059). Refuses unless EXACTLY `legCount` scorecards arrived, their leg
 * indices are exactly 1..legCount with none repeated, every stamp fits the design, and all of
 * them name one commit, one harness version and one master seed. A missing leg is a failure,
 * never a median of fewer. Every applicable reason is reported, not only the first.
 */
export function checkLegArrival(
  scorecards: readonly LegScorecard[],
  legCount: number,
): ArrivalVerdict {
  if (!Number.isInteger(legCount) || legCount < 1) {
    return {
      outcome: "refused",
      failures: [
        {
          kind: "leg-count",
          subject: "legs",
          detail: `a design of ${legCount} leg(s) cannot be judged; k must be a positive integer`,
        },
      ],
    };
  }

  const failures: ArrivalFailure[] = [];
  if (scorecards.length !== legCount) {
    failures.push({
      kind: "leg-count",
      subject: "legs",
      detail: `${scorecards.length} scorecard(s) arrived and the gate judges exactly ${legCount}, one per leg; a median of fewer legs is not this rule`,
    });
  }

  const claims = new Map<number, number>();
  for (const scorecard of scorecards) {
    const problems = legStampProblems(scorecard.leg, legCount);
    if (problems.length > 0) {
      failures.push({
        kind: "leg-stamp",
        subject: `leg ${scorecard.leg.index}`,
        detail: problems.join("; "),
      });
    }
    claims.set(scorecard.leg.index, (claims.get(scorecard.leg.index) ?? 0) + 1);
  }
  for (const [index, count] of claims) {
    if (count > 1) {
      failures.push({
        kind: "duplicate-leg",
        subject: `leg ${index}`,
        detail: `${count} scorecards claim leg ${index}; each leg is one distinct execution`,
      });
    }
  }
  for (let index = 1; index <= legCount; index += 1) {
    if (!claims.has(index)) {
      failures.push({
        kind: "missing-leg",
        subject: `leg ${index}`,
        detail: `no scorecard claims leg ${index} of ${legCount}`,
      });
    }
  }

  const commits = distinctValues(scorecards.map((scorecard) => scorecard.leg.commitSha));
  if (commits.length > 1) {
    failures.push({
      kind: "mixed-commit",
      subject: "legs",
      detail: `the scorecards name ${commits.length} commits (${commits.join(", ")}); the k legs must measure one commit`,
    });
  }
  const harnesses = distinctValues(
    scorecards.map((scorecard) => `${scorecard.harnessVersion} seed ${scorecard.seed}`),
  );
  if (harnesses.length > 1) {
    failures.push({
      kind: "mixed-harness",
      subject: "legs",
      detail: `the scorecards name ${harnesses.length} harnesses (${harnesses.join("; ")}); the k legs must run one harness version at one master seed`,
    });
  }

  const sorted = [...scorecards].sort((a, b) => a.leg.index - b.leg.index);
  const [first] = sorted;
  if (failures.length > 0 || first === undefined) {
    return { outcome: "refused", failures };
  }
  return {
    outcome: "arrived",
    legs: sorted,
    commitSha: first.leg.commitSha,
    harnessVersion: first.harnessVersion,
    seed: first.seed,
  };
}

/** A metric on which the k legs must agree exactly (ADR-059). */
export type LegDisagreementMetric =
  | "row"
  | "steps"
  | "errorRate"
  | "seed"
  | "harnessVersion"
  | "interruptionPrecision";

/** k legs that do not agree on a metric the harness claims is deterministic. */
export interface LegDisagreement {
  /** The job whose legs disagree, or the run-level `"interruption-precision"`. */
  readonly subject: RatchetSubject;
  readonly metric: LegDisagreementMetric;
  /** What each leg reported, in leg order. For `row`: how many rows the leg carried for the job. */
  readonly values: readonly { readonly leg: number; readonly value: number | string | null }[];
}

/** One job measured by k legs that agreed on everything but latency. */
export interface PooledRow {
  readonly job: JobToBeDone;
  readonly steps: number;
  readonly errorRate: number;
  readonly harnessVersion: string;
  readonly seed: number;
  /** One sample per leg, in leg order. */
  readonly latencySamples: readonly LatencySample[];
}

/** k legs pooled: one row per job in `JOB_ORDER`, each with k latency samples. */
export interface PooledMeasurement {
  readonly legCount: number;
  readonly commitSha: string;
  readonly harnessVersion: string;
  readonly seed: number;
  readonly rows: readonly PooledRow[];
  readonly interruptionPrecision: number | null;
}

/** The pooling verdict: one measurement, or every disagreement among the legs. */
export type PoolVerdict =
  | { readonly outcome: "pooled"; readonly measurement: PooledMeasurement }
  | { readonly outcome: "disagreed"; readonly disagreements: readonly LegDisagreement[] };

/** The row metrics the k legs must report identically. */
const AGREED_ROW_METRICS = ["steps", "errorRate", "seed", "harnessVersion"] as const;

/**
 * Pools an arrival into one measurement (ADR-059), or reports every disagreement. Each job must
 * appear exactly once in every leg, every leg must report the same `steps`, `errorRate`, row
 * seed and row harness version for it, and the same `interruptionPrecision` for the run.
 * Latency is the one metric allowed to differ: it becomes the row's k samples, in leg order.
 * Takes {@link ArrivedLegs} only, so a partial or mixed set cannot be pooled.
 */
export function poolLegs(arrived: ArrivedLegs): PoolVerdict {
  const disagreements: LegDisagreement[] = [];
  const rows: PooledRow[] = [];
  const jobs = JOB_ORDER.filter((job) =>
    arrived.legs.some((scorecard) => scorecard.rows.some((row) => row.job === job)),
  );

  for (const job of jobs) {
    const perLeg = arrived.legs.map((scorecard) => ({
      leg: scorecard.leg.index,
      matches: scorecard.rows.filter((row) => row.job === job),
    }));
    const present: { readonly leg: number; readonly row: LegRow }[] = [];
    for (const entry of perLeg) {
      const [row] = entry.matches;
      if (entry.matches.length === 1 && row !== undefined) present.push({ leg: entry.leg, row });
    }
    if (present.length !== perLeg.length) {
      disagreements.push({
        subject: job,
        metric: "row",
        values: perLeg.map((entry) => ({ leg: entry.leg, value: entry.matches.length })),
      });
      continue;
    }

    let agreed = true;
    for (const metric of AGREED_ROW_METRICS) {
      const values = present.map((entry) => ({ leg: entry.leg, value: entry.row[metric] }));
      if (distinctValues(values.map((entry) => entry.value)).length > 1) {
        disagreements.push({ subject: job, metric, values });
        agreed = false;
      }
    }
    const [head] = present;
    if (!agreed || head === undefined) continue;
    rows.push({
      job,
      steps: head.row.steps,
      errorRate: head.row.errorRate,
      harnessVersion: head.row.harnessVersion,
      seed: head.row.seed,
      latencySamples: present.map((entry) => ({
        leg: entry.leg,
        latencyMs: entry.row.latencyMs,
        capturedAt: entry.row.capturedAt,
      })),
    });
  }

  const precisions = arrived.legs.map((scorecard) => ({
    leg: scorecard.leg.index,
    value: scorecard.interruptionPrecision,
  }));
  if (distinctValues(precisions.map((entry) => entry.value)).length > 1) {
    disagreements.push({
      subject: "interruption-precision",
      metric: "interruptionPrecision",
      values: precisions,
    });
  }

  if (disagreements.length > 0) return { outcome: "disagreed", disagreements };
  const [firstLeg] = arrived.legs;
  return {
    outcome: "pooled",
    measurement: {
      legCount: arrived.legs.length,
      commitSha: arrived.commitSha,
      harnessVersion: arrived.harnessVersion,
      seed: arrived.seed,
      rows,
      interruptionPrecision: firstLeg === undefined ? null : firstLeg.interruptionPrecision,
    },
  };
}

/** A k-sample row as the median rule reads it: a committed baseline row or a pooled row. */
export interface KSampleRow {
  readonly job: JobToBeDone;
  readonly steps: number;
  readonly errorRate: number;
  readonly latencySamples: readonly LatencyReading[];
}

/** A k-sample measurement: the committed baseline, or a pooled fresh run. */
export interface KSampleMeasurement {
  readonly rows: readonly KSampleRow[];
  readonly interruptionPrecision: number | null;
}

/** The k-leg verdict: a {@link RatchetResult} plus the latency judgement behind each row. */
export interface LegRatchetResult extends RatchetResult {
  /** One judgement per compared job, in fresh-row order. */
  readonly latency: readonly LatencyJudgement[];
}

/**
 * The CI gate's comparator (ADR-059). `steps`, `errorRate` and `interruptionPrecision` are
 * judged by the same code as {@link compareScorecard}. Latency regresses on a row iff
 * `med_f - med_b > max(p * med_b, 3 * 1.4826 * MAD_b)`, with `med_b` and `MAD_b` taken from the
 * baseline's samples only ({@link judgeLatency}). It does not re-check that both sides carry k
 * samples per row: {@link checkLegArrival} and the baseline check enforce that before this is
 * called, and an empty sample set throws rather than reading as a pass.
 */
export function compareLegMedians(
  baseline: KSampleMeasurement,
  fresh: KSampleMeasurement,
  tol: RatchetTolerance,
): LegRatchetResult {
  const latency: LatencyJudgement[] = [];
  const result = ratchetRows<KSampleRow>(
    baseline.rows,
    fresh.rows,
    baseline.interruptionPrecision,
    fresh.interruptionPrecision,
    tol,
    (base, observed) => {
      const judgement = judgeLatency(
        observed.job,
        base.latencySamples,
        observed.latencySamples,
        tol.latencyPct,
      );
      latency.push(judgement);
      return {
        baseline: judgement.baselineMedian,
        observed: judgement.freshMedian,
        verdict: {
          worse: judgement.freshMedian > judgement.baselineMedian,
          regressed: judgement.regressed,
        },
      };
    },
  );
  return { ...result, latency };
}
