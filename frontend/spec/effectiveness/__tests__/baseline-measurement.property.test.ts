/**
 * Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
 *
 * Validates: Requirements 8.10
 *
 * Property-based verification of the COMMITTED effectiveness baseline's rules (design
 * "Property 36: A baseline is a measurement, not a ceiling"; ADR-059 for the k-leg format).
 * R8.10: "THE committed baseline SHALL record, for each row, the `harnessVersion`, the `seed`,
 * and the timestamp of the run that produced that row, SHALL retain the `proxyCeiling`
 * statement, and IF every row carries an identical `steps` value and an identical `latencyMs`
 * value, THEN THE baseline check SHALL fail the baseline as an authored ceiling rather than
 * accept it as a measurement". ADR-059 (operator decision S13.2=a) makes a baseline a
 * measurement of k = 5 harness legs of one commit: schema version 2, one latency sample per leg
 * per row with its capture instant, each row's `latencyMs` the median of its samples, and the
 * one-run format refused by name.
 *
 * ## What is universally quantified
 *
 * Over baseline CANDIDATES built from the shared `baselineCaseArb` (`../arbitraries.ts`): a
 * five-row document, one row per declared Job_To_Be_Done, carrying at most one injected
 * `BaselineDefect` (`none | missing-stamp | absent-ceiling | uniform-metrics`). This file
 * spreads each generated row's latency over k samples (`samplesAround`): the drawn latency is
 * the centre on leg 1, (k - 1) / 2 samples lie at or above it and as many at or below it, so the
 * drawn latency IS the row's median by construction and every candidate stays a function of the
 * shared generator. The commit is drawn too. Facets needing a finer choice quantify over it --
 * which row, which stamp, which leg, which leg-set defect, the framing whitespace of the
 * ceiling. The rejection-kind facet ENUMERATES the kinds rather than sampling them, so its
 * reachability claim is deterministic.
 *
 * The subjects are the shipped validator and constructor in `@lib/effectiveness-baseline`,
 * driven directly. The thresholds are the COMMITTED ones, read from
 * `infrastructure/quality/effectiveness-baseline.json` through `loadBaselinePolicy` (AD-13), so
 * a weakened policy shows up as a failing facet rather than a test agreeing with itself. No facet
 * states a run budget: the count is inherited from `HYPOTHESIS_PROFILE` through
 * `fc.configureGlobal` in `frontend/src/test/setup.ts` (R3.1-R3.3).
 *
 * ## The facets
 *
 *   1. GUARD -- the policy came from the committed file and its rule is evaluable by five rows,
 *      and the format constants are the decision's: version 2 read, version 1 refused, k odd
 *      (which `samplesAround` needs for the drawn latency to be the median).
 *   2. GUARD -- every `BaselineDefect` the shared generator declares is drawn and carries the
 *      defect it names. Without this the defect facets could pass vacuously.
 *   3. `buildBaseline` turns k agreeing legs into a baseline that validates clean: one sample
 *      per leg per row, the median as the row's latency, and byte-for-byte the document a reader
 *      would assemble by hand from the same legs.
 *   4. `buildBaseline` REFUSES fewer than k legs, a duplicated leg, and legs that disagree: it
 *      cannot make a baseline the arrival proof would not accept.
 *   5. The one-run format is refused BY NAME, whatever its rows carry.
 *   6. An AUTHORED CEILING -- identical `steps` and identical median latencies on every row -- is
 *      `uniform-metrics`, and the same rows spread apart are accepted.
 *   7. The same claim on raw generator output, with the generator's sharp edge stated (below).
 *   8. A missing stamp -- a row's harness version or seed, one sample's capture instant, or the
 *      document's commit -- is `missing-stamp`, attributed to its row (or `null`) and naming it.
 *   9. A row whose samples are not exactly legs 1..k, or a document of another leg count, is
 *      `leg-set`.
 *  10. A row whose `latencyMs` is not the median of its samples is `median-mismatch`.
 *  11. An absent or blank `proxyCeiling` is `absent-ceiling`.
 *  12. `proxyCeiling` is kept VERBATIM, and the committed-artifact rule rejects a non-canonical
 *      statement as `altered-ceiling` instead of silently replacing it.
 *  13. The canonical round trip is byte-stable, and independent of row and sample order.
 *  14. Below `min_rows` the distinctness rule is UNEVALUABLE, which is `insufficient-rows`.
 *  15. TOTALITY: no input makes the validator throw; anything that is not a baseline document --
 *      including one-run rows under the k-leg version -- is `malformed`.
 *  16. Every `BaselineRejectionKind` is reachable and NAMED.
 *
 * ## The generator's sharp edge, and how this file handles it (I-7)
 *
 * `baselineCaseArb`'s `none` case draws each row's `steps` and `latencyMs` independently, so it
 * can -- with small but non-zero probability -- draw a row set uniform in BOTH columns. That
 * candidate declares no defect yet is legitimately rejected as `uniform-metrics`: the rule is
 * right and the generator is not wrong either. So facet 3 and every facet needing a clean
 * baseline map the drawn metrics through `withDistinctMetrics` (running totals of the drawn
 * values, which strictly increase), and facet 7 keeps the raw case and asserts the narrow
 * disjunction: accepted, OR rejected SOLELY as `uniform-metrics` on a row set it independently
 * confirms is uniform.
 *
 * ## What this file deliberately does NOT assert
 *
 * That the committed `frontend/spec/effectiveness/scorecard.baseline.json` is valid. Today it is
 * the one-run placeholder, which the check refuses as `one-run-format`; it clears when the k-leg
 * candidate a CI run writes through `buildBaseline` is committed over it unedited. Pinning the
 * artifact as passing or failing here would make this file a snapshot of a state instead of a
 * statement of the rule, so `checkCommittedBaseline` is exercised on GENERATED input.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  assembleBaselineDocument,
  BASELINE_SCHEMA_VERSION,
  type BaselinePolicy,
  type BaselineRejectionKind,
  type BaselineVerdict,
  buildBaseline,
  checkCommittedBaseline,
  ONE_RUN_BASELINE_SCHEMA_VERSION,
  serializeBaseline,
  validateBaseline,
  validateBaselineText,
} from "@lib/effectiveness-baseline";
import {
  EFFECTIVENESS_LEG_COUNT,
  type LegRow,
  type LegScorecard,
} from "@lib/effectiveness-ratchet";
import { JOB_ORDER, type JobToBeDone, SCRIPTED_PROXY_CEILING } from "@lib/effectiveness-scorecard";
import { canonicalJson } from "@lib/json-canonical";

import {
  type BaselineCase,
  baselineCaseArb,
  type BaselineDefect,
  type CapturedScorecardRow,
} from "../arbitraries";
import { BASELINE_POLICY_RELPATH, loadBaselinePolicy } from "../check-baseline";

// ---------------------------------------------------------------------------
// The committed policy (AD-13) -- read, never restated
// ---------------------------------------------------------------------------

/**
 * The thresholds the production check uses, loaded from
 * `infrastructure/quality/effectiveness-baseline.json` at module scope. A missing or
 * rule-disabling policy throws here and fails the whole file, which is the honest outcome: a
 * check that cannot read its own thresholds has not passed (I-7).
 */
