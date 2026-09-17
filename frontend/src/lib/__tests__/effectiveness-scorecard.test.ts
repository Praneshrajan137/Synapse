import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  EFFECTIVENESS_HARNESS_SEED,
  EFFECTIVENESS_HARNESS_VERSION,
  JOB_ORDER,
  type JobToBeDone,
  SCORECARD_SCHEMA_VERSION,
  SCRIPTED_PROXY_CEILING,
  type ScorecardRow,
  buildMeasuredScorecard,
  buildScorecard,
  parseScorecard,
  serializeScorecard,
} from "../effectiveness-scorecard";
import {
  type ConfirmedStake,
  InterruptionPrecisionUnavailableError,
  type RunContext,
  type SealedInterruptionLedger,
  computeInterruptionPrecision,
  findCommittedInterruptionLiterals,
  openInterruptionLedger,
  requireComputedOutcome,
} from "../interruption-precision";

/**
 * Unit coverage for the shared Effectiveness_Scorecard type/serialization
 * (task 4.1). The pure ratchet comparator that consumes this shape is a
 * separate task (4.2) with its own property test (4.3); these tests guard the
 * emitter contract and the committed baseline artifact.
 *
 * R8.5 / task 11.5 rewrote one assertion in this file. The committed baseline's
 * `interruptionPrecision` used to be compared against `seededInterruptionPrecision()`
 * -- a helper that returned the same hand-authored ratio the baseline recorded, so
 * the assertion compared a literal to itself and held no matter what the Console
 * did. The helper is deleted and the comparison with it; what replaces it asserts
 * the DERIVATION instead: the measured value enters a scorecard only through
 * `buildMeasuredScorecard`, from a run's own sealed interruption ledger. The
 * property test for the metric's seed responsiveness is task 11.6 (Property 34).
 */

const sampleRows: readonly ScorecardRow[] = [
  { job: "catch-disruption-before-cascade", steps: 7, latencyMs: 4200, errorRate: 0 },
  { job: "resolve-escalation-correctly", steps: 5, latencyMs: 3100, errorRate: 0 },
  { job: "adjust-steering-safely", steps: 6, latencyMs: 2800, errorRate: 0 },
];

// ---------------------------------------------------------------------------
// A measured run, for the R8.5 ingress
// ---------------------------------------------------------------------------

const NO_STAKES: readonly ConfirmedStake[] = [];

const measuredRun: RunContext = {
  runId: "scorecard-unit-run",
  seed: 40404,
  harnessVersion: "9.9.9",
  startedAt: "2026-06-17T09:41:02.184Z",
};

/**
 * A sealed ledger holding `outcomeChanging` interruptions whose review changed
 * the decision's outcome (warranted, derived -- never asserted) followed by
 * `inert` interruptions that changed nothing and confirmed no stake
 * (unwarranted). The clock is a counter so the records are monotonic inside the
 * run's window without touching a real timer.
 */
function sealLedger(outcomeChanging: number, inert: number): SealedInterruptionLedger {
  let tick = 0;
  const ledger = openInterruptionLedger(measuredRun, () => {
    tick += 1;
    return tick;
  });
  for (let index = 0; index < outcomeChanging + inert; index += 1) {
    ledger.record({
      interruptionId: `escalation-${index}`,
      scenarioId: "jtbd.resolve-escalation",
      outcomeChanged: index < outcomeChanging,
      confirmedStakes: NO_STAKES,
      evidence: `operator response ${index} observed in the seeded scenario`,
    });
  }
  return ledger.seal();
}

