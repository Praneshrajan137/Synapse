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
  buildScorecard,
  parseScorecard,
  serializeScorecard,
} from "../effectiveness-scorecard";
import { seededInterruptionPrecision } from "../interruption-precision";

/**
 * Unit coverage for the shared Effectiveness_Scorecard type/serialization
 * (task 4.1). The pure ratchet comparator that consumes this shape is a
 * separate task (4.2) with its own property test (4.3); these tests guard the
 * emitter contract and the committed baseline artifact.
 */

const sampleRows: readonly ScorecardRow[] = [
  { job: "catch-disruption-before-cascade", steps: 7, latencyMs: 4200, errorRate: 0 },
  { job: "resolve-escalation-correctly", steps: 5, latencyMs: 3100, errorRate: 0 },
  { job: "adjust-steering-safely", steps: 6, latencyMs: 2800, errorRate: 0 },
];

describe("buildScorecard", () => {
  it("stamps defaults and reserves interruptionPrecision as null", () => {
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

  it("round-trips through parseScorecard", () => {
    const sc = buildScorecard({ rows: sampleRows, interruptionPrecision: 0.75 });
    const parsed = parseScorecard(serializeScorecard(sc));
    expect(parsed).toEqual(sc);
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
    // Task 15 wired the North-Star measurement: the committed baseline carries
    // the seeded Interruption_Precision so the ratchet can gate it (Req 13.3).
    // A `null` baseline would defeat the gate (it is compared only when both
    // baseline and fresh carry a value), so the baseline is intentionally
    // populated rather than reserved-null here.
    expect(baseline.interruptionPrecision).toBe(seededInterruptionPrecision());
    expect(baseline.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
  });
});