const POLICY: BaselinePolicy = loadBaselinePolicy();

// ---------------------------------------------------------------------------
// Total enumerations of the unions under test
// ---------------------------------------------------------------------------

/**
 * Every {@link BaselineRejectionKind}. The `Record` annotation makes totality a compile-time
 * obligation: a kind added to the union fails to typecheck until it is listed here (and facet
 * 16 then demands it be reachable).
 */
const REJECTION_KIND_INDEX: Readonly<Record<BaselineRejectionKind, BaselineRejectionKind>> = {
  malformed: "malformed",
  "one-run-format": "one-run-format",
  "missing-stamp": "missing-stamp",
  "leg-set": "leg-set",
  "median-mismatch": "median-mismatch",
  "absent-ceiling": "absent-ceiling",
  "altered-ceiling": "altered-ceiling",
  "uniform-metrics": "uniform-metrics",
  "insufficient-rows": "insufficient-rows",
};

const ALL_REJECTION_KINDS: readonly BaselineRejectionKind[] = Object.values(REJECTION_KIND_INDEX);

/** Every {@link BaselineDefect} the shared generator declares, total by the same trick. */
const DEFECT_INDEX: Readonly<Record<BaselineDefect, BaselineDefect>> = {
  none: "none",
  "missing-stamp": "missing-stamp",
  "absent-ceiling": "absent-ceiling",
  "uniform-metrics": "uniform-metrics",
};

const ALL_DEFECTS: readonly BaselineDefect[] = Object.values(DEFECT_INDEX);

/** The provenance stamps a row and its samples carry: two per row, one per sample. */
type StampKey = "harnessVersion" | "seed" | "capturedAt";

const STAMP_KEY_INDEX: Readonly<Record<StampKey, StampKey>> = {
  harnessVersion: "harnessVersion",
  seed: "seed",
  capturedAt: "capturedAt",
};

const ALL_STAMP_KEYS: readonly StampKey[] = Object.values(STAMP_KEY_INDEX);

/** How a row's sample set, or the document's leg count, leaves the k-leg design. */
type LegSetDefect = "dropped" | "repeated" | "beyond" | "document";

// ---------------------------------------------------------------------------
// Verdict narrowing (no casts, no non-null assertions)
// ---------------------------------------------------------------------------

type AcceptedVerdict = Extract<BaselineVerdict, { readonly outcome: "accepted" }>;
type RejectedVerdict = Extract<BaselineVerdict, { readonly outcome: "rejected" }>;

/** The kinds a verdict rejected on; empty for an accepted verdict. */
function rejectedKinds(verdict: BaselineVerdict): readonly BaselineRejectionKind[] {
  return verdict.outcome === "rejected" ? verdict.rejections.map((r) => r.kind) : [];
}

function requireAccepted(verdict: BaselineVerdict): AcceptedVerdict {
  if (verdict.outcome !== "accepted") {
    throw new Error(
      `expected an accepted baseline; rejected as [${rejectedKinds(verdict).join(", ")}]`,
    );
  }
  return verdict;
}

function requireRejected(verdict: BaselineVerdict): RejectedVerdict {
  if (verdict.outcome !== "rejected") {
    throw new Error("expected a rejected baseline; the candidate was accepted");
  }
  return verdict;
}

/** First element, throwing rather than asserting non-null (`noUncheckedIndexedAccess`). */
function headOf<T>(items: readonly T[]): T {
  const first = items[0];
  if (first === undefined) {
    throw new Error("expected a non-empty collection");
  }
  return first;
}

/** The item at `at`, throwing rather than asserting non-null. */
function itemAt<T>(items: readonly T[], at: number, what: string): T {
  const item = items[at];
  if (item === undefined) {
    throw new Error(`generator drift: no ${what} at ${at}`);
  }
  return item;
}

/** A value an undefected candidate always carries, throwing if the generator drifted. */
function requireValue<T>(value: T | null, what: string): T {
  if (value === null) {
    throw new Error(`generator drift: an undefected candidate carried no ${what}`);
  }
  return value;
}

// ---------------------------------------------------------------------------
// k legs and the k-sample candidate
// ---------------------------------------------------------------------------

/** k, the legs behind every row (ADR-059). */
const K = EFFECTIVENESS_LEG_COUNT;

/** Legs 1..k. */
const LEGS: readonly number[] = Array.from({ length: K }, (_, offset) => offset + 1);

/** A 40-character lowercase hexadecimal commit, the form `github.sha` takes. */
const commitShaArb: fc.Arbitrary<string> = fc
  .array(fc.constantFrom(..."0123456789abcdef".split("")), { minLength: 40, maxLength: 40 })
  .map((digits) => digits.join(""));

