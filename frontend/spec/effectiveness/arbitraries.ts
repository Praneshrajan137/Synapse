/**
 * Feature: purpose-achievement-audit, task 1.2 — shared fast-check arbitraries for
 * the E6 console-effectiveness properties.
 *
 * Imported by the effectiveness property tests (design Property 32 "the scorecard is
 * complete or the job fails", Property 33 "the ratchet is sensitive to any
 * degradation", Property 34 "interruption precision responds to its inputs", Property
 * 36 "a baseline is a measurement, not a ceiling") so the input space is constrained
 * once, here, instead of per spec file.
 *
 * Three generators, matching the three shapes the tasks need:
 *
 *   • **scorecard rows** — `scorecardRowArb` / `scorecardRowsArb` /
 *     `capturedScorecardRowArb`, plus `baselineCaseArb` for the Property 36
 *     rejection modes (missing capture stamp, absent proxy ceiling, every row
 *     carrying an identical `steps`/`latencyMs` — the authored-ceiling tell).
 *   • **job sets** — `jobSetArb` / `jobCoverageArb`: subsets of the five declared
 *     Jobs-To-Be-Done, including the omission and duplication cases that must make
 *     the effectiveness job FAIL rather than emit a shorter scorecard (R8.1–R8.3).
 *   • **interruption sets** — `interruptionsArb` / `interruptionSetArb`, including
 *     the empty set whose precision is honestly `null` rather than zero.
 *
 * `JobToBeDone`, `JOB_ORDER`, `ScorecardRow` and `Interruption` are imported from the
 * shipped `@lib/` modules rather than redeclared: the enumerated job list has exactly
 * one source of truth (`@lib/effectiveness-scorecard`), so an arbitrary here can never
 * drift from the set the emitter and the ratchet agree on.
 *
 * No arbitrary in this module sets a run count, and neither should its importers. The
 * budget is inherited from the `HYPOTHESIS_PROFILE` profile through `fc.configureGlobal`
 * in `frontend/src/test/setup.ts` (see `frontend/src/test/fc-budget.ts` for the table) —
 * the genuine analogue of the Python side inheriting `max_examples` from the root
 * `conftest.py` profiles, rather than the earlier convention of stating `>= 100` in place.
 *
 * A per-call `{ numRuns }` silently overrides the global, so the five property files
 * declared in `tests/verify/test_property_inventory_consistency.py` carry none and the
 * inventory gate now fails on any. Specs outside that inventory may still state one; that
 * is other features' debt, scoped deliberately rather than fixed by a sweep (R3.4).
 */

import { JOB_ORDER, type JobToBeDone, type ScorecardRow } from "@lib/effectiveness-scorecard";
import type { Interruption } from "@lib/interruption-precision";
import fc from "fast-check";

// ---------------------------------------------------------------------------
// Job sets (Property 32)
// ---------------------------------------------------------------------------

/** One declared Job_To_Be_Done. */
export const jobArb: fc.Arbitrary<JobToBeDone> = fc.constantFrom<JobToBeDone>(...JOB_ORDER);

/**
 * A set of distinct declared jobs, in `JOB_ORDER`. Empty by default so the
 * "a declared job emitted no row" case is reachable; pass `minLength: JOB_ORDER.length`
 * for the complete-coverage case.
 */
export function jobSetArb(
  opts: { readonly minLength?: number; readonly maxLength?: number } = {},
): fc.Arbitrary<readonly JobToBeDone[]> {
  const minLength = opts.minLength ?? 0;
  const maxLength = opts.maxLength ?? JOB_ORDER.length;
  return fc
    .uniqueArray(jobArb, { minLength, maxLength })
    .map((jobs) => [...jobs].sort((a, b) => JOB_ORDER.indexOf(a) - JOB_ORDER.indexOf(b)));
}

/** How a generated harness run covers the declared job set. */
export type JobCoverageKind = "complete" | "missing" | "duplicated" | "empty";

/**
 * A run's emitted job list together with the coverage mode that produced it, so a
 * property can assert "complete ⇒ scorecard emitted, anything else ⇒ failed result"
 * without re-deriving the mode from the list.
 *
 * `emitted` may contain repeats (the `duplicated` mode): a bijection between rows and
 * declared jobs is exactly what R8.2 requires, so a repeat must be as visible to the
 * generator as an omission.
 */
