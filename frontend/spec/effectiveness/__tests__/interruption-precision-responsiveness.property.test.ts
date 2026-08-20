/**
 * Feature: purpose-achievement-audit, Property 34: Interruption precision responds to
 * its inputs
 *
 * Validates: Requirements 8.5
 *
 * R8.5 does not ask whether the ratio is arithmetically right. The audit already found
 * the formula correct and the measurement absent: the value was `0.75` by construction,
 * the same array was duplicated in the spec, and the committed baseline recorded the
 * identical number, so the ratchet compared a constant against itself. What R8.5 demands
 * is therefore a DERIVATION claim -- the value must be computed from interruptions raised
 * during an executed run, and it must MOVE when those interruptions differ.
 *
 * So this file quantifies over generated interruption sets and over seeds, drives the
 * shipped `@lib/interruption-precision` pipeline (open a run ledger -> record observed
 * facts -> seal -> compute -> audit two seeds), and asserts what an authored constant
 * cannot satisfy. Nothing here states a warrant: a generated interruption carries one
 * bit, that bit is realized as OBSERVED FACTS, and whether the interruption was
 * warranted is left to the module's own `warrantOf`/`isWarranted`. The expected value is
 * derived through those same two functions rather than by restating the warrant rules
 * here, so this test cannot drift from R13.1's definition and cannot silently re-define
 * "worth it".
 *
 * Six facets. No facet states a run budget: `numRuns` is inherited from the
 * `HYPOTHESIS_PROFILE` profile via `fc.configureGlobal` in `frontend/src/test/setup.ts`
 * (R3.1-R3.3), the same way the Python side inherits `max_examples` from the root
 * `conftest.py`. A per-call `{ numRuns }` would override that global, so there is none:
 *
 *  1. RESPONSIVENESS AT THE SEED (the reason this file exists). For any generated set,
 *     two runs at two seeds whose collected interruptions differ materially in warrant
 *     content produce values whose divergence `auditSeedResponsiveness` classifies
 *     `responsive` against the COMMITTED threshold -- read from
 *     `infrastructure/quality/effectiveness-precision.json` through
 *     `parseInterruptionPrecisionPolicy`, never typed into this file.
 *  2. THE ADVERSARIAL CONSTANT. A computation that returns the same number whatever it
 *     is handed is exactly a pair of runs whose inputs differ and whose reported values
 *     coincide -- divergence 0. Mechanism 4 makes a bare number unpassable to the audit
 *     (the ingress takes a branded outcome, not a `number`), so the constant is realized
 *     the only way it can reach this API: two genuinely different interruption sets whose
 *     warranted fractions are equal. The audit must report `unresponsive`, and
 *     `unresponsive` must not be readable as a pass.
 *  3. RESPONSIVENESS AT ONE BIT. Flipping a single generated `warranted` flag moves the
 *     computed value by exactly `1 / total` -- the finest-grained statement of the same
 *     claim, and design Property 34's flip clause verbatim.
 *  4. THE DEFINITION. For any generated set the computed value is warranted / total over
 *     the run's OWN collected interruptions, its `warrantCounts` partition the set across
 *     `WARRANT_KINDS`, and an empty collection is not a number at all.
 *  5. HONEST INDETERMINACY (I-7). Every `IndeterminateReason` these generators can reach
 *     -- no collection, broken provenance (a non-monotonic clock), a witness that does
 *     not cover its body -- is reported as that reason, and `requireComputedOutcome`
 *     REFUSES the outcome instead of coercing it to `0` or a default. A
 *     `SeedResponsivenessVerdict` of `inapplicable` is likewise distinguishable from
 *     `responsive` and is not a pass: `responsive` is the only passing status.
 *  6. AUTHORSHIP IS DETECTABLE. For any generated set, the authored form of that same
 *     data -- committed list, authored warrant flags, and the metric assigned the very
 *     number the run measured -- is reported by `findCommittedInterruptionLiterals`,
 *     while an empty accumulator is not a finding. The scanner judges the derivation, so
 *     a literal equal to the measurement is still a finding.
 *
 * Why these suffice: facets 1 and 3 falsify seed-invariance at both granularities R8.5
 * names, facet 2 falsifies the constant that motivated the requirement, facet 4 pins the
 * ratio to the run's own data, facet 5 closes the skip-as-pass hole the audit found, and
 * facet 6 keeps the authored shape mechanically detectable. A guard facet proves the
 * generated space actually reaches warranted and unwarranted interruptions, every warrant
 * kind, and both empty and non-empty collections, so no facet can pass vacuously.
 *
 * Deliberately NOT re-asserted here: the pure ratio kernel `interruptionPrecision` --
 * bounds, the empty-window `null`, the all/none boundaries, and an independent oracle --
 * which is Property 18's subject in
 * `frontend/src/lib/__tests__/interruption-precision.property.test.ts`. That file tests
 * the FORMULA over plain arrays; this one tests the MEASUREMENT over sealed runs.
 *
 * NOTE (task 11.6): `frontend/tsconfig.json` does not `include` this directory -- only
 * `spec/effectiveness/harness.ts` and `e2e-entry.ts` are listed -- so `pnpm typecheck` and
 * `pnpm build` do not type-check this file or the three property tests already beside it.
 * Vitest transpiles without checking, so the assertions below run, but the compile-time
 * guarantees this file leans on (the exhaustive `Record<WarrantKind, number>` and
 * `Record<IndeterminateReason, boolean>`, and mechanism 4's brands rejecting an authored
 * outcome) are only enforced where a compiler sees the file. Adding
 * `"spec/effectiveness"` to that `include` is a one-line change outside this task's scope;
 * it is stated rather than assumed (I-7).
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  type ComputedInterruptionPrecision,
  type ConfirmedStake,
  INTERRUPTION_PRECISION_POLICY_RELPATH,
  type IndeterminateInterruptionPrecision,
  type IndeterminateReason,
  type Interruption,
  type InterruptionObservation,
  type InterruptionPrecisionOutcome,
  type InterruptionPrecisionPolicy,
  InterruptionPrecisionUnavailableError,
  type RunContext,
  type SealedInterruptionLedger,
  type SeedProbe,
  type SeedResponsivenessVerdict,
  WARRANT_KINDS,
  type WarrantKind,
  auditSeedResponsiveness,
  computeInterruptionPrecision,
  findCommittedInterruptionLiterals,
  isWarranted,
  openInterruptionLedger,
  parseInterruptionPrecisionPolicy,
  requireComputedOutcome,
  warrantOf,
} from "@lib/interruption-precision";

import { interruptionArb, interruptionSetArb, interruptionsArb } from "../arbitraries";

// ---------------------------------------------------------------------------
// The committed threshold -- loaded, never typed here
// ---------------------------------------------------------------------------

/** `frontend/spec/effectiveness/__tests__` -> the repository root. */
const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");