/** A latency sample as a candidate carries it; `capturedAt` may be absent, which is a defect. */
interface CandidateSample {
  readonly leg: number;
  readonly latencyMs: number;
  readonly capturedAt: string | null;
}

/** A k-sample candidate row: the shape `assembleBaselineDocument` packages. */
interface CandidateRow {
  readonly job: JobToBeDone;
  readonly steps: number;
  readonly latencyMs: number;
  readonly errorRate: number;
  readonly harnessVersion: string | null;
  readonly seed: number | null;
  readonly latencySamples: readonly CandidateSample[];
}

/** An instant moved by `milliseconds`, still ISO-8601 UTC with milliseconds. */
function shiftInstant(instant: string, milliseconds: number): string {
  return new Date(Date.parse(instant) + milliseconds).toISOString();
}

/**
 * k samples whose median is exactly `centre`: the centre on leg 1, (k - 1) / 2 samples at or
 * above it and as many at or below it (floored at 0). Leg n is captured n - 1 ms after the row's
 * instant, or not at all when the row has none.
 */
function samplesAround(
  centre: number,
  offsets: readonly number[],
  capturedAt: string | null,
): readonly CandidateSample[] {
  const half = (K - 1) / 2;
  const values = [
    centre,
    ...offsets.map((offset, at) => (at < half ? centre + offset : Math.max(0, centre - offset))),
  ];
  return values.map((latencyMs, at) => ({
    leg: at + 1,
    latencyMs,
    capturedAt: capturedAt === null ? null : shiftInstant(capturedAt, at),
  }));
}

/** A generated row as a k-sample candidate row: its drawn latency becomes the median. */
function toCandidateRow(row: CapturedScorecardRow, offsets: readonly number[]): CandidateRow {
  return {
    job: row.job,
    steps: row.steps,
    latencyMs: row.latencyMs,
    errorRate: row.errorRate,
    harnessVersion: row.harnessVersion,
    seed: row.seed,
    latencySamples: samplesAround(row.latencyMs, offsets, row.capturedAt),
  };
}

/** One offset set per row: k - 1 non-negative distances from the row's centre. */
const spreadsArb: fc.Arbitrary<readonly (readonly number[])[]> = fc.array(
  fc.array(fc.integer({ min: 0, max: 500 }), { minLength: K - 1, maxLength: K - 1 }),
  { minLength: JOB_ORDER.length, maxLength: JOB_ORDER.length },
);

/** A generated baseline case, plus the spreads and commit that make it a k-sample candidate. */
interface KCase {
  readonly defect: BaselineDefect;
  /** The generator's one-row-per-job metrics and stamps, before the spread. */
  readonly source: readonly CapturedScorecardRow[];
  readonly spreads: readonly (readonly number[])[];
  readonly proxyCeiling: string | null;
  readonly commitSha: string;
}

function kCaseOf(
  candidate: BaselineCase,
  spreads: readonly (readonly number[])[],
  commitSha: string,
): KCase {
  return {
    defect: candidate.defect,
    source: candidate.rows,
    spreads,
    proxyCeiling: candidate.proxyCeiling,
    commitSha,
  };
}

/** `rows` spread into k-sample candidate rows with the case's offsets. */
function expand(
  rows: readonly CapturedScorecardRow[],
  spreads: readonly (readonly number[])[],
): readonly CandidateRow[] {
  return rows.map((row, at) => toCandidateRow(row, itemAt(spreads, at, "spread")));
}

/** The case's k-sample candidate rows. */
function rowsOf(candidate: KCase): readonly CandidateRow[] {
  return expand(candidate.source, candidate.spreads);
}

/** The sample `leg` of a row. */
function sampleOn(row: CandidateRow, leg: number): CandidateSample {
  const sample = row.latencySamples.find((candidate) => candidate.leg === leg);
  if (sample === undefined) {
    throw new Error(`generator drift: no sample for leg ${leg}`);
  }
  return sample;
}

/** The middle of an odd-sized set, by sorting a copy: the oracle for a row's median. */
function middleOf(values: readonly number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  return itemAt(sorted, (sorted.length - 1) / 2, "middle sample");
}

/** k legs that measured the case: leg n reports sample n of every row and agrees on the rest. */
function legsOf(candidate: KCase): readonly LegScorecard[] {
  const rows = rowsOf(candidate);
  const head = headOf(rows);
  const harnessVersion = requireValue(head.harnessVersion, "harnessVersion");
  const seed = requireValue(head.seed, "seed");
  return LEGS.map(
    (leg): LegScorecard => ({
      leg: { index: leg, count: K, commitSha: candidate.commitSha },
      harnessVersion,
      seed,
      rows: rows.map((row): LegRow => {
        const sample = sampleOn(row, leg);
        return {
          job: row.job,
          steps: row.steps,
          latencyMs: sample.latencyMs,
          errorRate: row.errorRate,
          harnessVersion: requireValue(row.harnessVersion, "harnessVersion"),
          seed: requireValue(row.seed, "seed"),
          capturedAt: requireValue(sample.capturedAt, "capturedAt"),
        };
      }),
      interruptionPrecision: null,
    }),
  );
}

// ---------------------------------------------------------------------------
// Row helpers
// ---------------------------------------------------------------------------

function distinctCount(values: readonly number[]): number {
  return new Set(values).size;
}

/** Whether a row set is uniform in BOTH columns, per the COMMITTED minima. */
function isUniformUnderPolicy(rows: readonly CapturedScorecardRow[]): boolean {
  return (
    distinctCount(rows.map((row) => row.steps)) < POLICY.minDistinctSteps &&
    distinctCount(rows.map((row) => row.latencyMs)) < POLICY.minDistinctLatencyMs
  );
}

/** Whether a generated row carries all three of its one-run stamps. */
function isStampedRow(row: CapturedScorecardRow): boolean {
  return row.harnessVersion !== null && row.seed !== null && row.capturedAt !== null;
}