describe("buildScorecard", () => {
  it("stamps defaults and carries no precision until a run measures one", () => {
    const sc = buildScorecard({ rows: sampleRows });
    expect(sc.schemaVersion).toBe(SCORECARD_SCHEMA_VERSION);
    expect(sc.harnessVersion).toBe(EFFECTIVENESS_HARNESS_VERSION);
    expect(sc.seed).toBe(EFFECTIVENESS_HARNESS_SEED);
    expect(sc.interruptionPrecision).toBeNull();
    expect(sc.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
  });

  it("sorts rows into the canonical JOB_ORDER regardless of input order", () => {
    const sc = buildScorecard({ rows: sampleRows });
    const emitted = sc.rows.map((r) => r.job);
    const expected = JOB_ORDER.filter((j) => sampleRows.some((r) => r.job === j));
    expect(emitted).toEqual(expected);
  });
});

describe("serializeScorecard", () => {
  it("is deterministic and order-independent (byte-stable for a fixed seed)", () => {
    const a = serializeScorecard(buildScorecard({ rows: sampleRows }));
    const shuffled = [...sampleRows].reverse();
    const b = serializeScorecard(buildScorecard({ rows: shuffled }));
    expect(a).toBe(b);
  });

  it("round-trips a measured scorecard through parseScorecard", () => {
    // Built through the measured ingress, so the round-trip covers the value a
    // run actually computes rather than a number typed into this test.
    const outcome = requireComputedOutcome(computeInterruptionPrecision(sealLedger(3, 1)));
    const sc = buildMeasuredScorecard({ rows: sampleRows, precision: outcome });
    const parsed = parseScorecard(serializeScorecard(sc));
    expect(parsed).toEqual(sc);
    expect(parsed.interruptionPrecision).toBe(outcome.value);
  });
});

describe("parseScorecard", () => {
  it("rejects a scorecard with an unknown job", () => {
    const bad = JSON.stringify({
      schemaVersion: 1,
      harnessVersion: "1.0.0",
      seed: 30000,
      rows: [{ job: "not-a-real-job", steps: 1, latencyMs: 1, errorRate: 0 }],
      interruptionPrecision: null,
      proxyCeiling: SCRIPTED_PROXY_CEILING,
    });
    expect(() => parseScorecard(bad)).toThrow(/Invalid EffectivenessScorecard/);
  });
});

describe("committed baseline artifact", () => {
  const baselinePath = resolve(process.cwd(), "spec/effectiveness/scorecard.baseline.json");

  it("parses and covers every enumerated Job_To_Be_Done exactly once", () => {
    const baseline = parseScorecard(readFileSync(baselinePath, "utf8"));
    const jobs = baseline.rows.map((r) => r.job);
    expect(new Set(jobs)).toEqual(new Set<JobToBeDone>(JOB_ORDER));
    expect(jobs).toHaveLength(JOB_ORDER.length);
    expect(baseline.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
  });

  it("has its interruptionPrecision judged elsewhere, not by comparison to a constant", () => {
    const baseline = parseScorecard(readFileSync(baselinePath, "utf8"));
    // R8.5: a number in a committed file is not a measurement, and this test
    // cannot make it one. So it asserts only that the field is inside the
    // schema's domain and deliberately asserts NOTHING about its magnitude --
    // pinning the magnitude here is what made the removed assertion vacuous.
    // Two checks this file cannot stand in for decide what the committed value
    // is worth: `auditSeedResponsiveness`, which a seed-invariant constant fails
    // by construction, and the baseline check (`@lib/effectiveness-baseline`,
    // R8.10), which already rejects this artifact's unstamped, uniform rows.
    const committed = baseline.interruptionPrecision;
    expect(committed === null || (committed >= 0 && committed <= 1)).toBe(true);
  });
});

describe("buildMeasuredScorecard (R8.5 -- the measured ingress)", () => {
  it("records warranted / total over the run's own collected interruptions", () => {
    // Three reviews changed the outcome, one changed nothing: 3 / 4. The audit
    // found this same ratio as a committed literal; here it exists only because
    // four interruptions were RECORDED, and it moves the moment they differ.
    const outcome = requireComputedOutcome(computeInterruptionPrecision(sealLedger(3, 1)));
    const sc = buildMeasuredScorecard({ rows: sampleRows, precision: outcome });
    expect(sc.interruptionPrecision).toBe(0.75);
    expect(outcome.warranted).toBe(3);
    expect(outcome.total).toBe(4);
  });

  it("responds to a different interruption set from the same emitter", () => {
    const half = requireComputedOutcome(computeInterruptionPrecision(sealLedger(2, 2)));
    const sc = buildMeasuredScorecard({ rows: sampleRows, precision: half });
    expect(sc.interruptionPrecision).toBe(0.5);
  });

  it("stamps the measuring run's seed and harness version, not the module defaults", () => {
    const outcome = requireComputedOutcome(computeInterruptionPrecision(sealLedger(1, 1)));
    const sc = buildMeasuredScorecard({ rows: sampleRows, precision: outcome });
    expect(sc.seed).toBe(measuredRun.seed);
    expect(sc.harnessVersion).toBe(measuredRun.harnessVersion);
    expect(sc.seed).not.toBe(EFFECTIVENESS_HARNESS_SEED);
    expect(sc.harnessVersion).not.toBe(EFFECTIVENESS_HARNESS_VERSION);
    expect(sc.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
  });

  it("cannot be reached when the run collected no interruption", () => {
    const outcome = computeInterruptionPrecision(sealLedger(0, 0));
    expect(outcome.status).toBe("indeterminate");
    // There is no narrowing to the measured ingress and no null to record: the
    // caller throws and the effectiveness job fails with the reason (I-7).
    let thrown: unknown = null;
    try {
      requireComputedOutcome(outcome);
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeInstanceOf(InterruptionPrecisionUnavailableError);
    expect((thrown as InterruptionPrecisionUnavailableError).reason).toBe(
      "no-interruptions-collected",
    );
  });

  it("leaves no committed interruption data in the module the value lands in", () => {
    // Mechanism 3 turned on its own scope: the file that owns the scorecard shape
    // must itself hold no authored warrant flag, committed interruption list, or
    // numeric literal assigned to the metric.
    const modulePath = resolve(process.cwd(), "src/lib/effectiveness-scorecard.ts");
    expect(findCommittedInterruptionLiterals(readFileSync(modulePath, "utf8"))).toEqual([]);
  });
});
