import fc from "fast-check";
import { describe, expect, it } from "vitest";
import {
  DEFAULT_RATCHET_TOLERANCE,
  type RatchetTolerance,
  compareScorecard,
} from "../effectiveness-ratchet";
import {
  type EffectivenessScorecard,
  JOB_ORDER,
  type JobToBeDone,
  type ScorecardRow,
  buildScorecard,
} from "../effectiveness-scorecard";

// Feature: atlas-console-effectiveness
// Property 5: The ratchet fails iff some job's steps/latency/error-rate
// regresses beyond tolerance relative to baseline, and an improvement permits a
// monotonic baseline advance.
//
// `compareScorecard(baseline, fresh, tol)` is pure. It compares a fresh
// scorecard against a committed baseline job-by-job (matched by name; a fresh
// job with no baseline counterpart is skipped). A metric REGRESSES iff it moves
// in its worsening direction by MORE than its tolerance relative to baseline:
//   • steps      — lower-better, RELATIVE:  observed > baseline·(1 + stepsPct)
//   • latencyMs  — lower-better, RELATIVE:  observed > baseline·(1 + latencyPct)
//   • errorRate  — lower-better, ABSOLUTE:  observed > baseline + errorRateAbs
//   • interruptionPrecision — higher-better, ABSOLUTE: observed < baseline −
//     interruptionPrecisionAbs, compared ONLY when both scorecards carry a value.
// The verdict `passed` is true iff `regressions` is empty. `canAdvanceBaseline`
// is set exactly when EVERY comparable metric improved or held — i.e. no metric
// moved in the worsening direction AT ALL, even within tolerance (a strictly
// stronger condition than `passed`), so the ratchet advances monotonically.
//
// **Validates: Requirements 4.3, 4.4, 4.5**

// ── Generators ──────────────────────────────────────────────────────────────

const arbMetrics = fc.record({
  steps: fc.integer({ min: 1, max: 40 }),
  latencyMs: fc.integer({ min: 100, max: 20_000 }),
  errorRate: fc.double({ min: 0, max: 0.6, noNaN: true }),
});

/** A tolerance with non-degenerate ranges, plus the shipped default sometimes. */
const arbTolerance: fc.Arbitrary<RatchetTolerance> = fc.oneof(
  fc.constant(DEFAULT_RATCHET_TOLERANCE),
  fc.record({
    stepsPct: fc.double({ min: 0, max: 0.5, noNaN: true }),
    latencyPct: fc.double({ min: 0, max: 0.5, noNaN: true }),
    errorRateAbs: fc.double({ min: 0, max: 0.1, noNaN: true }),
    interruptionPrecisionAbs: fc.double({ min: 0, max: 0.1, noNaN: true }),
  }),
);

const arbIp: fc.Arbitrary<number | null> = fc.oneof(
  fc.constant<number | null>(null),
  fc.double({ min: 0, max: 1, noNaN: true }),
);

/**
 * Generates a baseline scorecard and a fresh scorecard over a shared, matching
 * job set (so the comparator actually compares them), plus optional fresh-only
 * jobs (which must be skipped). Each fresh metric is derived from its baseline
 * value by a signed delta so improvements, holds, within-tolerance drifts, and
 * beyond-tolerance regressions all occur.
 */
