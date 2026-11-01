/**
 * The fast-check example budget is a total function of the profile name.
 *
 * Feature: decision-quality-proof, task 1.5.
 *
 * **Validates: Requirements 3.1, 3.2, 3.5, 3.9**
 *
 * What this closes
 * ----------------
 *
 * The Python side inherits `max_examples` from a named Hypothesis profile, so a local run
 * is cheap (invariant I-0) and a CI run satisfies the >=100-iteration obligation, and
 * neither is achieved by a literal written into a test file. The TypeScript side had no
 * such mechanism: all five declared console property files stated `{ numRuns: 100 }` at
 * every call site, which pins the local cost to the CI cost and cannot be tuned per
 * environment at all.
 *
 * An earlier draft of this header put the pre-removal call-site total at 48. **That
 * number is NOT derivable from this tree and is therefore not asserted.** All five
 * declared files were untracked until task 1.1 committed them, and task 1.3 removed the
 * call sites, so no pre-removal revision exists to diff against - the figure is an
 * unverifiable third-party claim, and CLAUDE.md requires any number stated to be
 * derivable from a gate. What IS mechanical is the post-condition, and it is checked
 * elsewhere rather than restated here: the five declared files now state no `numRuns` at
 * all, and `tests/verify/test_property_inventory_consistency.py` (task 1.4) fails on any
 * that reappears while reporting the count itself (CF-13's discipline - the gate produces
 * the number, the prose does not).
 *
 * `src/test/fc-budget.ts` is the missing mechanism and `src/test/setup.ts` is the single
 * place it is applied. This file is the proof that the resolver is *total*, that the
 * global actually *took*, and that the run record says which budget was in force - the
 * three ways the mechanism can silently fail.
 *
 * Why the second half matters as much as the first (R3.9)
 * ------------------------------------------------------
 *
 * `fc.configureGlobal` returns `void`. If the call were removed, reordered after the first
 * property, or shadowed by a second setup file, every property in the console would fall
 * back to **fast-check's own implicit default of 100** - a number that looks CI-legal
 * while costing a laptop ten times the intended `dev` budget of 10. Nothing would go red.
 * So the last test here reads the configuration *back* and compares it against the
 * resolver's answer for the active profile, which also has the effect of carrying the
 * effective count into `artifacts/test-reports/vitest.json` as a named per-file verdict -
 * the machine-readable record `frontend/spec/check_fe_invariants.py` reads.
 *
 * Why matching is exact and unset resolves to the CHEAP profile
 * ------------------------------------------------------------
 *
 * Two deliberate asymmetries with the Python side, both asserted below because both look
 * like bugs until you know why:
 *
 * 1. Python resolves an unset `HYPOTHESIS_PROFILE` to `default` (500); this resolves it to
 *    `dev` (10). An unset variable is the *local* case, and under I-0 the local case must
 *    be the cheap one. CI sets the variable explicitly - `frontend.yml`'s `quality`
 *    (`:41`) and `mutation` (`:710`) jobs both set `HYPOTHESIS_PROFILE: heavy`, verified
 *    by reading those two lines. `heavy` is 100, the same per-call value the removed sites
 *    stated, so the inversion is cost-neutral in CI and R3.5's ">= 100" holds where it
 *    matters.
 * 2. Matching is case-sensitive and never folded. `settings.load_profile` raises on an
 *    unregistered name; this resolver cannot raise inside a vitest setup file without
 *    taking the run down for a typo, so it falls back instead - but it falls back to the
 *    *cheapest* budget. Folding `"CI"` to `ci` would silently grant a 500-example budget
 *    for a name Python would have rejected, which is the wrong direction to be wrong in.
 *
 * What would falsify these properties
 * -----------------------------------
 *
 * * Making the resolver throw on an unknown name: the totality property fails.
 * * Case-folding the lookup: the `"CI"` case in the exact-matching property fails.
 * * Changing the fallback to `default`: the unset/unknown property fails, and a laptop
 *   silently runs 50x the intended examples.
 * * Dropping the `configureGlobal` call from `setup.ts`: the readback property fails.
 * * Dropping the `beforeEach` stamp from `setup.ts`, or renaming the meta key on one side
 *   only: the run-record property fails. That is the clause that makes R3.9 falsifiable
 *   rather than merely implemented - without it the attestation is written by one file and
 *   read by nobody, which is indistinguishable from not being written at all.
 * * Making `appliedNumRuns` absent instead of `null` when the readback yields nothing: the
 *   attestation property fails on `Object.hasOwn`. An absent field cannot be told apart
 *   from a reader looking in the wrong place; a `null` can (I-7).
 *
 * No `numRuns` appears anywhere in this file, and that is not incidental - the subject
 * under test IS the global, so it is read as a pure function and as a readback. A per-call
 * value would override the very thing being measured, and the inventory gate
 * (`tests/verify/test_property_inventory_consistency.py`) now fails on any.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  activeBudget,
  budgetAttestation,
  FALLBACK_PROFILE,
  FAST_CHECK_IMPLICIT_NUM_RUNS,
  FC_BUDGET_META_KEY,
  type FcBudgetAttestation,
  PROFILE_NUM_RUNS,
  resolveBudget,
  resolveNumRuns,
} from "@test/fc-budget";

/** The profile names the resolver recognises, read from the table rather than restated. */
const REGISTERED = Object.keys(PROFILE_NUM_RUNS);