/**
 * Rewrites `steps` and `latencyMs` as running totals of the DRAWN values. Every drawn value is
 * at least 1, so the totals strictly increase and the row set carries `rows.length` distinct
 * values in both columns -- which is how the acceptance facets avoid the generator's legitimate
 * `uniform-metrics` collision without touching `arbitraries.ts`. The numbers remain generated;
 * only their collision is removed.
 */
function withDistinctMetrics(
  rows: readonly CapturedScorecardRow[],
): readonly CapturedScorecardRow[] {
  const spread: CapturedScorecardRow[] = [];
  let steps = 0;
  let latencyMs = 0;
  for (const row of rows) {
    steps += Math.max(1, row.steps);
    latencyMs += Math.max(1, row.latencyMs);
    spread.push({ ...row, steps, latencyMs });
  }
  return spread;
}

/** Collapses every row onto the first row's metrics -- the authored-ceiling shape. */
function withUniformMetrics(
  rows: readonly CapturedScorecardRow[],
): readonly CapturedScorecardRow[] {
  const head = headOf(rows);
  return rows.map((row) => ({ ...row, steps: head.steps, latencyMs: head.latencyMs }));
}

/** The rows with exactly one stamp removed: a row's version or seed, or one sample's instant. */
function withStampRemoved(
  rows: readonly CandidateRow[],
  index: number,
  stamp: StampKey,
  leg: number,
): readonly CandidateRow[] {
  return rows.map((row, position) => {
    if (position !== index) return row;
    return {
      ...row,
      harnessVersion: stamp === "harnessVersion" ? null : row.harnessVersion,
      seed: stamp === "seed" ? null : row.seed,
      latencySamples: row.latencySamples.map((sample) =>
        stamp === "capturedAt" && sample.leg === leg ? { ...sample, capturedAt: null } : sample,
      ),
    };
  });
}

/** The rows with row `index`'s samples replaced. */
function withSamplesAt(
  rows: readonly CandidateRow[],
  index: number,
  samples: readonly CandidateSample[],
): readonly CandidateRow[] {
  return rows.map((row, position) =>
    position === index ? { ...row, latencySamples: samples } : row,
  );
}

function isRetainedCeiling(ceiling: string | null): boolean {
  return ceiling !== null && ceiling.trim().length > 0;
}

function requireCeiling(ceiling: string | null): string {
  if (ceiling === null || ceiling.trim().length === 0) {
    throw new Error("generator drift: expected a retained, non-blank proxyCeiling");
  }
  return ceiling;
}

/** Assemble + validate, against the committed policy. */
function verdictFor(
  rows: readonly CandidateRow[],
  proxyCeiling: string | null,
  commitSha: string | null,
): BaselineVerdict {
  return validateBaseline(assembleBaselineDocument({ rows, proxyCeiling, commitSha }), POLICY);
}

// ---------------------------------------------------------------------------
// Arbitraries -- all derived from the shared `baselineCaseArb`
// ---------------------------------------------------------------------------

/**
 * A candidate the generator declares defect-free AND whose drawn ceiling is non-blank. The
 * ceiling filter is not cosmetic: `fc.string({ minLength: 20 })` can in principle draw an
 * all-whitespace statement, which is honestly `absent-ceiling`, and a facet asserting an exact
 * rejection set must not be flaky on it.
 */
const undefectedCaseArb: fc.Arbitrary<KCase> = fc
  .tuple(
    baselineCaseArb.filter(
      (candidate) => candidate.defect === "none" && isRetainedCeiling(candidate.proxyCeiling),
    ),
    spreadsArb,
    commitShaArb,
  )
  .map(([candidate, spreads, commitSha]) => kCaseOf(candidate, spreads, commitSha));

/** An undefected candidate whose drawn metrics are guaranteed distinct across rows. */
const measuredCaseArb: fc.Arbitrary<KCase> = undefectedCaseArb.map((candidate) => ({
  ...candidate,
  source: withDistinctMetrics(candidate.source),
}));

/** The generator's authored-ceiling case: identical `steps` and `latencyMs` on every row. */
const authoredCeilingCaseArb: fc.Arbitrary<KCase> = fc
  .tuple(
    baselineCaseArb.filter(
      (candidate) =>
        candidate.defect === "uniform-metrics" && isRetainedCeiling(candidate.proxyCeiling),
    ),
    spreadsArb,
    commitShaArb,
  )
  .map(([candidate, spreads, commitSha]) => kCaseOf(candidate, spreads, commitSha));

/** Which row is defected. */
const rowIndexArb: fc.Arbitrary<number> = fc.integer({ min: 0, max: JOB_ORDER.length - 1 });

/** Which leg's sample is defected. */
const legArb: fc.Arbitrary<number> = fc.integer({ min: 1, max: K });

/** Which stamp is the missing one. */
const stampKeyArb: fc.Arbitrary<StampKey> = fc.constantFrom<StampKey>(...ALL_STAMP_KEYS);

/** Framing whitespace, to prove the retained statement is never trimmed. */
const framingArb: fc.Arbitrary<string> = fc.constantFrom("", " ", "   ", "\t", "\n", " \t\n ");

/** A ceiling that is present but says nothing -- indistinguishable from absent (R8.10). */
const blankCeilingArb: fc.Arbitrary<string | null> = fc.constantFrom<string | null>(
  null,
  "",
  " ",
  "\t",
  "\n",
  "   \t\n  ",
);