const arbScorecardPair = fc
  .uniqueArray(fc.constantFrom<JobToBeDone>(...JOB_ORDER), {
    minLength: 1,
    maxLength: JOB_ORDER.length,
  })
  .chain((jobs) =>
    fc.record({
      jobs: fc.constant(jobs),
      baseMetrics: fc.array(arbMetrics, { minLength: jobs.length, maxLength: jobs.length }),
      // Multipliers/deltas that move fresh around baseline in both directions.
      stepDelta: fc.array(fc.integer({ min: -10, max: 15 }), {
        minLength: jobs.length,
        maxLength: jobs.length,
      }),
      latencyMul: fc.array(fc.double({ min: 0.5, max: 1.8, noNaN: true }), {
        minLength: jobs.length,
        maxLength: jobs.length,
      }),
      errorDelta: fc.array(fc.double({ min: -0.3, max: 0.3, noNaN: true }), {
        minLength: jobs.length,
        maxLength: jobs.length,
      }),
      baseIp: arbIp,
      freshIp: arbIp,
      tol: arbTolerance,
    }),
  )
  .map((g) => {
    const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));
    const baselineRows: ScorecardRow[] = g.jobs.map((job, i) => {
      const m = g.baseMetrics[i]!;
      return { job, steps: m.steps, latencyMs: m.latencyMs, errorRate: clamp01(m.errorRate) };
    });
    const freshRows: ScorecardRow[] = g.jobs.map((job, i) => {
      const b = baselineRows[i]!;
      return {
        job,
        steps: Math.max(0, b.steps + g.stepDelta[i]!),
        latencyMs: Math.max(0, Math.round(b.latencyMs * g.latencyMul[i]!)),
        errorRate: clamp01(b.errorRate + g.errorDelta[i]!),
      };
    });
    const baseline = buildScorecard({ rows: baselineRows, interruptionPrecision: g.baseIp });
    const fresh = buildScorecard({ rows: freshRows, interruptionPrecision: g.freshIp });
    return { baseline, fresh, tol: g.tol };
  });

// ── Reference oracle (independent of the implementation) ─────────────────────

interface OracleRegression {
  readonly job: string;
  readonly metric: string;
  readonly baseline: number;
  readonly observed: number;
}

function oracle(
  baseline: EffectivenessScorecard,
  fresh: EffectivenessScorecard,
  tol: RatchetTolerance,
): { regressions: OracleRegression[]; anyWorse: boolean } {
  const byJob = new Map<JobToBeDone, ScorecardRow>(baseline.rows.map((r) => [r.job, r]));
  const regressions: OracleRegression[] = [];
  let anyWorse = false;

  const consider = (
    job: string,
    metric: string,
    base: number,
    obs: number,
    worse: boolean,
    regressed: boolean,
  ): void => {
    if (worse) anyWorse = true;
    if (regressed) regressions.push({ job, metric, baseline: base, observed: obs });
  };

  for (const f of fresh.rows) {
    const b = byJob.get(f.job);
    if (b === undefined) continue; // fresh-only job: skipped
    consider(
      f.job,
      "steps",
      b.steps,
      f.steps,
      f.steps > b.steps,
      f.steps > b.steps * (1 + tol.stepsPct),
    );
    consider(
      f.job,
      "latencyMs",
      b.latencyMs,
      f.latencyMs,
      f.latencyMs > b.latencyMs,
      f.latencyMs > b.latencyMs * (1 + tol.latencyPct),
    );
    consider(
      f.job,
      "errorRate",
      b.errorRate,
      f.errorRate,
      f.errorRate > b.errorRate,
      f.errorRate > b.errorRate + tol.errorRateAbs,
    );
  }

  const bIp = baseline.interruptionPrecision;
  const fIp = fresh.interruptionPrecision;
  if (bIp !== null && fIp !== null) {
    consider(
      "interruption-precision",
      "interruptionPrecision",
      bIp,
      fIp,
      fIp < bIp,
      fIp < bIp - tol.interruptionPrecisionAbs,
    );
  }
  return { regressions, anyWorse };
}

/** A stable key for comparing regression sets regardless of array order. */
const regKey = (r: { job: string; metric: string }): string => `${r.job}::${r.metric}`;