/** The run count for the fallback profile, via the same lookup the resolver uses. */
const FALLBACK_NUM_RUNS = PROFILE_NUM_RUNS[FALLBACK_PROFILE] ?? -1;

/**
 * Names that must NOT resolve: case variants of real profiles, near-misses, and padding.
 * Case variants are the interesting ones - they are the plausible typo that would be
 * dangerous to accept, because folding them upward grants a heavier budget.
 */
const UNRECOGNISED = [
  "",
  " ",
  "CI",
  "Ci",
  "DEV",
  "Dev",
  "HEAVY",
  "Nightly",
  "DEFAULT",
  " ci",
  "ci ",
  "ci\t",
  "dev2",
  "heavyweight",
  "prod",
  "profile",
];

/**
 * A vitest task, narrowed to the two fields the run-record assertion reads.
 *
 * Declared locally rather than imported because `TaskMeta` is an EMPTY interface: an
 * interface gets no implicit index signature, so `task.meta[someStringKey]` is an implicit
 * `any` under `noImplicitAny` and `Task[]` is not assignable to anything keyed by string.
 * That is the same reason `setup.ts` writes the stamp with `Object.assign` rather than a
 * property assignment. One cast at the boundary, commented, in place of an `any` per read.
 */
interface MetaBearingTask {
  readonly name: string;
  readonly meta: Readonly<Record<string, unknown>>;
  readonly tasks?: ReadonlyArray<MetaBearingTask>;
}

/** Every task in the tree, depth-first: suites and tests alike. */
function flattenTasks(tasks: ReadonlyArray<MetaBearingTask>): MetaBearingTask[] {
  return tasks.flatMap((task) => [task, ...flattenTasks(task.tasks ?? [])]);
}