/**
 * The one threshold this file compares against, read from the committed policy through
 * the shipped parser. A number typed into this test would be the very defect R8.5
 * exists to catch, and an unreadable policy is `unavailable` -- so this throws naming the
 * file rather than substituting a default (I-7).
 */
function loadCommittedPolicy(): InterruptionPrecisionPolicy {
  const path = join(REPO_ROOT, INTERRUPTION_PRECISION_POLICY_RELPATH);
  const outcome = parseInterruptionPrecisionPolicy(
    readFileSync(path, "utf8"),
    INTERRUPTION_PRECISION_POLICY_RELPATH,
  );
  if (outcome.status !== "loaded") {
    throw new Error(
      `Property 34 cannot run without the committed threshold at ${path}: ${outcome.detail}`,
    );
  }
  return outcome.policy;
}

const POLICY: InterruptionPrecisionPolicy = loadCommittedPolicy();

/**
 * Comparison tolerance for a computed ratio. Two divisions of the same rational are
 * bitwise equal, but the facets below compare DIFFERENCES of ratios, so every
 * floating-point assertion goes through this explicit epsilon rather than `===`.
 */
const PRECISION_EPSILON = 1e-12;

function expectClose(actual: number, expected: number): void {
  expect(Math.abs(actual - expected)).toBeLessThanOrEqual(PRECISION_EPSILON);
}

// ---------------------------------------------------------------------------
// Realizing a generated interruption as something a collector could have observed
// ---------------------------------------------------------------------------

const NO_STAKES: readonly ConfirmedStake[] = [];
const IRREVERSIBLE: readonly ConfirmedStake[] = ["irreversible"];
const HIGH_BLAST: readonly ConfirmedStake[] = ["high-blast"];
const UNCERTAIN: readonly ConfirmedStake[] = ["uncertain"];