describe("Property 5: the ratchet fails iff a metric regresses beyond tolerance, and improvement permits a monotonic advance", () => {
  it("passed is true iff there are no regressions", () => {
    fc.assert(
      fc.property(arbScorecardPair, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        expect(result.passed).toBe(result.regressions.length === 0);
      }),
      { numRuns: 100 },
    );
  });

  it("the regression set exactly matches the beyond-tolerance oracle (the iff)", () => {
    fc.assert(
      fc.property(arbScorecardPair, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        const expected = oracle(baseline, fresh, tol);

        const actualKeys = new Set(result.regressions.map(regKey));
        const expectedKeys = new Set(expected.regressions.map(regKey));
        expect(actualKeys).toEqual(expectedKeys);
        // The count matches too (no duplicate/missing named regressions).
        expect(result.regressions.length).toBe(expected.regressions.length);
      }),
      { numRuns: 100 },
    );
  });

  it("every reported regression names its job/metric with the true baseline and observed values", () => {
    fc.assert(
      fc.property(arbScorecardPair, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        const expected = oracle(baseline, fresh, tol);
        const expectedByKey = new Map(expected.regressions.map((r) => [regKey(r), r]));

        for (const reg of result.regressions) {
          const match = expectedByKey.get(regKey(reg));
          expect(match).toBeDefined();
          expect(reg.baseline).toBe(match!.baseline);
          expect(reg.observed).toBe(match!.observed);
          // The observed value genuinely worsened relative to baseline.
          if (reg.metric === "interruptionPrecision") {
            expect(reg.observed).toBeLessThan(reg.baseline);
          } else {
            expect(reg.observed).toBeGreaterThan(reg.baseline);
          }
        }
      }),
      { numRuns: 100 },
    );
  });

  it("canAdvanceBaseline is set iff no comparable metric moved in the worsening direction at all", () => {
    fc.assert(
      fc.property(arbScorecardPair, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        const expected = oracle(baseline, fresh, tol);
        expect(result.canAdvanceBaseline).toBe(!expected.anyWorse);
      }),
      { numRuns: 100 },
    );
  });

  it("canAdvanceBaseline implies passed (advancing is strictly stronger than passing)", () => {
    fc.assert(
      fc.property(arbScorecardPair, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        if (result.canAdvanceBaseline) {
          expect(result.passed).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("a pure improvement/hold (every metric ≤ baseline, IP ≥ baseline) passes and permits a monotonic advance", () => {
    const arbImproving = fc
      .uniqueArray(fc.constantFrom<JobToBeDone>(...JOB_ORDER), {
        minLength: 1,
        maxLength: JOB_ORDER.length,
      })
      .chain((jobs) =>
        fc.record({
          jobs: fc.constant(jobs),
          baseMetrics: fc.array(arbMetrics, { minLength: jobs.length, maxLength: jobs.length }),
          // Non-negative reductions toward better (or equal) values.
          stepDrop: fc.array(fc.integer({ min: 0, max: 20 }), {
            minLength: jobs.length,
            maxLength: jobs.length,
          }),
          latencyDrop: fc.array(fc.integer({ min: 0, max: 10_000 }), {
            minLength: jobs.length,
            maxLength: jobs.length,
          }),
          errorDrop: fc.array(fc.double({ min: 0, max: 0.6, noNaN: true }), {
            minLength: jobs.length,
            maxLength: jobs.length,
          }),
          baseIp: fc.double({ min: 0, max: 0.9, noNaN: true }),
          ipGain: fc.double({ min: 0, max: 0.1, noNaN: true }),
          tol: arbTolerance,
        }),
      )
      .map((g) => {
        const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));
        const baselineRows: ScorecardRow[] = g.jobs.map((job, i) => {
          const m = g.baseMetrics[i]!;
          return { job, steps: m.steps, latencyMs: m.latencyMs, errorRate: clamp01(m.errorRate) };
        });
        const freshRows: ScorecardRow[] = g.jobs.map((job, i) => {
          const b = baselineRows[i]!;
          return {
            job,
            steps: Math.max(0, b.steps - g.stepDrop[i]!),
            latencyMs: Math.max(0, b.latencyMs - g.latencyDrop[i]!),
            errorRate: Math.max(0, b.errorRate - g.errorDrop[i]!),
          };
        });
        const baseIp = clamp01(g.baseIp);
        const baseline = buildScorecard({ rows: baselineRows, interruptionPrecision: baseIp });
        const fresh = buildScorecard({
          rows: freshRows,
          interruptionPrecision: clamp01(baseIp + g.ipGain),
        });
        return { baseline, fresh, tol: g.tol };
      });

    fc.assert(
      fc.property(arbImproving, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        expect(result.regressions).toHaveLength(0);
        expect(result.passed).toBe(true);
        expect(result.canAdvanceBaseline).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it("interruption_precision is neutral when either scorecard's value is null", () => {
    const arbMixedIp = arbScorecardPair.chain(({ baseline, fresh, tol }) =>
      fc
        .record({
          baseNull: fc.boolean(),
          freshNull: fc.boolean(),
        })
        .map(({ baseNull, freshNull }) => {
          const b = buildScorecard({
            rows: [...baseline.rows],
            interruptionPrecision: baseNull ? null : (baseline.interruptionPrecision ?? 0.5),
          });
          const f = buildScorecard({
            rows: [...fresh.rows],
            interruptionPrecision: freshNull ? null : (fresh.interruptionPrecision ?? 0.5),
          });
          return { baseline: b, fresh: f, tol, atLeastOneNull: baseNull || freshNull };
        }),
    );

    fc.assert(
      fc.property(arbMixedIp, ({ baseline, fresh, tol, atLeastOneNull }) => {
        const result = compareScorecard(baseline, fresh, tol);
        if (atLeastOneNull) {
          // No regression is ever attributed to interruption-precision, and it
          // does not block a baseline advance, when either side is null.
          expect(result.regressions.some((r) => r.metric === "interruptionPrecision")).toBe(false);
        }
      }),
      { numRuns: 100 },
    );
  });

  it("a fresh-only job with no baseline counterpart is never ratcheted", () => {
    const arbFreshOnly = fc
      .record({
        // baseline covers only the first job; fresh adds a second, baseline-less job
        baseMetrics: arbMetrics,
        freshExtra: arbMetrics,
        tol: arbTolerance,
      })
      .map((g) => {
        const jobA = JOB_ORDER[0]!;
        const jobB = JOB_ORDER[1]!;
        const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));
        const baseline = buildScorecard({
          rows: [
            {
              job: jobA,
              steps: g.baseMetrics.steps,
              latencyMs: g.baseMetrics.latencyMs,
              errorRate: clamp01(g.baseMetrics.errorRate),
            },
          ],
          interruptionPrecision: null,
        });
        // Fresh keeps jobA identical (no regression) and adds a worst-case jobB
        // that has no baseline — it must be ignored, not flagged.
        const fresh = buildScorecard({
          rows: [
            {
              job: jobA,
              steps: g.baseMetrics.steps,
              latencyMs: g.baseMetrics.latencyMs,
              errorRate: clamp01(g.baseMetrics.errorRate),
            },
            {
              job: jobB,
              steps: g.freshExtra.steps + 1000,
              latencyMs: g.freshExtra.latencyMs + 1_000_000,
              errorRate: 1,
            },
          ],
          interruptionPrecision: null,
        });
        return { baseline, fresh, tol: g.tol };
      });

    fc.assert(
      fc.property(arbFreshOnly, ({ baseline, fresh, tol }) => {
        const result = compareScorecard(baseline, fresh, tol);
        // The baseline-less jobB never appears in the regressions.
        expect(result.regressions.some((r) => r.job === JOB_ORDER[1])).toBe(false);
        // jobA held exactly → clean pass and advance.
        expect(result.passed).toBe(true);
        expect(result.canAdvanceBaseline).toBe(true);
      }),
      { numRuns: 100 },
    );
  });
});