export interface JobCoverage {
  readonly kind: JobCoverageKind;
  readonly emitted: readonly JobToBeDone[];
  readonly missing: readonly JobToBeDone[];
}

/** A job list per coverage mode: complete, one-or-more missing, duplicated, or empty. */
export const jobCoverageArb: fc.Arbitrary<JobCoverage> = fc
  .constantFrom<JobCoverageKind>("complete", "missing", "duplicated", "empty")
  .chain((kind) => {
    if (kind === "empty") {
      return fc.constant<JobCoverage>({ kind, emitted: [], missing: [...JOB_ORDER] });
    }
    if (kind === "complete") {
      return fc.constant<JobCoverage>({ kind, emitted: [...JOB_ORDER], missing: [] });
    }
    if (kind === "duplicated") {
      return jobArb.map<JobCoverage>((repeated) => ({
        kind,
        emitted: [...JOB_ORDER, repeated],
        missing: [],
      }));
    }
    return jobSetArb({ minLength: 1, maxLength: JOB_ORDER.length - 1 }).map<JobCoverage>(
      (emitted) => ({
        kind,
        emitted,
        missing: JOB_ORDER.filter((job) => !emitted.includes(job)),
      }),
    );
  });

// ---------------------------------------------------------------------------
// Scorecard rows (Properties 32, 33, 36)
// ---------------------------------------------------------------------------

/** Plausible measured step counts: a golden path is short, a bad path is not. */
const stepsArb: fc.Arbitrary<number> = fc.integer({ min: 1, max: 40 });

/** Time-to-complete in milliseconds, bounded well inside the harness timeout. */
const latencyArb: fc.Arbitrary<number> = fc.integer({ min: 1, max: 120_000 });

/** Dead-ends ÷ attempts, the scorecard's `errorRate` domain of `[0, 1]`. */
const errorRateArb: fc.Arbitrary<number> = fc
  .integer({ min: 0, max: 100 })
  .map((tenths) => tenths / 100);

/** One measured row for a given job (or a drawn one when `job` is omitted). */
export function scorecardRowArb(job?: JobToBeDone): fc.Arbitrary<ScorecardRow> {
  return fc.record<ScorecardRow>({
    job: job === undefined ? jobArb : fc.constant(job),
    steps: stepsArb,
    latencyMs: latencyArb,
    errorRate: errorRateArb,
  });
}

/**
 * One row per declared job, in `JOB_ORDER` — the shape a passing harness run emits.
 * Property 33 degrades a subset of these; Property 32 asserts the bijection.
 */
export const scorecardRowsArb: fc.Arbitrary<readonly ScorecardRow[]> = fc.tuple(
  ...JOB_ORDER.map((job) => scorecardRowArb(job)),
);

/**
 * A row carrying the per-row capture metadata E6 adds to the baseline schema
 * (`harnessVersion`, `seed`, `capturedAt`), which Property 36 requires on every row.
 * Optional fields are `null`-able rather than absent so the rejection case is
 * expressible under `exactOptionalPropertyTypes`.
 */
export interface CapturedScorecardRow extends ScorecardRow {
  readonly harnessVersion: string | null;
  readonly seed: number | null;
  readonly capturedAt: string | null;
}

const harnessVersionArb: fc.Arbitrary<string> = fc
  .tuple(fc.integer({ min: 1, max: 3 }), fc.integer({ min: 0, max: 9 }), fc.integer({ min: 0, max: 9 }))
  .map(([major, minor, patch]) => `${major}.${minor}.${patch}`);

const seedArb: fc.Arbitrary<number> = fc.integer({ min: 0, max: 0xffffffff });

const capturedAtArb: fc.Arbitrary<string> = fc
  .date({ min: new Date("2026-01-01T00:00:00.000Z"), max: new Date("2027-01-01T00:00:00.000Z") })
  .map((moment) => moment.toISOString());

/**
 * A row with capture metadata; `stamped: false` drops one of the three stamps, which
 * is the state Property 36 rejects.
 */