/** Observed facts behind an interruption that was worth the operator's attention. */
interface WarrantingFacts {
  readonly outcomeChanged: boolean;
  readonly confirmedStakes: readonly ConfirmedStake[];
}

/**
 * The four ways a review can be warranted, cycled by observation index so a generated
 * set reaches every warranting `WarrantKind` rather than only `outcome-changed`. Which
 * kind these facts earn is `warrantOf`'s judgement, not this table's.
 */
const WARRANTING_FACTS: readonly WarrantingFacts[] = [
  { outcomeChanged: true, confirmedStakes: NO_STAKES },
  { outcomeChanged: false, confirmedStakes: IRREVERSIBLE },
  { outcomeChanged: false, confirmedStakes: HIGH_BLAST },
  { outcomeChanged: false, confirmedStakes: UNCERTAIN },
];

/** A false interruption: the review changed nothing and confirmed no stake. */
const INERT_FACTS: WarrantingFacts = { outcomeChanged: false, confirmedStakes: NO_STAKES };

/**
 * Turn one generated `Interruption` into an `InterruptionObservation` -- facts a
 * collector could have written down. The generator's single bit selects between
 * warranting and inert FACTS; it is never copied into a `warranted` field, because the
 * ledger derives that and this test must not pre-empt it.
 */
function observationOf(
  interruption: Interruption,
  index: number,
  scenarioId: string,
): InterruptionObservation {
  const warranting = WARRANTING_FACTS[index % WARRANTING_FACTS.length] ?? INERT_FACTS;
  const facts = interruption.warranted ? warranting : INERT_FACTS;
  return {
    interruptionId: `${scenarioId}#${index}`,
    scenarioId,
    outcomeChanged: facts.outcomeChanged,
    confirmedStakes: facts.confirmedStakes,
    evidence: `announced at ${scenarioId} position ${index}; operator response observed`,
  };
}

/** What a generated run is: an identity, a scenario, and the interruptions it raised. */
interface LedgerPlan {
  readonly run: RunContext;
  readonly scenarioId: string;
  readonly interruptions: readonly Interruption[];
}

interface SealedRun {
  readonly sealed: SealedInterruptionLedger;
  readonly observations: readonly InterruptionObservation[];
}

function runContext(runId: string, seed: number): RunContext {
  return {
    runId,
    seed,
    harnessVersion: "34.0.0-property",
    startedAt: "2026-07-04T11:22:33.444Z",
  };
}

/**
 * Drive the real collection path: open an append-only ledger, record one observation per
 * generated interruption, seal it. The clock is a counter rather than a timer so the
 * window is monotonic without touching wall time; `direction: "backward"` hands the
 * ledger a clock that runs the wrong way, which is how the `provenance-broken` state is
 * reached honestly -- by a ledger the module itself refuses, not by an edited record.
 */
function sealPlan(plan: LedgerPlan, direction: "forward" | "backward" = "forward"): SealedRun {
  let tick = direction === "forward" ? 0 : 1_000_000;
  const ledger = openInterruptionLedger(plan.run, () => {
    tick += direction === "forward" ? 1 : -1;
    return tick;
  });
  const observations = plan.interruptions.map((interruption, index) =>
    observationOf(interruption, index, plan.scenarioId),
  );
  for (const observation of observations) {
    ledger.record(observation);
  }
  return { sealed: ledger.seal(), observations };
}

/**
 * The same sealed artifact with a witness that no longer covers its body -- the shape an
 * edited or reassembled ledger has. Built by SPREADING the sealed object (no cast, no
 * `as unknown as`): the brand travels with the spread, so this is precisely the
 * "assembled after the run" artifact the witness exists to catch.
 */
function withTamperedWitness(sealed: SealedInterruptionLedger): SealedInterruptionLedger {
  return { ...sealed, witness: `${sealed.witness}-edited` };
}

/**
 * The expected ratio, derived through the module's OWN warrant derivation. This is the
 * oracle: it re-uses `warrantOf` and `isWarranted` deliberately, so the facets check that
 * the pipeline counts the run's collected data, without this file holding a second,
 * drift-prone copy of R13.1's warrant rules.
 */