/** A document whose row `index` (or whose leg count) has the given leg-set defect. */
function legSetDocument(
  candidate: KCase,
  index: number,
  leg: number,
  defect: LegSetDefect,
  bump: number,
): unknown {
  const rows = rowsOf(candidate);
  const samples = itemAt(rows, index, "row").latencySamples;
  const ceiling = requireCeiling(candidate.proxyCeiling);
  const commitSha = candidate.commitSha;
  switch (defect) {
    case "dropped":
      return assembleBaselineDocument({
        rows: withSamplesAt(
          rows,
          index,
          samples.filter((sample) => sample.leg !== leg),
        ),
        proxyCeiling: ceiling,
        commitSha,
      });
    case "repeated":
      // Leg `leg` relabelled as another leg: k samples, but k - 1 distinct legs.
      return assembleBaselineDocument({
        rows: withSamplesAt(
          rows,
          index,
          samples.map((sample) =>
            sample.leg === leg ? { ...sample, leg: leg === 1 ? 2 : 1 } : sample,
          ),
        ),
        proxyCeiling: ceiling,
        commitSha,
      });
    case "beyond":
      return assembleBaselineDocument({
        rows: withSamplesAt(
          rows,
          index,
          samples.map((sample) => (sample.leg === leg ? { ...sample, leg: K + bump } : sample)),
        ),
        proxyCeiling: ceiling,
        commitSha,
      });
    case "document":
      return assembleBaselineDocument({
        rows,
        proxyCeiling: ceiling,
        commitSha,
        legCount: K + bump,
      });
  }
}

/**
 * A verdict exhibiting `kind`, built from a measured candidate by injecting exactly the one
 * defect that kind names. Every branch yields exactly ONE rejection, which is what lets facet 16
 * assert the kind set exactly rather than merely containing the target.
 */
function verdictExhibiting(kind: BaselineRejectionKind, candidate: KCase): BaselineVerdict {
  const rows = rowsOf(candidate);
  const ceiling = requireCeiling(candidate.proxyCeiling);
  const commitSha = candidate.commitSha;
  switch (kind) {
    case "malformed":
      // Document-shaped but missing every required field except `rows`.
      return validateBaseline({ rows }, POLICY);
    case "one-run-format":
      return validateBaseline(
        assembleBaselineDocument({
          rows: candidate.source,
          proxyCeiling: ceiling,
          commitSha: null,
          schemaVersion: ONE_RUN_BASELINE_SCHEMA_VERSION,
        }),
        POLICY,
      );
    case "missing-stamp":
      return verdictFor(withStampRemoved(rows, 0, "seed", 1), ceiling, commitSha);
    case "leg-set":
      return validateBaseline(legSetDocument(candidate, 0, 1, "document", 1), POLICY);
    case "median-mismatch":
      return verdictFor(
        rows.map((row, at) => (at === 0 ? { ...row, latencyMs: row.latencyMs + 1 } : row)),
        ceiling,
        commitSha,
      );
    case "absent-ceiling":
      return verdictFor(rows, null, commitSha);
    case "altered-ceiling":
      // Raised only by the committed-artifact rule: a present but non-canonical statement.
      return checkCommittedBaseline(
        canonicalJson(assembleBaselineDocument({ rows, proxyCeiling: ceiling, commitSha })),
        POLICY,
      );
    case "uniform-metrics":
      return verdictFor(
        expand(withUniformMetrics(candidate.source), candidate.spreads),
        ceiling,
        commitSha,
      );
    case "insufficient-rows":
      // Policy-derived, never a literal row count: one fewer row than the rule can evaluate.
      return verdictFor(rows.slice(0, POLICY.minRows - 1), ceiling, commitSha);
  }
}

