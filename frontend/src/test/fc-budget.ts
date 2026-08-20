/**
 * The fast-check analogue of the root `conftest.py` Hypothesis profiles (R3.1, R3.2,
 * R3.5, R3.9; AD-13's inheritance rule).
 *
 * Why this module exists
 * ----------------------
 *
 * The Python side inherits `max_examples` from a named profile, so a local run is cheap
 * (I-0) and a CI run satisfies the >=100-iteration obligation, and neither is achieved by
 * a literal written into a test file. The TypeScript side had no such mechanism: every
 * fast-check property stated `{ numRuns: 100 }` in place, which overrides any global and
 * pins the local cost to the CI cost. This resolver is the missing profile mechanism, and
 * `../test/setup.ts` is the single place it is applied.
 *
 * Why the resolver is a separate module from the setup file
 * --------------------------------------------------------
 *
 * `setup.ts` has top-level side effects (MSW lifecycle hooks, `expect.extend`, global
 * stubs). A property test that imported it to read the resolver would re-register all of
 * them. So the resolution is a pure function here, the *application* of it is in
 * `setup.ts`, and the property test reads this module. Deviation from task 1.2's literal
 * "File: frontend/src/test/setup.ts" is deliberate and is what makes task 1.5's property
 * ("the budget is a total function of the profile name") expressible at all.
 *
 * The deliberate asymmetry with the Python side (R3.2)
 * ---------------------------------------------------
 *
 * Python resolves an unset `HYPOTHESIS_PROFILE` to `default` (500). This resolves it to
 * `dev` (10). That is not an inconsistency: an unset variable is the *local* case, and
 * under I-0 the local case must be the cheap one. CI sets the variable explicitly.
 *
 * Matching is exact, never case-folded or fuzzy
 * --------------------------------------------
 *
 * `settings.load_profile` raises on an unregistered name. This resolver cannot raise
 * inside a vitest setup file without taking the whole run down for a typo, so it falls
 * back instead — but it falls back to the *cheapest* budget and records that the name was
 * not recognised. Case-folding `"CI"` to `ci` would silently grant a 500-example budget
 * for a name Python would have rejected, so it is not done.
 */

/**
 * Profile name -> run count. Mirrors the five profiles `conftest.py` registers
 * (`dev`=10, `heavy`=100, `default`=500, `ci`=500, `nightly`=5000). Written once here and
 * read everywhere else, so the two sides cannot drift silently.
 */
export const PROFILE_NUM_RUNS: Readonly<Record<string, number>> = Object.freeze({
  dev: 10,
  heavy: 100,
  default: 500,
  ci: 500,
  nightly: 5000,
});

/** Resolution target for an unset or unrecognised profile name. See R3.2 above. */
export const FALLBACK_PROFILE = "dev";

/**
 * fast-check's own default when no global is configured. Recorded so the failure mode
 * R3.9 is about is nameable: 100 looks CI-legal while costing a laptop ten times the
 * intended `dev` budget, which is exactly why a silently-failed global must not pass for
 * an applied one.
 *
 * R3.9 records this value as "reportedly 100 - **not** confirmed against the installed
 * library". It is now confirmed: `fast-check@3.23.2` (the version resolved under a
 * `^3.22.0` declaration) sets `const defaultValue = 100` in
 * `QualifiedParameters.readNumRuns`, which is the sole resolution path for `numRuns` when
 * neither a per-call value nor a global is present. So the 10x-over-budget failure mode is
 * a measured property of the installed library, not an assumption.
 */
export const FAST_CHECK_IMPLICIT_NUM_RUNS = 100;

/** The outcome of resolving a profile name. Every field is reportable (R3.9). */
export interface BudgetResolution {
  /** The raw value read from the environment, unmodified. `null` when unset. */
  readonly requested: string | null;
  /** The profile actually used: `requested` when known, otherwise `FALLBACK_PROFILE`. */
  readonly profile: string;
  /** The run count for `profile`. */
  readonly numRuns: number;
  /** False when `requested` named no registered profile (including when unset). */
  readonly recognised: boolean;
}

/**
 * Resolve a profile name to a run budget. Total: every input, including `undefined`, the
 * empty string and any unregistered name, yields a `BudgetResolution`. Never throws.
 */
export function resolveBudget(requested: string | undefined | null): BudgetResolution {
  const raw = requested ?? null;
  const known = raw === null ? undefined : PROFILE_NUM_RUNS[raw];
  if (known === undefined) {
    const fallback = PROFILE_NUM_RUNS[FALLBACK_PROFILE];
    // `FALLBACK_PROFILE` is a key of the frozen table above, so this branch is
    // unreachable; it exists because `noUncheckedIndexedAccess` makes the lookup
    // `number | undefined` and an unchecked `!` would be an assertion, not a check.
    if (fallback === undefined) {
      throw new Error(
        `fc budget table is missing its fallback profile '${FALLBACK_PROFILE}'`,
      );
    }
    return { requested: raw, profile: FALLBACK_PROFILE, numRuns: fallback, recognised: false };
  }
  return { requested: raw, profile: raw as string, numRuns: known, recognised: true };
}

/** `resolveBudget(...).numRuns`, for callers that need only the count. */
export function resolveNumRuns(requested: string | undefined | null): number {
  return resolveBudget(requested).numRuns;
}

/**
 * The key under which the attestation below is stamped into a vitest task's `meta`.
 *
 * Written once here and imported by every reader, so the run-record contract is a symbol
 * rather than a string repeated in a setup file, a property test and a Python gate.
 */
export const FC_BUDGET_META_KEY = "fcBudget";

/**
 * What the run record carries about the budget that was actually in force (R3.9).
 *
 * Both counts are present deliberately. `numRuns` is what the profile resolved to and
 * `appliedNumRuns` is what fast-check reports back, so a reader can tell an applied global
 * from a silently failed one without re-deriving either. `appliedNumRuns` is `null`, never
 * absent, when the readback produced nothing: an absent field is indistinguishable from a
 * reader looking in the wrong place, and a `null` is not (I-7).
 */
export interface FcBudgetAttestation {
  readonly profile: string;
  readonly requested: string | null;
  readonly recognised: boolean;
  readonly numRuns: number;
  readonly appliedNumRuns: number | null;
  readonly fastCheckImplicitDefault: number;
}

/** Build the attestation. Pure, total, and never throws. */
export function budgetAttestation(
  resolution: BudgetResolution,
  applied: number | undefined,
): FcBudgetAttestation {
  return {
    profile: resolution.profile,
    requested: resolution.requested,
    recognised: resolution.recognised,
    numRuns: resolution.numRuns,
    appliedNumRuns: applied ?? null,
    fastCheckImplicitDefault: FAST_CHECK_IMPLICIT_NUM_RUNS,
  };
}

/**
 * The resolution in force for this process, from `HYPOTHESIS_PROFILE`.
 *
 * Read through `globalThis.process` rather than a bare `process` so the module stays
 * importable in a browser-ish environment where `process` is absent — the resolver is a
 * total function and losing the environment must degrade to `dev`, not to a crash.
 */
export function activeBudget(): BudgetResolution {
  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env;
  return resolveBudget(env?.["HYPOTHESIS_PROFILE"]);
}