function expectedPrecisionOf(observations: readonly InterruptionObservation[]): number {
  if (observations.length === 0) {
    throw new Error("expectedPrecisionOf: warranted / total is undefined over an empty collection");
  }
  let warranted = 0;
  for (const observation of observations) {
    if (isWarranted(warrantOf(observation))) warranted += 1;
  }
  return warranted / observations.length;
}

function emptyWarrantCounts(): Record<WarrantKind, number> {
  // Exhaustive by construction: a new WarrantKind fails this literal wherever a compiler
  // sees the file (see the header NOTE on the tsconfig `include` gap).
  return {
    "outcome-changed": 0,
    "confirmed-irreversible": 0,
    "confirmed-high-blast": 0,
    "confirmed-uncertain": 0,
    unwarranted: 0,
  };
}

function derivedWarrantCounts(
  observations: readonly InterruptionObservation[],
): Record<WarrantKind, number> {
  const counts = emptyWarrantCounts();
  for (const observation of observations) {
    counts[warrantOf(observation)] += 1;
  }
  return counts;
}

// ---------------------------------------------------------------------------
// Narrowing helpers -- an indeterminate outcome is never read as a number
// ---------------------------------------------------------------------------

function expectComputed(outcome: InterruptionPrecisionOutcome): ComputedInterruptionPrecision {
  expect(outcome.status).toBe("computed");
  return requireComputedOutcome(outcome);
}

function expectIndeterminate(
  outcome: InterruptionPrecisionOutcome,
): IndeterminateInterruptionPrecision {
  if (outcome.status === "computed") {
    throw new Error(
      `expected an indeterminate outcome, got a computed value ${outcome.value} over ` +
        `${outcome.total} interruption(s)`,
    );
  }
  return outcome;
}

/**
 * `responsive` is the ONLY passing verdict (R8.5). `unresponsive` is the constant's
 * signature and `inapplicable` is an undecided probe -- neither demonstrates the
 * difference R8.5 requires, so neither may be read as a success (I-7).
 */
function passesSeedResponsiveness(verdict: SeedResponsivenessVerdict): boolean {
  return verdict.status === "responsive";
}

/** Assert a probe belongs to the run it claims, and hand it back for value assertions. */
function expectProbe(
  probe: SeedProbe | null,
  expected: { readonly runId: string; readonly seed: number; readonly total: number },
): SeedProbe {
  if (probe === null) {
    throw new Error(`expected a probe for run "${expected.runId}", got none`);
  }
  expect(probe.runId).toBe(expected.runId);
  expect(probe.seed).toBe(expected.seed);
  expect(probe.total).toBe(expected.total);
  expect(probe.witness.length).toBeGreaterThan(0);
  return probe;
}

/**
 * The authored form of an interruption set: a committed list, warrant flags asserted
 * rather than observed, and the metric assigned a numeric literal. Rendered from
 * GENERATED data and the run's OWN measured value, so facet 6 shows the scanner judging
 * the derivation rather than the number.
 */
function renderAuthoredSource(interruptions: readonly Interruption[], measured: number): string {
  const rows = interruptions.map(
    (interruption) => `  { warranted: ${interruption.warranted ? "true" : "false"} },`,
  );
  return [
    "const committedInterruptionSamples: readonly Interruption[] = [",
    ...rows,
    "];",
    `export const interruptionPrecision = ${measured};`,
  ].join("\n");
}

function findingsByKind(source: string, kind: string): number {
  return findCommittedInterruptionLiterals(source).filter((finding) => finding.kind === kind).length;
}

// ---------------------------------------------------------------------------
// Generators (composed from the shared effectiveness arbitraries)
// ---------------------------------------------------------------------------

/** A seed base; each facet derives a second, DIFFERENT seed from it. */
const seedBaseArb = fc.integer({ min: 1, max: 0xffff });

/** A non-empty raised set -- the case where a ratio exists at all. */
const raisedSetArb = interruptionsArb({ minLength: 1, maxLength: 16 });

/** Possibly empty, so the honest `indeterminate` branch is inside the quantifier. */
const anySetArb = interruptionsArb({ minLength: 0, maxLength: 12 });

/** Small and possibly empty, so the guard facet reaches both outcome branches often. */
const guardSetArb = interruptionsArb({ minLength: 0, maxLength: 6 });