export function capturedScorecardRowArb(
  job?: JobToBeDone,
): fc.Arbitrary<CapturedScorecardRow> {
  return fc
    .tuple(
      scorecardRowArb(job),
      harnessVersionArb,
      seedArb,
      capturedAtArb,
      fc.constantFrom<"none" | "harnessVersion" | "seed" | "capturedAt">(
        "none",
        "harnessVersion",
        "seed",
        "capturedAt",
      ),
    )
    .map(([row, harnessVersion, seed, capturedAt, dropped]) => ({
      ...row,
      harnessVersion: dropped === "harnessVersion" ? null : harnessVersion,
      seed: dropped === "seed" ? null : seed,
      capturedAt: dropped === "capturedAt" ? null : capturedAt,
    }));
}

/** Why a generated baseline is (or is not) a measurement rather than a ceiling. */
export type BaselineDefect = "none" | "missing-stamp" | "absent-ceiling" | "uniform-metrics";

/** A committed baseline candidate plus the single defect (if any) injected into it. */
export interface BaselineCase {
  readonly defect: BaselineDefect;
  readonly rows: readonly CapturedScorecardRow[];
  readonly proxyCeiling: string | null;
}

/**
 * A baseline carrying at most one Property 36 defect.
 *
 * `uniform-metrics` is the authored-ceiling tell the audit named: every row sharing an
 * identical `steps` and an identical `latencyMs` is what a hand-written baseline looks
 * like, and it is rejected however plausible the numbers are.
 */
export const baselineCaseArb: fc.Arbitrary<BaselineCase> = fc
  .constantFrom<BaselineDefect>("none", "missing-stamp", "absent-ceiling", "uniform-metrics")
  .chain((defect) =>
    fc
      .tuple(
        fc.tuple(...JOB_ORDER.map((job) => capturedScorecardRowArb(job))),
        harnessVersionArb,
        seedArb,
        capturedAtArb,
        stepsArb,
        latencyArb,
        errorRateArb,
        fc.string({ minLength: 20, maxLength: 80 }),
      )
      .map(([drawn, harnessVersion, seed, capturedAt, steps, latencyMs, errorRate, ceiling]) => {
        // Start from fully stamped rows so only the named defect is present.
        const stamped: readonly CapturedScorecardRow[] = drawn.map((row) => ({
          ...row,
          harnessVersion,
          seed,
          capturedAt,
        }));
        if (defect === "missing-stamp") {
          const [head, ...tail] = stamped;
          const holed: readonly CapturedScorecardRow[] =
            head === undefined ? stamped : [{ ...head, capturedAt: null }, ...tail];
          return { defect, rows: holed, proxyCeiling: ceiling };
        }
        if (defect === "absent-ceiling") {
          return { defect, rows: stamped, proxyCeiling: null };
        }
        if (defect === "uniform-metrics") {
          return {
            defect,
            rows: stamped.map((row) => ({ ...row, steps, latencyMs, errorRate })),
            proxyCeiling: ceiling,
          };
        }
        return { defect, rows: stamped, proxyCeiling: ceiling };
      }),
  );

// ---------------------------------------------------------------------------
// Interruption sets (Property 34)
// ---------------------------------------------------------------------------

/** One interruption the console raised: warranted, or a false alarm. */
export const interruptionArb: fc.Arbitrary<Interruption> = fc.record<Interruption>({
  warranted: fc.boolean(),
});

/**
 * A set of raised interruptions. `minLength` defaults to `0` so the undefined-ratio
 * case (`total === 0` ⇒ `null`, never a fabricated `0`) is reachable; Property 34's
 * flip-any-flag clause needs `minLength: 1`.
 */
export function interruptionsArb(
  opts: { readonly minLength?: number; readonly maxLength?: number } = {},
): fc.Arbitrary<readonly Interruption[]> {
  return fc.array(interruptionArb, {
    minLength: opts.minLength ?? 0,
    maxLength: opts.maxLength ?? 32,
  });
}

/** A non-empty interruption set paired with an index into it, for the flip clause. */
export const interruptionSetArb: fc.Arbitrary<{
  readonly interruptions: readonly Interruption[];
  readonly index: number;
}> = interruptionsArb({ minLength: 1 }).chain((interruptions) =>
  fc
    .integer({ min: 0, max: interruptions.length - 1 })
    .map((index) => ({ interruptions, index })),
);