describe("fast-check budget resolution", () => {
  // Feature: decision-quality-proof, Property 42: The fast-check budget is a total function of the profile name
  it("resolves any input at all to a positive budget, and never throws", () => {
    fc.assert(
      fc.property(fc.oneof(fc.string(), fc.constant(""), fc.fullUnicodeString()), (name) => {
        const resolution = resolveBudget(name);

        expect(Number.isInteger(resolution.numRuns)).toBe(true);
        expect(resolution.numRuns).toBeGreaterThan(0);
        // Totality means the resolved profile is always one the table knows, so a
        // downstream reader can always look the count back up.
        expect(REGISTERED).toContain(resolution.profile);
        expect(PROFILE_NUM_RUNS[resolution.profile]).toBe(resolution.numRuns);
        // The convenience wrapper cannot disagree with the full resolution.
        expect(resolveNumRuns(name)).toBe(resolution.numRuns);
      }),
    );
  });

  // Feature: decision-quality-proof, Property 42: The fast-check budget is a total function of the profile name
  it("carries the requested name through verbatim, whatever it was", () => {
    fc.assert(
      fc.property(fc.string(), (name) => {
        // The reported `requested` is evidence, not a normalised echo: R3.9 wants a
        // failure to be able to say what was asked for as well as what was used.
        expect(resolveBudget(name).requested).toBe(name);
      }),
    );
  });

  // Feature: decision-quality-proof, Property 42: The fast-check budget is a total function of the profile name
  it("recognises a name exactly when the table holds it, and never case-folds", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.constantFrom(...REGISTERED), fc.constantFrom(...UNRECOGNISED), fc.string()),
        (name) => {
          const resolution = resolveBudget(name);
          const known = Object.hasOwn(PROFILE_NUM_RUNS, name);

          expect(resolution.recognised).toBe(known);
          if (known) {
            expect(resolution.profile).toBe(name);
            expect(resolution.numRuns).toBe(PROFILE_NUM_RUNS[name]);
          } else {
            // R3.2: an unknown name resolves to the CHEAPEST budget, not the default one.
            expect(resolution.profile).toBe(FALLBACK_PROFILE);
            expect(resolution.numRuns).toBe(FALLBACK_NUM_RUNS);
          }
        },
      ),
    );
  });

  it("mirrors the five Hypothesis profiles the Python side registers", () => {
    // Not generated: a committed table compared against the values `conftest.py`
    // registers. Stated here so a drift between the two sides is a test failure rather
    // than a discrepancy someone notices later. The Python values are quoted from
    // `conftest.py`'s `settings.register_profile` calls.
    expect(PROFILE_NUM_RUNS).toEqual({
      dev: 10,
      heavy: 100,
      default: 500,
      ci: 500,
      nightly: 5000,
    });
    // R3.5's floor, over the whole table rather than three names by hand: EVERY profile CI
    // could select runs at least 100 examples, and the ONE below the floor is exactly the
    // local fallback. Stated as a partition so a sixth profile added below 100 fails here
    // instead of quietly becoming selectable by CI.
    for (const [name, count] of Object.entries(PROFILE_NUM_RUNS)) {
      if (name === FALLBACK_PROFILE) {
        expect(count).toBeLessThan(100);
      } else {
        expect(count).toBeGreaterThanOrEqual(100);
      }
    }
  });

  it("treats an absent variable the same as an unknown one", () => {
    for (const absent of [undefined, null]) {
      const resolution = resolveBudget(absent);
      expect(resolution.requested).toBeNull();
      expect(resolution.recognised).toBe(false);
      expect(resolution.profile).toBe(FALLBACK_PROFILE);
      expect(resolution.numRuns).toBe(FALLBACK_NUM_RUNS);
    }
  });

  it("freezes the table, so no importer can retune another suite's budget", () => {
    expect(Object.isFrozen(PROFILE_NUM_RUNS)).toBe(true);
  });

  // Feature: decision-quality-proof, Property 42: The fast-check budget is a total function of the profile name
  it("builds an attestation carrying BOTH counts, with the applied one null and never absent", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.constantFrom(...REGISTERED), fc.constantFrom(...UNRECOGNISED), fc.string()),
        fc.oneof(fc.integer({ min: 1, max: 10_000 }), fc.constant(undefined)),
        (name, applied) => {
          const resolution = resolveBudget(name);
          const attestation = budgetAttestation(resolution, applied);

          // Every field of the resolution survives into the record: R3.9 wants the record
          // to state what was asked for AND what was used, not just the count.
          expect(attestation.profile).toBe(resolution.profile);
          expect(attestation.requested).toBe(resolution.requested);
          expect(attestation.recognised).toBe(resolution.recognised);
          expect(attestation.numRuns).toBe(resolution.numRuns);
          expect(attestation.fastCheckImplicitDefault).toBe(FAST_CHECK_IMPLICIT_NUM_RUNS);

          // THE TWO-COUNT CLAUSE. `numRuns` is what the profile resolved to and
          // `appliedNumRuns` is what fast-check reported back, so a silently failed global
          // is distinguishable from an applied one WITHOUT the reader re-deriving either.
          // A single count could not tell those apart.
          expect(Object.hasOwn(attestation, "appliedNumRuns")).toBe(true);
          expect(attestation.appliedNumRuns).toBe(applied ?? null);
          expect(attestation.appliedNumRuns === null).toBe(applied === undefined);
        },
      ),
    );
  });

  it("resolves the local fallback to a DIFFERENT count than fast-check's implicit default", () => {
    // This is WHY the readback below matters, and it is asserted rather than asserted-in-
    // prose. If the two numbers were equal, an unconfigured run would be indistinguishable
    // from a configured one by count alone and R3.9's obligation would be unfalsifiable.
    // They differ by 10x: fast-check falls back to 100, the local profile is 10.
    expect(FAST_CHECK_IMPLICIT_NUM_RUNS).not.toBe(FALLBACK_NUM_RUNS);
    expect(FAST_CHECK_IMPLICIT_NUM_RUNS).toBeGreaterThan(FALLBACK_NUM_RUNS);
  });

  it("applied the resolved budget to the fast-check global, and says which (R3.9)", () => {
    // THE READBACK. `setup.ts` resolves the active profile and calls
    // `fc.configureGlobal`; this asserts the call took effect, which is the only way to
    // tell an applied global from a silently failed one. A failure here means every
    // property in the console ran at fast-check's implicit default instead of the
    // declared budget - green, and measuring something nobody asked for.
    const expected = activeBudget();
    const applied = fc.readConfigureGlobal().numRuns;

    expect(applied).toBe(expected.numRuns);
    expect(applied).not.toBeUndefined();
    // The readback is not merely "some number": it is the one the profile resolved to, and
    // NOT fast-check's implicit fallback, whenever those two differ.
    expect(PROFILE_NUM_RUNS[expected.profile]).toBe(applied);
  });

  it("stamps that budget into the run record for this file, exactly once (R3.9)", (context) => {
    // THE RUN-RECORD CLAUSE, and the one that makes R3.9 falsifiable rather than merely
    // implemented. The readback above proves the global took INSIDE this process; it does
    // not put the number anywhere a Python gate can read. `vitest.config.ts:34-35` writes
    // `artifacts/test-reports/vitest.json`, and on a PASSING test `meta` is the only field
    // a setup file can populate - `failureMessages` is empty by definition and a static
    // title carries no number. So `setup.ts`'s `beforeEach` stamps the attestation into
    // `task.meta` under `FC_BUDGET_META_KEY`, and this asserts it arrived, under that key,
    // with the value the resolver and the readback jointly imply.
    //
    // Reading the whole file's task tree rather than only `context.task.meta` is
    // deliberate: the stamp lands on whichever test in the file runs FIRST, a stamped task
    // keeps its `meta` after running, and this way the assertion does not silently become
    // vacuous if a test is later inserted above it.
    //
    // ONE stamp per file is the committed expectation, and it depends on vitest's default
    // `isolate: true` (which `vitest.config.ts` does not override) re-executing the setup
    // module per file. If isolation is ever disabled, four of the five declared files would
    // carry NO attestation and R3.9's per-file reporting would genuinely degrade - so a red
    // here is a signal to restore per-file reporting, never to relax this count.
    const applied = fc.readConfigureGlobal().numRuns;
    const expectedAttestation: FcBudgetAttestation = budgetAttestation(activeBudget(), applied);

    // One cast at the boundary: `Task`'s `meta` is the empty `TaskMeta` interface, which
    // has no implicit index signature, so `Task[]` is not assignable to anything read by
    // string key. See `MetaBearingTask` above.
    const fileTasks = context.task.file.tasks as unknown as ReadonlyArray<MetaBearingTask>;
    const carriers = flattenTasks(fileTasks).filter((task) =>
      Object.hasOwn(task.meta, FC_BUDGET_META_KEY),
    );

    // Named, so a count failure says WHICH tests carried a stamp rather than only how many.
    expect(carriers.map((task) => task.name)).toHaveLength(1);
    expect(carriers.map((task) => task.meta[FC_BUDGET_META_KEY])).toEqual([expectedAttestation]);
  });
});