const SCENARIO = "jtbd.resolve-escalation";

/**
 * The indeterminate reasons these generators can reach, for iteration. The exhaustive
 * `Record<IndeterminateReason, boolean>` below pins the list to the union at compile time,
 * and the facet also asserts the two agree AT RUNTIME -- so a reason added to the module
 * cannot be quietly left unreached here even while the tsconfig gap in the header NOTE
 * stands.
 */
const REACHABLE_REASONS: readonly IndeterminateReason[] = [
  "no-interruptions-collected",
  "provenance-broken",
  "witness-mismatch",
];

describe("Property 34: Interruption precision responds to its inputs", () => {
  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("guards the generated space reaches both warrants, every warrant kind, and both outcome branches", () => {
    const kindsSeen = new Set<WarrantKind>();
    let sawWarranted = false;
    let sawUnwarranted = false;
    let sawEmptyCollection = false;
    let sawComputedOutcome = false;

    fc.assert(
      fc.property(guardSetArb, interruptionArb, seedBaseArb, (set, single, seed) => {
        for (const interruption of [...set, single]) {
          if (interruption.warranted) sawWarranted = true;
          else sawUnwarranted = true;
        }
        const { sealed, observations } = sealPlan({
          run: runContext(`guard-${seed}`, seed),
          scenarioId: SCENARIO,
          interruptions: set,
        });
        for (const observation of observations) {
          kindsSeen.add(warrantOf(observation));
        }
        const outcome = computeInterruptionPrecision(sealed);
        if (outcome.status === "computed") sawComputedOutcome = true;
        else sawEmptyCollection = true;
      }),
    );

    expect(sawWarranted).toBe(true);
    expect(sawUnwarranted).toBe(true);
    expect(sawEmptyCollection).toBe(true);
    expect(sawComputedOutcome).toBe(true);
    expect([...kindsSeen].sort()).toEqual([...WARRANT_KINDS].sort());

    // The threshold is loaded, positive, and low enough for the 0.5 divergence the
    // seed-responsiveness facet constructs -- stated here rather than assumed.
    expect(POLICY.source).toBe(INTERRUPTION_PRECISION_POLICY_RELPATH);
    expect(POLICY.minSeedDivergence).toBeGreaterThan(0);
    expect(POLICY.minSeedDivergence).toBeLessThanOrEqual(0.5);
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("two seeds whose collected interruptions differ are classified responsive against the committed threshold", () => {
    fc.assert(
      fc.property(raisedSetArb, seedBaseArb, (shared, seed) => {
        // Both runs collect the generated set; they then diverge only in the WARRANT
        // CONTENT of an equally sized block, so the values differ by exactly one half and
        // nothing but the interruptions can explain the difference.
        const block = shared.length;
        const warrantedBlock: readonly Interruption[] = Array.from({ length: block }, () => ({
          warranted: true,
        }));
        const inertBlock: readonly Interruption[] = Array.from({ length: block }, () => ({
          warranted: false,
        }));

        const left = sealPlan({
          run: runContext(`run-left-${seed}`, seed),
          scenarioId: SCENARIO,
          interruptions: [...shared, ...warrantedBlock],
        });
        const right = sealPlan({
          run: runContext(`run-right-${seed}`, seed + 1),
          scenarioId: SCENARIO,
          interruptions: [...shared, ...inertBlock],
        });

        const verdict = auditSeedResponsiveness(left.sealed, right.sealed, POLICY);
        expect(verdict.status).toBe("responsive");
        expect(verdict.reason).toBe("value-responded");
        expect(passesSeedResponsiveness(verdict)).toBe(true);

        const expectedLeft = expectedPrecisionOf(left.observations);
        const expectedRight = expectedPrecisionOf(right.observations);
        const leftProbe = expectProbe(verdict.left, {
          runId: `run-left-${seed}`,
          seed,
          total: 2 * block,
        });
        const rightProbe = expectProbe(verdict.right, {
          runId: `run-right-${seed}`,
          seed: seed + 1,
          total: 2 * block,
        });
        expectClose(leftProbe.value, expectedLeft);
        expectClose(rightProbe.value, expectedRight);

        // The divergence is the observed one, it is the construction's 0.5, and it clears
        // the COMMITTED floor the verdict carries.
        expect(verdict.divergence).not.toBeNull();
        const divergence = verdict.divergence ?? Number.NaN;
        expectClose(divergence, Math.abs(expectedLeft - expectedRight));
        expectClose(divergence, 0.5);
        expect(divergence).toBeGreaterThanOrEqual(POLICY.minSeedDivergence);
        expect(verdict.minSeedDivergence).toBe(POLICY.minSeedDivergence);
        expect(verdict.policySource).toBe(POLICY.source);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("a value that does not move when its inputs do is classified unresponsive, never a pass", () => {
    fc.assert(
      fc.property(raisedSetArb, seedBaseArb, (shared, seed) => {
        // The adversarial case: a computation that reports the same number whatever it is
        // handed. A bare literal cannot reach this API at all (the audit takes branded
        // outcomes, not numbers), so the constant is realized as its observable signature
        // -- two runs at two seeds whose interruption sets differ in scenario and in size,
        // yet whose reported values coincide. Divergence 0 is what a hardcoded 0.75 would
        // produce, and the audit must refuse it.
        const left = sealPlan({
          run: runContext(`run-constant-left-${seed}`, seed),
          scenarioId: "jtbd.left-scenario",
          interruptions: shared,
        });
        const right = sealPlan({
          run: runContext(`run-constant-right-${seed}`, seed + 1),
          scenarioId: "jtbd.right-scenario",
          interruptions: [...shared, ...shared],
        });

        const expectedLeft = expectedPrecisionOf(left.observations);
        const expectedRight = expectedPrecisionOf(right.observations);
        expectClose(expectedLeft, expectedRight);

        const verdict = auditSeedResponsiveness(left.sealed, right.sealed, POLICY);
        expect(verdict.status).toBe("unresponsive");
        expect(verdict.reason).toBe("value-did-not-respond");
        expect(passesSeedResponsiveness(verdict)).toBe(false);

        const divergence = verdict.divergence ?? Number.NaN;
        expectClose(divergence, 0);
        expect(divergence).toBeLessThan(POLICY.minSeedDivergence);

        // The refusal names both sides and the committed threshold, so a failure report
        // can be acted on rather than merely observed.
        expect(verdict.detail).toContain(String(POLICY.minSeedDivergence));
        expect(verdict.detail).toContain(POLICY.source);
        expectProbe(verdict.left, {
          runId: `run-constant-left-${seed}`,
          seed,
          total: shared.length,
        });
        expectProbe(verdict.right, {
          runId: `run-constant-right-${seed}`,
          seed: seed + 1,
          total: 2 * shared.length,
        });
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("flipping one collected warranted flag moves the computed value by exactly 1 / total", () => {
    fc.assert(
      fc.property(interruptionSetArb, seedBaseArb, ({ interruptions, index }, seed) => {
        const flipped: readonly Interruption[] = interruptions.map((interruption, position) =>
          position === index ? { warranted: !interruption.warranted } : interruption,
        );

        const before = sealPlan({
          run: runContext(`run-before-${seed}`, seed),
          scenarioId: SCENARIO,
          interruptions,
        });
        const after = sealPlan({
          run: runContext(`run-after-${seed}`, seed + 1),
          scenarioId: SCENARIO,
          interruptions: flipped,
        });

        const beforeValue = expectComputed(computeInterruptionPrecision(before.sealed)).value;
        const afterValue = expectComputed(computeInterruptionPrecision(after.sealed)).value;

        // One bit of input moves the output by one interruption's worth of the ratio: the
        // finest-grained form of "the value is derived from the collected set".
        expectClose(Math.abs(afterValue - beforeValue), 1 / interruptions.length);
        expectClose(beforeValue, expectedPrecisionOf(before.observations));
        expectClose(afterValue, expectedPrecisionOf(after.observations));
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("the computed value is warranted / total over the run's own collected interruptions", () => {
    fc.assert(
      fc.property(anySetArb, seedBaseArb, (interruptions, seed) => {
        const runId = `run-definition-${seed}`;
        const { sealed, observations } = sealPlan({
          run: runContext(runId, seed),
          scenarioId: SCENARIO,
          interruptions,
        });
        const outcome = computeInterruptionPrecision(sealed);

        if (interruptions.length === 0) {
          // No collection, no number -- asserted in full by the indeterminacy facet.
          expect(expectIndeterminate(outcome).reason).toBe("no-interruptions-collected");
          return;
        }

        const computed = expectComputed(outcome);
        const expectedCounts = derivedWarrantCounts(observations);
        const expectedWarranted = observations.filter((observation) =>
          isWarranted(warrantOf(observation)),
        ).length;

        expectClose(computed.value, expectedPrecisionOf(observations));
        expect(computed.total).toBe(interruptions.length);
        expect(computed.warranted).toBe(expectedWarranted);
        expect(computed.value).toBeGreaterThanOrEqual(0);
        expect(computed.value).toBeLessThanOrEqual(1);

        // The counts partition the collected set across every warrant kind, so the ratio
        // is accounted for rather than merely reported.
        let counted = 0;
        for (const kind of WARRANT_KINDS) {
          expect(computed.warrantCounts[kind]).toBe(expectedCounts[kind]);
          counted += computed.warrantCounts[kind];
        }
        expect(counted).toBe(computed.total);

        // A value never travels without the run that produced it or the honest ceiling.
        expect(computed.run.runId).toBe(runId);
        expect(computed.run.seed).toBe(seed);
        expect(computed.witness).toBe(sealed.witness);
        expect(computed.proxyCeiling.length).toBeGreaterThan(0);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("every reachable indeterminate reason is reported and refused rather than coerced to a number", () => {
    const reasonsReached: Record<IndeterminateReason, boolean> = {
      "no-interruptions-collected": false,
      "provenance-broken": false,
      "witness-mismatch": false,
    };

    fc.assert(
      fc.property(raisedSetArb, seedBaseArb, (interruptions, seed) => {
        const cases: readonly { reason: IndeterminateReason; ledger: SealedInterruptionLedger }[] = [
          {
            reason: "no-interruptions-collected",
            ledger: sealPlan({
              run: runContext(`run-empty-${seed}`, seed),
              scenarioId: SCENARIO,
              interruptions: [],
            }).sealed,
          },
          {
            reason: "provenance-broken",
            ledger: sealPlan(
              {
                run: runContext(`run-backwards-${seed}`, seed),
                scenarioId: SCENARIO,
                interruptions,
              },
              "backward",
            ).sealed,
          },
          {
            reason: "witness-mismatch",
            ledger: withTamperedWitness(
              sealPlan({
                run: runContext(`run-tampered-${seed}`, seed),
                scenarioId: SCENARIO,
                interruptions,
              }).sealed,
            ),
          },
        ];

        for (const { reason, ledger } of cases) {
          const outcome = computeInterruptionPrecision(ledger);
          const failing = expectIndeterminate(outcome);

          // The reason is declared and the detail is diagnosable; there is no `value`
          // field to misread, and nothing anywhere reports 0.
          expect(failing.reason).toBe(reason);
          expect(failing.detail.length).toBeGreaterThan(0);
          expect(failing.proxyCeiling.length).toBeGreaterThan(0);
          expect(Object.keys(failing)).not.toContain("value");
          reasonsReached[reason] = true;

          // I-7: the measured ingress refuses the outcome instead of substituting a
          // default that the ratchet would then skip over as a pass.
          let refusal: unknown = null;
          try {
            requireComputedOutcome(outcome);
          } catch (error) {
            refusal = error;
          }
          expect(refusal).toBeInstanceOf(InterruptionPrecisionUnavailableError);
          if (refusal instanceof InterruptionPrecisionUnavailableError) {
            expect(refusal.reason).toBe(reason);
          }
        }
      }),
    );

    // The union and this file's list agree, and every reason was actually observed.
    expect(Object.keys(reasonsReached).sort()).toEqual([...REACHABLE_REASONS].sort());
    for (const reason of REACHABLE_REASONS) {
      expect(reasonsReached[reason]).toBe(true);
    }
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("an inapplicable seed verdict is distinguishable from responsive and is not a pass", () => {
    fc.assert(
      fc.property(raisedSetArb, seedBaseArb, (interruptions, seed) => {
        const sameSeedLeft = sealPlan({
          run: runContext(`run-same-seed-a-${seed}`, seed),
          scenarioId: "jtbd.left-scenario",
          interruptions,
        }).sealed;
        const sameSeedRight = sealPlan({
          run: runContext(`run-same-seed-b-${seed}`, seed),
          scenarioId: "jtbd.right-scenario",
          interruptions: [...interruptions, { warranted: true }],
        }).sealed;

        const sameRun = runContext(`run-repeated-${seed}`, seed);
        const sameRunLeft = sealPlan({
          run: sameRun,
          scenarioId: "jtbd.left-scenario",
          interruptions,
        }).sealed;
        const sameRunRight = sealPlan({
          run: sameRun,
          scenarioId: "jtbd.right-scenario",
          interruptions: [...interruptions, { warranted: false }],
        }).sealed;

        const emptySide = sealPlan({
          run: runContext(`run-no-data-${seed}`, seed),
          scenarioId: SCENARIO,
          interruptions: [],
        }).sealed;
        const populatedSide = sealPlan({
          run: runContext(`run-with-data-${seed}`, seed + 1),
          scenarioId: SCENARIO,
          interruptions,
        }).sealed;

        // Two seeds that happened to raise the same scenario/warrant content cannot show
        // the value responding -- undecided, and therefore not a pass either.
        const identicalLeft = sealPlan({
          run: runContext(`run-identical-a-${seed}`, seed),
          scenarioId: SCENARIO,
          interruptions,
        }).sealed;
        const identicalRight = sealPlan({
          run: runContext(`run-identical-b-${seed}`, seed + 1),
          scenarioId: SCENARIO,
          interruptions,
        }).sealed;

        const undecided: readonly { reason: string; verdict: SeedResponsivenessVerdict }[] = [
          {
            reason: "same-seed",
            verdict: auditSeedResponsiveness(sameSeedLeft, sameSeedRight, POLICY),
          },
          { reason: "same-run", verdict: auditSeedResponsiveness(sameRunLeft, sameRunRight, POLICY) },
          {
            reason: "precision-indeterminate",
            verdict: auditSeedResponsiveness(emptySide, populatedSide, POLICY),
          },
          {
            reason: "identical-interruption-sets",
            verdict: auditSeedResponsiveness(identicalLeft, identicalRight, POLICY),
          },
        ];

        for (const { reason, verdict } of undecided) {
          expect(verdict.status).toBe("inapplicable");
          expect(verdict.reason).toBe(reason);
          expect(verdict.detail.length).toBeGreaterThan(0);

          // `inapplicable` is a THIRD state: not `responsive`, and not the constant's
          // `unresponsive` either. Reading it as a success is the skip-as-pass hole.
          expect(verdict.status).not.toBe("responsive");
          expect(verdict.status).not.toBe("unresponsive");
          expect(passesSeedResponsiveness(verdict)).toBe(false);
        }

        // An indeterminate side yields no probe for that side, so a caller cannot read a
        // value out of a run that produced none.
        const indeterminateSide = auditSeedResponsiveness(emptySide, populatedSide, POLICY);
        expect(indeterminateSide.left).toBeNull();
        expect(indeterminateSide.divergence).toBeNull();
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 34: Interruption precision responds to its inputs
  it("the authored form of a measured set is still detected in source, while an empty accumulator is not", () => {
    fc.assert(
      fc.property(raisedSetArb, seedBaseArb, (interruptions, seed) => {
        const { sealed } = sealPlan({
          run: runContext(`run-authored-${seed}`, seed),
          scenarioId: SCENARIO,
          interruptions,
        });
        const measured = expectComputed(computeInterruptionPrecision(sealed)).value;

        // The number here is the one the run actually measured, and the source is still a
        // finding: the scanner judges the DERIVATION, so a literal equal to the
        // measurement is rejected exactly like an invented one (R8.5's third clause).
        const authored = renderAuthoredSource(interruptions, measured);
        expect(findingsByKind(authored, "authored-warrant-flag")).toBe(interruptions.length);
        expect(findingsByKind(authored, "committed-interruption-list")).toBe(1);
        expect(findingsByKind(authored, "hardcoded-precision-value")).toBe(1);
        expect(findCommittedInterruptionLiterals(authored)).toHaveLength(interruptions.length + 2);

        // The contrast that keeps the scanner usable: an EMPTY accumulator -- what a
        // collector legitimately declares before a run fills it -- is not a finding.
        const accumulator = "const collectedInterruptions: CollectedInterruption[] = [];";
        expect(findCommittedInterruptionLiterals(accumulator)).toHaveLength(0);
      }),
    );
  });
});
