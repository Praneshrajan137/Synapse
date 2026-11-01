/**
 * Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
 *
 * Validates: Requirements 8.10
 *
 * Property-based verification of the COMMITTED effectiveness baseline's rules (design
 * "Property 36: A baseline is a measurement, not a ceiling"; R8.10: "THE committed
 * baseline SHALL record, for each row, the `harnessVersion`, the `seed`, and the
 * timestamp of the run that produced that row, SHALL retain the `proxyCeiling`
 * statement, and IF every row carries an identical `steps` value and an identical
 * `latencyMs` value, THEN THE baseline check SHALL fail the baseline as an authored
 * ceiling rather than accept it as a measurement").
 *
 * ## What is universally quantified
 *
 * Over baseline CANDIDATES, not over one artifact. Every candidate is drawn from the
 * shared `baselineCaseArb` (`frontend/spec/effectiveness/arbitraries.ts`): a five-row
 * document, one row per declared Job_To_Be_Done, carrying at most one injected
 * `BaselineDefect` (`none | missing-stamp | absent-ceiling | uniform-metrics`). Facets
 * that need a finer choice also quantify over it -- WHICH row and WHICH of the three
 * provenance stamps is missing, and the whitespace framing of the retained ceiling -- so
 * no facet is a single hand-picked example wearing a property's clothes. The one place a
 * choice is ENUMERATED rather than drawn is the rejection-kind facet, where every kind is
 * constructed on every run so its reachability claim is deterministic.
 *
 * The subject is the shipped validator `@lib/effectiveness-baseline` (task 11.7), driven
 * directly. The thresholds are the COMMITTED ones, read from
 * `infrastructure/quality/effectiveness-baseline.json` through
 * `loadBaselinePolicy` (AD-13): not one policy number is restated in this file, so a
 * weakened policy shows up here as a failing facet rather than as a passing test that
 * agrees with itself.
 *
 * ## Why these facets suffice
 *
 * R8.10 is a conjunction of three rules plus a totality obligation, and each facet below
 * closes one side of it. Twelve facets, and the first is a static guard over the
 * committed policy. No facet states a run budget: `numRuns` is inherited from the
 * `HYPOTHESIS_PROFILE` profile via `fc.configureGlobal` in `frontend/src/test/setup.ts`
 * (R3.1-R3.3), mirroring the Python side's inheritance of `max_examples` from the root
 * `conftest.py`. A per-call `{ numRuns }` would override that global, so there is none:
 *
 *   1. GUARD -- the policy really came from the committed file and the rule it configures
 *      is evaluable by a five-row baseline (otherwise later facets are unconstructible).
 *   2. GUARD -- every `BaselineDefect` the shared generator declares is actually drawn,
 *      and each drawn case really carries the defect it names. Without this the defect
 *      facets could pass vacuously.
 *   3. A MEASURED baseline is accepted: rows carrying `harnessVersion`, `seed`, and
 *      `capturedAt`, assembled through the production constructor `buildBaseline`,
 *      validate clean and are read back unchanged.
 *   4. An AUTHORED CEILING is rejected -- the heart of the property. Identical `steps`
 *      and identical `latencyMs` on every row is `uniform-metrics`, and the same rows
 *      with spread metrics are accepted, so the rule is a discriminator rather than a
 *      blanket refusal.
 *   5. The same claim on candidates drawn straight from the shared generator, with the
 *      generator's one honest sharp edge stated (see below).
 *   6. PROVENANCE IS MANDATORY: dropping any ONE of the three stamps on any ONE row is
 *      `missing-stamp`, attributed to that row's job and naming that stamp.
 *   7. The ceiling STATEMENT is mandatory: absent or whitespace-only is `absent-ceiling`.
 *   8. `proxyCeiling` is kept VERBATIM: an accepted baseline returns the retained string
 *      byte-for-byte, framing whitespace included -- untrimmed, unnormalised, never
 *      re-derived from `SCRIPTED_PROXY_CEILING`. The stricter committed-artifact rule
 *      rejects a non-canonical statement as `altered-ceiling` instead of silently
 *      replacing it.
 *   9. The canonical round trip is byte-stable: `buildBaseline` ->
 *      `serializeBaseline` -> `validateBaselineText` -> `serializeBaseline` reproduces
 *      identical bytes, and the canonical statement appears in the artifact's bytes.
 *  10. Below `min_rows` the distinctness rule is UNEVALUABLE, and unevaluable is a
 *      rejection (`insufficient-rows`), never a pass (I-7).
 *  11. TOTALITY: no input makes the validator throw. Anything that is not a baseline
 *      document is `malformed`.
 *  12. Every `BaselineRejectionKind` is reachable and NAMED. A rejection is never a bare
 *      boolean false: it carries its kind, its attribution, and a non-empty detail.
 *
 * ## The generator's sharp edge, and how this file handles it (I-7)
 *
 * `baselineCaseArb`'s `none` case draws each row's `steps` and `latencyMs`
 * independently, so it can -- with small but non-zero probability -- draw a row set that
 * is uniform in BOTH columns. That candidate declares no defect yet is legitimately
 * rejected as `uniform-metrics`: the rule is right and the generator is not wrong
 * either. Two honest responses, and this file uses both rather than weakening either:
 *
 *   * Facet 3 (and every facet needing a clean baseline) maps the drawn metrics through
 *     `withDistinctMetrics`, which rewrites `steps`/`latencyMs` as running totals of the
 *     drawn values. Every drawn value is >= 1, so the totals strictly increase and the
 *     row set carries `rows.length` distinct values in both columns. The metrics are
 *     still generated, not authored; only their collision is removed. That lets those
 *     facets assert plain ACCEPTANCE, which is the strong claim.
 *   * Facet 5 keeps the raw `none` candidate and asserts the disjunction: accepted, OR
 *     rejected SOLELY as `uniform-metrics` -- and in that branch it independently
 *     recomputes the distinct counts from the drawn rows and requires them to be below
 *     the committed minima. So the disjunction cannot absorb an unrelated failure: a
 *     `missing-stamp`, an `absent-ceiling`, or a `uniform-metrics` verdict on a row set
 *     that is not actually uniform all still fail the facet.
 *
 * ## What this file deliberately does NOT assert
 *
 * That the committed `frontend/spec/effectiveness/scorecard.baseline.json` is valid. It
 * is not: it carries no per-row stamps and identical `steps`/`latencyMs` on all five
 * rows, so `checkCommittedBaselineFile` reports five `missing-stamp` rejections plus one
 * `uniform-metrics`. That is R8.10's finding becoming mechanical, and it clears only when
 * the browser harness (task 11.1) and the complete-or-failed emitter (task 11.2) produce
 * a measured baseline through `buildBaseline`. Pinning the current artifact as either
 * passing or failing here would make this file a snapshot of a defect instead of a
 * statement of the rule, so `checkCommittedBaseline` is exercised on GENERATED input
 * (facets 8 and 9) and the artifact is left to its own check.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  assembleBaselineDocument,
  type BaselinePolicy,
  type BaselineRejectionKind,
  type BaselineRow,
  type BaselineVerdict,
  buildBaseline,
  checkCommittedBaseline,
  serializeBaseline,
  validateBaseline,
  validateBaselineText,
} from "@lib/effectiveness-baseline";
import { JOB_ORDER, SCRIPTED_PROXY_CEILING } from "@lib/effectiveness-scorecard";
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
 * rule-disabling policy throws here and fails the whole file, which is the honest
 * outcome: a check that cannot read its own thresholds has not passed (I-7).
 */