describe("Property 36: A baseline is a measurement, not a ceiling", () => {
  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("guards that the committed policy was read from disk and the k-leg format is the decision's", () => {
    // The thresholds under test are the committed ones (AD-13), at the location the whole repo
    // already watches -- not defaults, and not values copied into this file.
    expect(BASELINE_POLICY_RELPATH).toBe("infrastructure/quality/effectiveness-baseline.json");
    expect(POLICY.version).toBeGreaterThan(0);

    // The policy schema floors all three at 2 so the rule cannot be switched off from
    // configuration. Asserting the floor, not the committed value.
    expect(POLICY.minRows).toBeGreaterThanOrEqual(2);
    expect(POLICY.minDistinctSteps).toBeGreaterThanOrEqual(2);
    expect(POLICY.minDistinctLatencyMs).toBeGreaterThanOrEqual(2);

    // A five-job baseline must be able to satisfy the rule, else the acceptance facets below
    // would be unconstructible and would pass for the wrong reason.
    expect(JOB_ORDER.length).toBeGreaterThanOrEqual(POLICY.minRows);
    expect(JOB_ORDER.length).toBeGreaterThanOrEqual(POLICY.minDistinctSteps);
    expect(JOB_ORDER.length).toBeGreaterThanOrEqual(POLICY.minDistinctLatencyMs);

    // ADR-059: version 2 is the k-leg format the check reads, and version 1 is the one-run
    // format it refuses by name. k is odd, so a row's median is one of its own samples, which
    // is what makes `samplesAround`'s centre the median.
    expect(BASELINE_SCHEMA_VERSION).toBe(2);
    expect(ONE_RUN_BASELINE_SCHEMA_VERSION).toBe(1);
    expect(K % 2).toBe(1);
    expect(LEGS).toHaveLength(K);
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("guards that every declared BaselineDefect is drawn and carries the defect it names", () => {
    const observed = new Set<BaselineDefect>();

    fc.assert(
      fc.property(baselineCaseArb, (candidate) => {
        observed.add(candidate.defect);

        // One row per declared Job_To_Be_Done, whatever the defect.
        expect(candidate.rows).toHaveLength(JOB_ORDER.length);

        const unstamped = candidate.rows.some((row) => !isStampedRow(row));
        if (candidate.defect === "missing-stamp") {
          expect(unstamped).toBe(true);
        }
        if (candidate.defect === "absent-ceiling") {
          expect(candidate.proxyCeiling).toBeNull();
          expect(unstamped).toBe(false);
        }
        if (candidate.defect === "uniform-metrics") {
          expect(isUniformUnderPolicy(candidate.rows)).toBe(true);
          expect(unstamped).toBe(false);
        }
        if (candidate.defect === "none") {
          expect(unstamped).toBe(false);
          expect(candidate.proxyCeiling).not.toBeNull();
        }
      }),
    );

    // Nothing above can pass vacuously: all four defects were actually generated. This file
    // states no run budget (R3.3), so this guard's strength is a function of the active profile.
    // Over a uniform draw of four values, n runs miss at least one with probability at most
    // 4*(3/4)^n -- about 0.22 at the local `dev` budget of 10, and below 1e-11 from 100 upward.
    // A local miss is a statement about the budget, not about the generator (I-7).
    expect([...observed].sort()).toEqual([...ALL_DEFECTS].sort());
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("builds a baseline from k agreeing legs that validates clean, one sample per leg per row", () => {
    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        const built = buildBaseline(legsOf(candidate));
        expect(built.outcome).toBe("built");
        if (built.outcome !== "built") return;

        // Byte-for-byte the document a reader assembles from the same legs: the constructor
        // invents nothing, and each row's drawn latency is its median by construction.
        const rows = rowsOf(candidate);
        const head = headOf(rows);
        const assembled = assembleBaselineDocument({
          rows,
          proxyCeiling: SCRIPTED_PROXY_CEILING,
          commitSha: candidate.commitSha,
          harnessVersion: requireValue(head.harnessVersion, "harnessVersion"),
          seed: requireValue(head.seed, "seed"),
        });
        expect(canonicalJson(built.baseline)).toBe(canonicalJson(assembled));

        const accepted = requireAccepted(validateBaseline(built.baseline, POLICY));
        expect(accepted.baseline.schemaVersion).toBe(BASELINE_SCHEMA_VERSION);
        expect(accepted.baseline.legCount).toBe(K);
        expect(accepted.baseline.commitSha).toBe(candidate.commitSha);
        expect(accepted.baseline.rows).toHaveLength(JOB_ORDER.length);
        for (const row of accepted.baseline.rows) {
          // Every row can name each leg and instant that measured it (R8.10, ADR-059).
          expect(row.latencySamples.map((sample) => sample.leg)).toEqual([...LEGS]);
          expect(row.latencyMs).toBe(
            middleOf(row.latencySamples.map((sample) => sample.latencyMs)),
          );
          for (const sample of row.latencySamples) {
            expect(sample.capturedAt.endsWith("Z")).toBe(true);
            expect(Number.isNaN(Date.parse(sample.capturedAt))).toBe(false);
          }
        }

        // `buildBaseline` writes the canonical statement, so it is reported canonical.
        expect(accepted.baseline.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
        expect(accepted.proxyCeilingIsCanonical).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("refuses to build a baseline from fewer than k legs, a duplicated leg, or legs that disagree", () => {
    fc.assert(
      fc.property(measuredCaseArb, fc.integer({ min: 0, max: K - 1 }), (candidate, position) => {
        const legs = legsOf(candidate);
        const firstJob = headOf(JOB_ORDER);

        // One leg short: a median of k - 1 legs is not this rule.
        const short = buildBaseline(legs.filter((_, at) => at !== position));
        expect(short.outcome).toBe("refused");
        if (short.outcome === "refused") {
          expect(short.arrival.map((failure) => failure.kind)).toContain("leg-count");
        }

        // k scorecards, one leg claimed twice.
        const twice = buildBaseline(
          legs.map((scorecard, at) =>
            at === position
              ? { ...scorecard, leg: { ...scorecard.leg, index: position === 0 ? 2 : 1 } }
              : scorecard,
          ),
        );
        expect(twice.outcome).toBe("refused");
        if (twice.outcome === "refused") {
          expect(twice.arrival.map((failure) => failure.kind)).toContain("duplicate-leg");
        }

        // k legs that disagree on a deterministic metric: refused by the pooling, not built.
        const split = buildBaseline(
          legs.map((scorecard, at) =>
            at === position
              ? {
                  ...scorecard,
                  rows: scorecard.rows.map((row) =>
                    row.job === firstJob ? { ...row, steps: row.steps + 1 } : row,
                  ),
                }
              : scorecard,
          ),
        );
        expect(split.outcome).toBe("refused");
        if (split.outcome === "refused") {
          expect(split.arrival).toEqual([]);
          expect(split.disagreements.map((entry) => `${entry.subject}::${entry.metric}`)).toEqual([
            `${firstJob}::steps`,
          ]);
        }
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("refuses the one-run format by name, whatever its rows carry", () => {
    fc.assert(
      fc.property(baselineCaseArb, (candidate) => {
        // The shape every baseline had before ADR-059: one run's rows, stamped or not, uniform
        // or not, with or without a ceiling. None of that is read; the format is refused first.
        const oneRun = assembleBaselineDocument({
          rows: candidate.rows,
          proxyCeiling: candidate.proxyCeiling,
          commitSha: null,
          schemaVersion: ONE_RUN_BASELINE_SCHEMA_VERSION,
        });
        const rejected = requireRejected(validateBaseline(oneRun, POLICY));
        expect(rejectedKinds(rejected)).toEqual(["one-run-format"]);
        const rejection = headOf(rejected.rejections);
        expect(rejection.job).toBeNull();
        expect(rejection.detail).toContain("one-run");

        // The committed-artifact rule refuses it the same way, through its text.
        expect(rejectedKinds(checkCommittedBaseline(canonicalJson(oneRun), POLICY))).toEqual([
          "one-run-format",
        ]);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects an authored ceiling as uniform-metrics, and accepts the same rows once spread", () => {
    fc.assert(
      fc.property(authoredCeilingCaseArb, (candidate) => {
        expect(candidate.defect).toBe("uniform-metrics");

        // The audit's finding, generated: identical steps and identical millisecond latencies
        // on every row -- here identical MEDIANS over k legs, however their samples spread --
        // however plausible the numbers and however complete the stamps.
        expect(isUniformUnderPolicy(candidate.source)).toBe(true);
        const ceiling = requireCeiling(candidate.proxyCeiling);
        const rejected = requireRejected(
          verdictFor(rowsOf(candidate), ceiling, candidate.commitSha),
        );

        // Exactly one reason, and it is the authored-ceiling one.
        expect(rejectedKinds(rejected)).toEqual(["uniform-metrics"]);
        const rejection = headOf(rejected.rejections);
        expect(rejection.job).toBeNull();
        expect(rejection.detail.length).toBeGreaterThan(0);

        // The rule discriminates rather than refuses: the SAME rows, with the drawn metrics
        // spread apart, are accepted.
        const spread = withDistinctMetrics(candidate.source);
        expect(isUniformUnderPolicy(spread)).toBe(false);
        const accepted = requireAccepted(
          verdictFor(expand(spread, candidate.spreads), ceiling, candidate.commitSha),
        );
        expect(accepted.baseline.rows).toHaveLength(JOB_ORDER.length);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("accepts an undefected candidate, or rejects it solely as a genuinely uniform row set", () => {
    fc.assert(
      fc.property(undefectedCaseArb, (candidate) => {
        // Raw from the shared generator: metrics drawn per row and NOT spread, so the `none`
        // case can collide into a uniform row set, which the rule correctly rejects. The
        // disjunction is kept narrow: uniform-metrics ALONE, on a row set the drawn rows
        // independently confirm is uniform.
        const verdict = verdictFor(
          rowsOf(candidate),
          requireCeiling(candidate.proxyCeiling),
          candidate.commitSha,
        );

        if (verdict.outcome === "accepted") {
          expect(verdict.baseline.rows).toHaveLength(JOB_ORDER.length);
          expect(isUniformUnderPolicy(candidate.source)).toBe(false);
          return;
        }
        expect(rejectedKinds(verdict)).toEqual(["uniform-metrics"]);
        expect(isUniformUnderPolicy(candidate.source)).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects a row or sample missing its provenance stamp, or a document without its commit, as missing-stamp", () => {
    fc.assert(
      fc.property(
        measuredCaseArb,
        rowIndexArb,
        stampKeyArb,
        legArb,
        (candidate, index, stamp, leg) => {
          const rows = rowsOf(candidate);
          const target = itemAt(rows, index, "row");
          const ceiling = requireCeiling(candidate.proxyCeiling);

          // Exactly one rejection, attributed to the row and naming the stamp it could not supply.
          const holed = withStampRemoved(rows, index, stamp, leg);
          const rejected = requireRejected(verdictFor(holed, ceiling, candidate.commitSha));
          expect(rejectedKinds(rejected)).toEqual(["missing-stamp"]);
          const rejection = headOf(rejected.rejections);
          expect(rejection.job).toBe(target.job);
          expect(rejection.detail).toContain(stamp);
          if (stamp === "capturedAt") {
            expect(rejection.detail).toContain(`leg(s) ${leg}`);
          }

          // The document must name the commit its legs measured, as a 40-character hex sha.
          const unnamed: readonly (string | null)[] = [
            null,
            "",
            candidate.commitSha.slice(1),
            `A${candidate.commitSha.slice(1)}`,
          ];
          for (const commit of unnamed) {
            const refused = requireRejected(verdictFor(rows, ceiling, commit));
            expect(rejectedKinds(refused)).toEqual(["missing-stamp"]);
            expect(headOf(refused.rejections).job).toBeNull();
            expect(headOf(refused.rejections).detail).toContain("commitSha");
          }

          // Restored, the same document is accepted: the stamp was the only cause.
          const accepted = requireAccepted(verdictFor(rows, ceiling, candidate.commitSha));
          expect(accepted.baseline.rows).toHaveLength(JOB_ORDER.length);
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects a row whose samples are not exactly legs 1..k, or another leg count, as leg-set", () => {
    const defectArb = fc.constantFrom<LegSetDefect>("dropped", "repeated", "beyond", "document");
    fc.assert(
      fc.property(
        measuredCaseArb,
        rowIndexArb,
        legArb,
        defectArb,
        fc.integer({ min: 1, max: 9 }),
        (candidate, index, leg, defect, bump) => {
          const target = itemAt(rowsOf(candidate), index, "row");
          const document = legSetDocument(candidate, index, leg, defect, bump);

          // One sample short, one leg twice, a leg outside 1..k, or a document of another
          // design: each alone is a leg-set rejection, and the median of the wrong samples is
          // not evaluated on top of it.
          const rejected = requireRejected(validateBaseline(document, POLICY));
          expect(rejectedKinds(rejected)).toEqual(["leg-set"]);
          const rejection = headOf(rejected.rejections);
          expect(rejection.job).toBe(defect === "document" ? null : target.job);
          expect(rejection.detail.length).toBeGreaterThan(0);
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects a row whose latencyMs is not the median of its samples as median-mismatch", () => {
    fc.assert(
      fc.property(
        measuredCaseArb,
        rowIndexArb,
        fc.integer({ min: 1, max: 1000 }),
        fc.boolean(),
        (candidate, index, delta, up) => {
          const rows = rowsOf(candidate);
          const target = itemAt(rows, index, "row");
          const moved = up ? target.latencyMs + delta : Math.max(0, target.latencyMs - delta);
          fc.pre(moved !== target.latencyMs);

          // The samples are untouched; only the row's stated latency moved off their median.
          const edited = rows.map((row, at) => (at === index ? { ...row, latencyMs: moved } : row));
          const rejected = requireRejected(
            verdictFor(edited, requireCeiling(candidate.proxyCeiling), candidate.commitSha),
          );
          expect(rejectedKinds(rejected)).toEqual(["median-mismatch"]);
          const rejection = headOf(rejected.rejections);
          expect(rejection.job).toBe(target.job);
          expect(rejection.detail).toContain(String(moved));
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects an absent or blank proxyCeiling as absent-ceiling", () => {
    fc.assert(
      fc.property(measuredCaseArb, blankCeilingArb, (candidate, blank) => {
        const rejected = requireRejected(verdictFor(rowsOf(candidate), blank, candidate.commitSha));

        // A statement that says nothing is not a retained statement, whether it is null, empty,
        // or whitespace. The rows are stamped and non-uniform, so this is the only reason.
        expect(rejectedKinds(rejected)).toEqual(["absent-ceiling"]);
        const rejection = headOf(rejected.rejections);
        expect(rejection.job).toBeNull();
        expect(rejection.detail.length).toBeGreaterThan(0);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("keeps a retained proxyCeiling verbatim, and rejects a non-canonical one as altered-ceiling", () => {
    fc.assert(
      fc.property(measuredCaseArb, framingArb, framingArb, (candidate, lead, trail) => {
        // Framing whitespace makes "verbatim" falsifiable: a validator that trimmed, normalised,
        // or re-derived the statement would return a different string.
        const retained = `${lead}${requireCeiling(candidate.proxyCeiling)}${trail}`;
        const candidateDocument = assembleBaselineDocument({
          rows: rowsOf(candidate),
          proxyCeiling: retained,
          commitSha: candidate.commitSha,
        });

        const accepted = requireAccepted(validateBaseline(candidateDocument, POLICY));
        expect(accepted.baseline.proxyCeiling).toBe(retained);
        expect(accepted.proxyCeilingIsCanonical).toBe(false);

        // Through JSON text, byte for byte.
        const text = canonicalJson(candidateDocument);
        expect(text).toContain(canonicalJson(retained));
        const viaText = requireAccepted(validateBaselineText(text, POLICY));
        expect(viaText.baseline.proxyCeiling).toBe(retained);

        // The COMMITTED artifact's rule is stricter: a present but non-canonical statement is a
        // named rejection, never a silent replacement with the canonical wording.
        expect(rejectedKinds(checkCommittedBaseline(text, POLICY))).toEqual(["altered-ceiling"]);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("round-trips a built baseline through serialization byte-identically, in any row or sample order", () => {
    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        const built = buildBaseline(legsOf(candidate));
        if (built.outcome !== "built") {
          throw new Error("generator drift: k agreeing legs did not build a baseline");
        }
        const text = serializeBaseline(built.baseline);
        const accepted = requireAccepted(validateBaselineText(text, POLICY));

        // The canonical statement survives as bytes in the artifact and as a string out of the
        // validator -- retained, not regenerated.
        expect(text).toContain(canonicalJson(SCRIPTED_PROXY_CEILING));
        expect(accepted.baseline.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
        expect(accepted.proxyCeilingIsCanonical).toBe(true);

        // Re-emitting what the validator returned reproduces identical bytes (Req 4.6), and so
        // does the same measurement with its rows and samples handed over in reverse.
        expect(serializeBaseline(accepted.baseline)).toBe(text);
        const reversed = {
          ...built.baseline,
          rows: [...built.baseline.rows]
            .reverse()
            .map((row) => ({ ...row, latencySamples: [...row.latencySamples].reverse() })),
        };
        expect(serializeBaseline(reversed)).toBe(text);

        // And the stricter committed-artifact rule accepts it -- on GENERATED input.
        const committed = requireAccepted(checkCommittedBaseline(text, POLICY));
        expect(committed.baseline.rows).toHaveLength(JOB_ORDER.length);
        expect(committed.proxyCeilingIsCanonical).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects a baseline too short to evaluate rather than passing it vacuously", () => {
    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        // One row short of the committed minimum, derived from the policy, not written here.
        const tooFew = rowsOf(candidate).slice(0, POLICY.minRows - 1);
        expect(tooFew.length).toBeLessThan(POLICY.minRows);

        const rejected = requireRejected(
          verdictFor(tooFew, requireCeiling(candidate.proxyCeiling), candidate.commitSha),
        );

        // Unevaluable is a rejection, not a pass (I-7): a one-row baseline is trivially uniform.
        expect(rejectedKinds(rejected)).toEqual(["insufficient-rows"]);
        expect(headOf(rejected.rejections).detail.length).toBeGreaterThan(0);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects anything that is not a baseline document as malformed, and never throws", () => {
    // The text path: unparseable JSON, or JSON that is not a baseline document.
    fc.assert(
      fc.property(fc.string(), (text) => {
        expect(rejectedKinds(validateBaselineText(text, POLICY))).toEqual(["malformed"]);
      }),
    );

    // The object path: totality over arbitrary structured input.
    fc.assert(
      fc.property(fc.anything(), (value) => {
        expect(rejectedKinds(validateBaseline(value, POLICY))).toEqual(["malformed"]);
      }),
    );

    // A document that claims the k-leg version but carries one-run rows (a row-level
    // `capturedAt`, no samples) is not half-read: it is not a baseline document at all.
    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        const mislabelled = assembleBaselineDocument({
          rows: candidate.source,
          proxyCeiling: requireCeiling(candidate.proxyCeiling),
          commitSha: candidate.commitSha,
        });
        expect(rejectedKinds(validateBaseline(mislabelled, POLICY))).toEqual(["malformed"]);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("names a kind on every rejection, and every declared BaselineRejectionKind is reachable", () => {
    const observed = new Set<BaselineRejectionKind>();

    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        // The candidate is quantified; the kinds are ENUMERATED rather than sampled, so
        // reachability below is deterministic instead of a function of how the draws fell.
        for (const kind of ALL_REJECTION_KINDS) {
          const rejected = requireRejected(verdictExhibiting(kind, candidate));

          // A rejection is never a bare boolean false: it states its kind, its attribution, and
          // a non-empty detail naming what was observed.
          expect(rejectedKinds(rejected)).toEqual([kind]);
          for (const rejection of rejected.rejections) {
            expect(ALL_REJECTION_KINDS).toContain(rejection.kind);
            expect(rejection.detail.trim().length).toBeGreaterThan(0);
            expect(rejection.job === null || JOB_ORDER.includes(rejection.job)).toBe(true);
            observed.add(rejection.kind);
          }
        }
      }),
    );

    // Not one kind is decorative: each is reachable from a generated candidate.
    expect([...observed].sort()).toEqual([...ALL_REJECTION_KINDS].sort());
  });
});