const POLICY: BaselinePolicy = loadBaselinePolicy();

// ---------------------------------------------------------------------------
// Total enumerations of the two unions under test
// ---------------------------------------------------------------------------

/**
 * Every {@link BaselineRejectionKind}. The `Record` annotation makes totality a
 * compile-time obligation: a kind added to the union fails to typecheck until it is
 * listed here (and facet 12 then demands it be reachable).
 */
const REJECTION_KIND_INDEX: Readonly<Record<BaselineRejectionKind, BaselineRejectionKind>> = {
  malformed: "malformed",
  "missing-stamp": "missing-stamp",
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

/** The three per-row provenance stamps R8.10 requires. */
type StampKey = "harnessVersion" | "seed" | "capturedAt";

const STAMP_KEY_INDEX: Readonly<Record<StampKey, StampKey>> = {
  harnessVersion: "harnessVersion",
  seed: "seed",
  capturedAt: "capturedAt",
};

const ALL_STAMP_KEYS: readonly StampKey[] = Object.values(STAMP_KEY_INDEX);

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

/** Narrows a generated row to a stamped {@link BaselineRow}, or `null` if a stamp is absent. */
function asMeasuredRow(row: CapturedScorecardRow): BaselineRow | null {
  const { harnessVersion, seed, capturedAt } = row;
  if (harnessVersion === null || seed === null || capturedAt === null) return null;
  return {
    job: row.job,
    steps: row.steps,
    latencyMs: row.latencyMs,
    errorRate: row.errorRate,
    harnessVersion,
    seed,
    capturedAt,
  };
}

/**
 * Every row as a {@link BaselineRow}, throwing if any is unstamped. Used only where the
 * candidate declares no defect, so the throw is a generator-drift alarm rather than a
 * tolerated skip: silently dropping an unstamped row would make the acceptance facets
 * weaker than they read.
 */
function requireMeasuredRows(rows: readonly CapturedScorecardRow[]): readonly BaselineRow[] {
  const complete = rows.map(asMeasuredRow).filter((row): row is BaselineRow => row !== null);
  if (complete.length !== rows.length) {
    throw new Error("generator drift: an undefected candidate carried an unstamped row");
  }
  return complete;
}

/**
 * Rewrites `steps` and `latencyMs` as running totals of the DRAWN values. Every drawn
 * value is at least 1, so the totals strictly increase and the row set carries
 * `rows.length` distinct values in both columns -- which is how the acceptance facets
 * avoid the generator's legitimate `uniform-metrics` collision (see the file header)
 * without touching `arbitraries.ts`. The numbers remain generated; only their collision
 * is removed.
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

/** The row set with exactly one stamp removed from exactly one row. */
function withStampRemoved(
  rows: readonly CapturedScorecardRow[],
  index: number,
  stamp: StampKey,
): readonly CapturedScorecardRow[] {
  return rows.map((row, position) => {
    if (position !== index) return row;
    return {
      ...row,
      harnessVersion: stamp === "harnessVersion" ? null : row.harnessVersion,
      seed: stamp === "seed" ? null : row.seed,
      capturedAt: stamp === "capturedAt" ? null : row.capturedAt,
    };
  });
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
  rows: readonly CapturedScorecardRow[],
  proxyCeiling: string | null,
): BaselineVerdict {
  return validateBaseline(assembleBaselineDocument({ rows, proxyCeiling }), POLICY);
}

// ---------------------------------------------------------------------------
// Arbitraries -- all derived from the shared `baselineCaseArb`
// ---------------------------------------------------------------------------

/**
 * A candidate the generator declares defect-free AND whose drawn ceiling is non-blank.
 * The ceiling filter is not cosmetic: `fc.string({ minLength: 20 })` can in principle
 * draw an all-whitespace statement, which is honestly `absent-ceiling`, and a facet
 * asserting an exact rejection set must not be flaky on it.
 */
const undefectedCaseArb: fc.Arbitrary<BaselineCase> = baselineCaseArb.filter(
  (candidate) => candidate.defect === "none" && isRetainedCeiling(candidate.proxyCeiling),
);

/** An undefected candidate whose drawn metrics are guaranteed distinct across rows. */
const measuredCaseArb: fc.Arbitrary<BaselineCase> = undefectedCaseArb.map((candidate) => ({
  ...candidate,
  rows: withDistinctMetrics(candidate.rows),
}));

/** The generator's authored-ceiling case: identical `steps` and `latencyMs` on every row. */
const authoredCeilingCaseArb: fc.Arbitrary<BaselineCase> = baselineCaseArb.filter(
  (candidate) =>
    candidate.defect === "uniform-metrics" && isRetainedCeiling(candidate.proxyCeiling),
);

/** Which row loses a stamp. */
const rowIndexArb: fc.Arbitrary<number> = fc.integer({ min: 0, max: JOB_ORDER.length - 1 });

/** Which of the three stamps is the missing one. */
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

/**
 * A verdict exhibiting `kind`, built from a measured candidate by injecting exactly the
 * one defect that kind names. Every branch yields exactly ONE rejection, which is what
 * lets facet 12 assert the kind set exactly rather than merely containing the target.
 */
function verdictExhibiting(kind: BaselineRejectionKind, candidate: BaselineCase): BaselineVerdict {
  const rows = candidate.rows;
  const ceiling = requireCeiling(candidate.proxyCeiling);
  switch (kind) {
    case "malformed":
      // Document-shaped but missing every required field except `rows`.
      return validateBaseline({ rows }, POLICY);
    case "missing-stamp":
      return verdictFor(withStampRemoved(rows, 0, "seed"), ceiling);
    case "absent-ceiling":
      return verdictFor(rows, null);
    case "altered-ceiling":
      // Raised only by the committed-artifact rule: a present but non-canonical statement.
      return checkCommittedBaseline(
        canonicalJson(assembleBaselineDocument({ rows, proxyCeiling: ceiling })),
        POLICY,
      );
    case "uniform-metrics":
      return verdictFor(withUniformMetrics(rows), ceiling);
    case "insufficient-rows":
      // Policy-derived, never a literal row count: one fewer row than the rule can evaluate.
      return verdictFor(rows.slice(0, POLICY.minRows - 1), ceiling);
  }
}

describe("Property 36: A baseline is a measurement, not a ceiling", () => {
  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("guards that the committed policy was read from disk and its rule is evaluable", () => {
    // The thresholds under test are the committed ones (AD-13), at the location the
    // whole repo already watches -- not defaults, and not values copied into this file.
    expect(BASELINE_POLICY_RELPATH).toBe("infrastructure/quality/effectiveness-baseline.json");
    expect(POLICY.version).toBeGreaterThan(0);

    // The policy schema floors all three at 2 so the rule cannot be switched off from
    // configuration. Asserting the floor, not the committed value.
    expect(POLICY.minRows).toBeGreaterThanOrEqual(2);
    expect(POLICY.minDistinctSteps).toBeGreaterThanOrEqual(2);
    expect(POLICY.minDistinctLatencyMs).toBeGreaterThanOrEqual(2);

    // A five-job baseline must be able to satisfy the rule, else the acceptance facets
    // below would be unconstructible and would pass for the wrong reason.
    expect(JOB_ORDER.length).toBeGreaterThanOrEqual(POLICY.minRows);
    expect(JOB_ORDER.length).toBeGreaterThanOrEqual(POLICY.minDistinctSteps);
    expect(JOB_ORDER.length).toBeGreaterThanOrEqual(POLICY.minDistinctLatencyMs);
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("guards that every declared BaselineDefect is drawn and carries the defect it names", () => {
    const observed = new Set<BaselineDefect>();

    fc.assert(
      fc.property(baselineCaseArb, (candidate) => {
        observed.add(candidate.defect);

        // One row per declared Job_To_Be_Done, whatever the defect (R8.1's bijection is
        // Property 32's; here it is only the shape the facets rely on).
        expect(candidate.rows).toHaveLength(JOB_ORDER.length);

        const unstamped = candidate.rows.some((row) => asMeasuredRow(row) === null);
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
    // states no run budget (R3.3): the count is inherited from `fc.configureGlobal` in
    // `frontend/src/test/setup.ts`, so this guard's strength is a function of the active
    // profile rather than of a fixed 100. Over a uniform draw of four values, n runs miss at
    // least one with probability at most 4*(3/4)^n -- about 0.22 at the local `dev` budget of
    // 10, and below 1e-11 from 100 upward. A local miss is therefore a statement about the
    // budget and not about the generator, and it is recorded here rather than hidden by
    // pinning the count back in place (I-7).
    expect([...observed].sort()).toEqual([...ALL_DEFECTS].sort());
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("accepts a measured baseline: stamped rows through buildBaseline validate clean", () => {
    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        const rows = requireMeasuredRows(candidate.rows);
        const stamp = headOf(rows);

        // The production constructor, with the document stamps taken from the measuring
        // run's own rows rather than invented here.
        const built = buildBaseline({
          rows,
          seed: stamp.seed,
          harnessVersion: stamp.harnessVersion,
          interruptionPrecision: null,
        });
        expect(built.seed).toBe(stamp.seed);
        expect(built.harnessVersion).toBe(stamp.harnessVersion);

        const accepted = requireAccepted(validateBaseline(built, POLICY));
        expect(accepted.baseline.rows).toHaveLength(JOB_ORDER.length);

        // Read back unchanged: the validator narrows, it does not re-derive.
        expect(canonicalJson(accepted.baseline.rows)).toBe(canonicalJson(built.rows));

        // Every accepted row can still name the run that produced it (R8.10).
        for (const row of accepted.baseline.rows) {
          expect(row.harnessVersion.trim().length).toBeGreaterThan(0);
          expect(Number.isFinite(row.seed)).toBe(true);
          expect(row.capturedAt.endsWith("Z")).toBe(true);
          expect(Number.isNaN(Date.parse(row.capturedAt))).toBe(false);
        }

        // `buildBaseline` writes the canonical statement, so it is reported canonical.
        expect(accepted.baseline.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
        expect(accepted.proxyCeilingIsCanonical).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects an authored ceiling as uniform-metrics, and accepts the same rows once spread", () => {
    fc.assert(
      fc.property(authoredCeilingCaseArb, (candidate) => {
        expect(candidate.defect).toBe("uniform-metrics");

        // The audit's finding, generated: identical steps and identical millisecond
        // latencies on every row, however plausible the numbers and however complete the
        // provenance stamps.
        expect(isUniformUnderPolicy(candidate.rows)).toBe(true);
        expect(requireMeasuredRows(candidate.rows)).toHaveLength(JOB_ORDER.length);

        const ceiling = requireCeiling(candidate.proxyCeiling);
        const rejected = requireRejected(verdictFor(candidate.rows, ceiling));

        // Exactly one reason, and it is the authored-ceiling one: this candidate is
        // stamped, retains its statement, and has enough rows to evaluate.
        expect(rejectedKinds(rejected)).toEqual(["uniform-metrics"]);
        const rejection = headOf(rejected.rejections);
        expect(rejection.job).toBeNull(); // a document-level finding, not a row's
        expect(rejection.detail.length).toBeGreaterThan(0);

        // The rule discriminates rather than refuses: the SAME rows, with the drawn
        // metrics spread apart, are accepted. So `uniform-metrics` is a statement about
        // the measurement, not about the shape of the document.
        const spread = withDistinctMetrics(candidate.rows);
        expect(isUniformUnderPolicy(spread)).toBe(false);
        const accepted = requireAccepted(verdictFor(spread, ceiling));
        expect(accepted.baseline.rows).toHaveLength(JOB_ORDER.length);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("accepts an undefected candidate, or rejects it solely as a genuinely uniform row set", () => {
    fc.assert(
      fc.property(undefectedCaseArb, (candidate) => {
        // Raw from the shared generator: metrics drawn per row and NOT spread. The
        // generator's `none` case can therefore collide into a uniform row set, which the
        // rule correctly rejects. The disjunction below is the honest statement of that,
        // and it is kept narrow: the rejection must be uniform-metrics ALONE, and the
        // drawn rows must independently confirm the uniformity. Any other rejection, or a
        // uniform-metrics verdict on a non-uniform row set, fails this facet.
        const verdict = verdictFor(candidate.rows, requireCeiling(candidate.proxyCeiling));

        if (verdict.outcome === "accepted") {
          expect(verdict.baseline.rows).toHaveLength(JOB_ORDER.length);
          expect(isUniformUnderPolicy(candidate.rows)).toBe(false);
          return;
        }
        expect(rejectedKinds(verdict)).toEqual(["uniform-metrics"]);
        expect(isUniformUnderPolicy(candidate.rows)).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects a row missing any one of its three provenance stamps as missing-stamp", () => {
    fc.assert(
      fc.property(measuredCaseArb, rowIndexArb, stampKeyArb, (candidate, index, stamp) => {
        const target = candidate.rows[index];
        if (target === undefined) {
          throw new Error(`generator drift: no row at index ${index}`);
        }

        const ceiling = requireCeiling(candidate.proxyCeiling);
        const holed = withStampRemoved(candidate.rows, index, stamp);
        const rejected = requireRejected(verdictFor(holed, ceiling));

        // Exactly one rejection, naming the kind, the row it is attributable to, and the
        // stamp that row could not supply. Provenance is mandatory whichever stamp it is.
        expect(rejectedKinds(rejected)).toEqual(["missing-stamp"]);
        const rejection = headOf(rejected.rejections);
        expect(rejection.job).toBe(target.job);
        expect(rejection.detail).toContain(stamp);

        // And the same document with the stamp restored is accepted, so the rejection is
        // caused by the missing stamp and nothing else.
        const accepted = requireAccepted(verdictFor(candidate.rows, ceiling));
        expect(accepted.baseline.rows).toHaveLength(JOB_ORDER.length);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects an absent or blank proxyCeiling as absent-ceiling", () => {
    fc.assert(
      fc.property(measuredCaseArb, blankCeilingArb, (candidate, blank) => {
        const rejected = requireRejected(verdictFor(candidate.rows, blank));

        // A statement that says nothing is not a retained statement, whether it is null,
        // empty, or whitespace. The rows are stamped and non-uniform, so this is the only
        // reason available.
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
        // Framing whitespace makes "verbatim" falsifiable: a validator that trimmed,
        // normalised, or re-derived the statement would return a different string.
        const retained = `${lead}${requireCeiling(candidate.proxyCeiling)}${trail}`;
        const candidateDocument = assembleBaselineDocument({
          rows: candidate.rows,
          proxyCeiling: retained,
        });

        const accepted = requireAccepted(validateBaseline(candidateDocument, POLICY));
        expect(accepted.baseline.proxyCeiling).toBe(retained);
        expect(accepted.proxyCeilingIsCanonical).toBe(false);

        // Through JSON text, byte for byte: the statement's bytes appear in the artifact
        // exactly as drawn, and come back out exactly as they went in.
        const text = canonicalJson(candidateDocument);
        expect(text).toContain(canonicalJson(retained));
        const viaText = requireAccepted(validateBaselineText(text, POLICY));
        expect(viaText.baseline.proxyCeiling).toBe(retained);

        // The COMMITTED artifact's rule is stricter: a present but non-canonical statement
        // is a named rejection, never a silent replacement with the canonical wording.
        expect(rejectedKinds(checkCommittedBaseline(text, POLICY))).toEqual(["altered-ceiling"]);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("round-trips a measured baseline through serialization byte-identically", () => {
    fc.assert(
      fc.property(measuredCaseArb, (candidate) => {
        const rows = requireMeasuredRows(candidate.rows);
        const stamp = headOf(rows);
        const built = buildBaseline({
          rows,
          seed: stamp.seed,
          harnessVersion: stamp.harnessVersion,
          interruptionPrecision: null,
        });

        const text = serializeBaseline(built);
        const accepted = requireAccepted(validateBaselineText(text, POLICY));

        // The canonical statement survives as bytes in the artifact and as a string out of
        // the validator -- retained, not regenerated.
        expect(text).toContain(canonicalJson(SCRIPTED_PROXY_CEILING));
        expect(accepted.baseline.proxyCeiling).toBe(SCRIPTED_PROXY_CEILING);
        expect(accepted.proxyCeilingIsCanonical).toBe(true);

        // Re-emitting what the validator returned reproduces identical bytes (Req 4.6).
        expect(serializeBaseline(accepted.baseline)).toBe(text);

        // And the stricter committed-artifact rule accepts it -- asserted on GENERATED
        // input, deliberately not on the committed artifact (see the file header).
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
        // One row short of the committed minimum, derived from the policy rather than
        // written as a number here.
        const ceiling = requireCeiling(candidate.proxyCeiling);
        const tooFew = candidate.rows.slice(0, POLICY.minRows - 1);
        expect(tooFew.length).toBeLessThan(POLICY.minRows);

        const rejected = requireRejected(verdictFor(tooFew, ceiling));

        // Unevaluable is a rejection, not a pass (I-7): a one-row baseline is trivially
        // uniform, so accepting it would switch the authored-ceiling rule off.
        expect(rejectedKinds(rejected)).toEqual(["insufficient-rows"]);
        expect(headOf(rejected.rejections).detail.length).toBeGreaterThan(0);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 36: A baseline is a measurement, not a ceiling
  it("rejects anything that is not a baseline document as malformed, and never throws", () => {
    // The text path: unparseable JSON, or JSON that is not a baseline document, is a
    // named verdict rather than an exception, so one caller shape handles every failure.
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

          // A rejection is never a bare boolean false: it states its kind, its
          // attribution, and a non-empty detail naming what was observed.
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
