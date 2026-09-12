/**
 * Effectiveness_Scorecard emission rule -- complete, or failed (task 11.2).
 *
 * purpose-achievement-audit R8.1, R8.2, R8.3, R8.6, R8.8; design E6 "Scorecard
 * emission requires a bijection between emitted rows and declared Jobs-To-Be-Done (5);
 * an unreachable harness or a missing job is a **failed result**, not a shorter
 * scorecard"; Property 32 "The scorecard is complete or the job fails".
 *
 * ## What this module is for
 *
 * The audit's finding was not that the scorecard was wrong. It was that a scorecard
 * with `rows: []` was emitted, accepted, compared against nothing, and reported as
 * "the REAL effectiveness signal". Every step in that chain was individually
 * defensible; the aggregate was a measurement that had never measured. So emission
 * stops being a serialization step and becomes a **verdict**: either the run produced
 * one measured, stamped row for every declared Job_To_Be_Done, or the run FAILED.
 * There is no third outcome, and in particular there is no shorter scorecard (R8.2).
 *
 * ## The rule, in one function
 *
 * {@link evaluateEmission} is pure, total, and free of every import -- no `zod`, no
 * `@lib/*` alias, no `node:` builtin. That is deliberate on three counts:
 *
 *   1. The Playwright emitter (`frontend/tests/e2e/task-completion.jtbd.spec.ts`)
 *      imports it by relative path. Every other e2e spec in this repository stays
 *      clear of the app's `@`-alias module graph by convention, and a Playwright
 *      transform that cannot resolve `@lib` would break the whole harness suite for
 *      a reason unrelated to effectiveness. A zero-import module cannot fail that way.
 *   2. The same rule then governs BOTH sides of the gate: the emitter decides
 *      complete-or-failed at emission time, and `spec/effectiveness/run-ratchet.ts`
 *      re-decides it from the emitted artifact. One rule, two independent executions.
 *   3. Property 32 (task 11.3) drives it directly, with no fixture and no disk.
 *
 * ## Why the declared job set is a PARAMETER and not a constant here
 *
 * `JOB_ORDER` in `frontend/src/lib/effectiveness-scorecard.ts` is the single source of
 * truth for the five Jobs-To-Be-Done. This module deliberately holds no copy of it:
 * the job set is injected. `spec/effectiveness/scorecard-gate.ts` injects `JOB_ORDER`
 * itself, so the gate that decides the build is bound to the authority. The Playwright
 * emitter injects its own local mirror (the convention above), and the gate's
 * independent evaluation against the real `JOB_ORDER` is what makes a drifted mirror a
 * mechanical failure rather than a silent mis-measurement.
 *
 * ## Stamp validity: what is checked here and what is not
 *
 * A row must carry a usable `harnessVersion`, `seed`, and `capturedAt` -- present,
 * non-blank, finite (R8.10's per-row provenance, needed here because R8.2 requires the
 * metrics to be "captured during the run that emitted that scorecard"). The FORMAT
 * rule -- `capturedAt` is an ISO-8601 UTC instant, not a bare date -- belongs to
 * `@lib/effectiveness-baseline` and is enforced where the baseline is checked. This
 * module does not restate that regular expression, because a second copy of a rule is
 * a second thing to drift.
 *
 * ## I-7
 *
 * Every failure below is a FAILED RESULT. Not a warning attached to a pass, not an
 * annotation, not "informational". `EmissionVerdict` has exactly two shapes and the
 * failing one carries EVERY reason found, so one run reports the whole gap.
 */

// ---------------------------------------------------------------------------
// Artifact locations
// ---------------------------------------------------------------------------

/**
 * Where an INCOMPLETE run records what it did manage to measure, relative to the
 * `frontend/` root.
 *
 * R8.2 forbids emitting "a scorecard carrying fewer rows", so a failed run must not
 * write the canonical `SCORECARD_FRESH_RELPATH`. It must also not destroy the
 * evidence of what happened. Those two obligations are reconciled by a distinct path:
 * nothing consumes this file as a scorecard, the ratchet still finds no fresh
 * scorecard and fails naming it, and a human debugging the run still has the partial
 * measurement. Under `test-results/` so it is gitignored.
 */
export const SCORECARD_INCOMPLETE_RELPATH = "test-results/effectiveness/scorecard.incomplete.json";

/**
 * Where the ratchet writes the measured baseline CANDIDATE built from a complete run,
 * relative to the `frontend/` root.
 *
 * The committed `spec/effectiveness/scorecard.baseline.json` is rejected today as an
 * authored ceiling (5 `missing-stamp` + 1 `uniform-metrics`). The ONLY honest way it
 * clears is that a real run measures the numbers and `buildBaseline` writes them: not
 * by editing a number, not by typing a `capturedAt`, not by relaxing a threshold
 * (I-7). This is the file an operator commits over the current baseline.
 */
export const SCORECARD_BASELINE_CANDIDATE_RELPATH =
  "test-results/effectiveness/scorecard.baseline.candidate.json";

/**
 * The Playwright JSON run record for the harness suite, relative to the `frontend/`
 * root -- the same path `playwright.harness.config.ts` writes and
 * `frontend/spec/check_fe_invariants.py` reads for the FE-INV-056 attestation. The
 * ratchet reads it to answer a question the scorecard structurally cannot: whether any
 * resilience scenario was SKIPPED (R8.6). Those scenarios live in sibling spec files,
 * so the emitter's own ledger never sees them.
 */
export const HARNESS_RUN_RECORD_RELPATH = "artifacts/test-reports/playwright-harness.json";

// ---------------------------------------------------------------------------
// Scenario ledger
// ---------------------------------------------------------------------------

/**
 * What kind of thing a scenario is. R8.6 enumerates exactly these three: "IF a
 * Job_To_Be_Done, a resilience scenario, or a real-stack fidelity comparison is
 * skipped, THEN THE effectiveness job SHALL record that skip as a divergence".
 */
export type ScenarioKind = "job" | "resilience" | "fidelity";

/**
 * The observed outcome of one scenario. Exactly two values, so `executed` and
 * `skipped` PARTITION the scenario set (Property 32) -- a scenario that ran and failed
 * is `executed`, because it produced a measurement of the failure. A third "failed"
 * value would let a run be neither executed nor skipped and the partition would stop
 * being one.
 */
export type ScenarioOutcome = "executed" | "skipped";

/** One entry in a run's scenario ledger. */
export interface ScenarioRecord<J extends string = string> {
  /** Stable scenario identifier (a scenario id, or a spec file plus title). */
  readonly scenario: string;
  readonly kind: ScenarioKind;
  /** The Job_To_Be_Done for `kind: "job"`; `null` for every other kind. */
  readonly job: J | null;
  readonly outcome: ScenarioOutcome;
}

// ---------------------------------------------------------------------------
// Rows
// ---------------------------------------------------------------------------

/**
 * A row as OFFERED to the rule: the four metrics plus the three provenance stamps,
 * each of which may be absent. `null` rather than optional so an unstamped row is
 * expressible under `exactOptionalPropertyTypes` and lands as a named failure instead
 * of an opaque shape error.
 */
export interface CapturedRow<J extends string = string> {
  readonly job: J;
  /** Affordance activations to the terminal outcome. */
  readonly steps: number;
  /** Time-to-complete, milliseconds. */
  readonly latencyMs: number;
  /** Dead-ends divided by attempts, in [0, 1]. */
  readonly errorRate: number;
  readonly harnessVersion: string | null;
  readonly seed: number | null;
  readonly capturedAt: string | null;
}

/**
 * A row the rule ACCEPTED: stamped, so it can name the run that captured it.
 * Structurally a `BaselineRow` from `@lib/effectiveness-baseline`, which is what lets
 * `buildBaseline` consume a complete run's rows without a cast.
 */
export interface MeasuredRow<J extends string = string> extends CapturedRow<J> {
  readonly harnessVersion: string;
  readonly seed: number;
  readonly capturedAt: string;
}

// ---------------------------------------------------------------------------
// Verdict
// ---------------------------------------------------------------------------

/**
 * Why a run's emission failed. Each of Property 32's four named conditions appears
 * here, plus the bijection violations R8.1 implies and the two integrity checks the
 * gate needs when it re-reads an emitted document:
 *
 *   * `harness-unreachable`  -- Property 32 condition 1 (R8.1, R8.2).
 *   * `missing-job`          -- Property 32 condition 2 (R8.2, R8.3).
 *   * `zero-executed`        -- Property 32 condition 3 (R8.8).
 *   * `skipped-scenario`     -- Property 32 condition 4 (R8.6).
 *   * `duplicate-job` / `undeclared-job` -- the other two ways a row set fails to be a
 *     bijection with the declared job set (R8.1 "exactly one row per declared job").
 *   * `unstamped-row`        -- a row that cannot name the run that captured it, so its
 *     metrics are not shown to have been "captured during the run that emitted that
 *     scorecard" (R8.2, R8.10).
 *   * `count-mismatch`       -- a document whose reported executed/skipped counts do not
 *     match its own ledger. Reported counts are re-derived, never trusted.
 *   * `no-declared-jobs`     -- the bijection is vacuous with an empty job set, and an
 *     unevaluable rule is not a passing one (I-7).
 *   * `malformed-record`     -- the artifact is not an emitted scorecard at all.
 */
export type EmissionFailureKind =
  | "harness-unreachable"
  | "missing-job"
  | "duplicate-job"
  | "undeclared-job"
  | "unstamped-row"
  | "zero-executed"
  | "skipped-scenario"
  | "count-mismatch"
  | "no-declared-jobs"
  | "malformed-record";

/** One named reason a run did not produce a complete scorecard. */
export interface EmissionFailure {
  readonly kind: EmissionFailureKind;
  /** The job, scenario, or `"run"` the failure is attributable to. */
  readonly subject: string;
  /** Human-readable detail naming what was observed. */
  readonly detail: string;
}

/** The executed/skipped partition of a run's scenario set (R8.8). */
export interface EmissionCounts {
  readonly executed: number;
  readonly skipped: number;
  /** `executed + skipped` by construction -- the partition, stated. */
  readonly total: number;
}

/**
 * The outcome of applying the emission rule. Two shapes only: a complete scorecard, or
 * a failed result naming every reason. There is no partial success.
 */
export type EmissionVerdict<J extends string = string> =
  | {
      readonly outcome: "complete";
      /** One stamped row per declared job, in declared order. */
      readonly rows: readonly MeasuredRow<J>[];
      readonly counts: EmissionCounts;
    }
  | {
      readonly outcome: "failed";
      readonly failures: readonly EmissionFailure[];
      /** Reported even on failure: the counts are the evidence for `zero-executed`. */
      readonly counts: EmissionCounts;
    };

/** Everything the rule needs to reach a verdict. */
export interface EmissionInput<J extends string = string> {
  /**
   * The declared Jobs-To-Be-Done, in canonical order. Injected, never held here -- see
   * the module header on why the job set has exactly one source of truth.
   */
  readonly declaredJobs: readonly J[];
  /** Whether the Effectiveness_Harness was observed in the browser context (R8.1). */
  readonly harnessReachable: boolean;
  /** Every row the run offered, in any order, possibly incomplete or repeated. */
  readonly rows: readonly CapturedRow<J>[];
  /** The run's scenario ledger. */
  readonly scenarios: readonly ScenarioRecord<J>[];
  /**
   * The counts an already-emitted document CLAIMS. Omitted at emission time (the rule
   * derives them); supplied when the gate re-reads a document, so a doctored count is
   * a named failure rather than an accepted number.
   */
  readonly reportedCounts?: EmissionCounts | null;
}

// ---------------------------------------------------------------------------
// Stamp predicates (presence and usability only -- see the module header)
// ---------------------------------------------------------------------------

/** Present, a string, and not whitespace-only. The trim TESTS; it never transforms. */
function isNonBlank(value: string | null): value is string {
  return value !== null && value.trim().length > 0;
}

/** Present and finite -- a seed that cannot be replayed is not a seed. */
function isReplayableSeed(value: number | null): value is number {
  return value !== null && Number.isFinite(value);
}

/** The stamps this row cannot supply, named for the failure detail. */
function missingStamps(row: CapturedRow): readonly string[] {
  const problems: string[] = [];
  if (!isNonBlank(row.harnessVersion)) problems.push("harnessVersion");
  if (!isReplayableSeed(row.seed)) problems.push("seed");
  if (!isNonBlank(row.capturedAt)) problems.push("capturedAt");
  return problems;
}

// ---------------------------------------------------------------------------
// The rule
// ---------------------------------------------------------------------------

function countBy<J extends string>(
  scenarios: readonly ScenarioRecord<J>[],
  outcome: ScenarioOutcome,
): number {
  return scenarios.filter((scenario) => scenario.outcome === outcome).length;
}

/**
 * Applies the emission rule to one run.
 *
 * Total: every input reaches a verdict, and the failing verdict carries EVERY
 * applicable reason so a single run reports the whole gap rather than the first hole.
 * Pure: no I/O, no clock, no randomness, no import.
 *
 * The verdict is `complete` iff ALL of the following hold, and `failed` naming each
 * violation otherwise:
 *
 *   * the declared job set is non-empty;
 *   * the harness was reachable;
 *   * the offered rows are a bijection with the declared job set -- one row per job,
 *     no job missing, no job repeated, no row for an undeclared job;
 *   * every accepted row carries a usable `harnessVersion`, `seed`, and `capturedAt`;
 *   * the ledger holds exactly one `kind: "job"` entry per declared job;
 *   * at least one scenario executed;
 *   * no scenario was skipped;
 *   * any reported counts match the ledger.
 */
export function evaluateEmission<J extends string>(input: EmissionInput<J>): EmissionVerdict<J> {
  const failures: EmissionFailure[] = [];
  const counts: EmissionCounts = {
    executed: countBy(input.scenarios, "executed"),
    skipped: countBy(input.scenarios, "skipped"),
    total: input.scenarios.length,
  };

  // -- The job set must exist before a bijection with it can mean anything (I-7).
  if (input.declaredJobs.length === 0) {
    failures.push({
      kind: "no-declared-jobs",
      subject: "run",
      detail:
        "no Job_To_Be_Done was declared, so the row-to-job bijection is vacuous; an " +
        "unevaluable completeness rule is not a satisfied one",
    });
  }

  // -- Property 32 condition 1: the harness must have been reachable (R8.1, R8.2).
  if (!input.harnessReachable) {
    failures.push({
      kind: "harness-unreachable",
      subject: "run",
      detail:
        "window.__atlasHarness was never observed in the browser context; an unmeasured " +
        "run is a failed run, never a scorecard with fewer rows",
    });
  }

  // -- Bijection, direction 1: no row may name a job nobody declared.
  const declaredJobSet = new Set<string>(input.declaredJobs);
  const reportedUndeclared = new Set<string>();
  for (const row of input.rows) {
    if (!declaredJobSet.has(row.job) && !reportedUndeclared.has(row.job)) {
      reportedUndeclared.add(row.job);
      failures.push({
        kind: "undeclared-job",
        subject: row.job,
        detail:
          `a row names "${row.job}", which is not a declared Job_To_Be_Done; the emitted ` +
          "row set must be a bijection with the declared job set, not a superset of it",
      });
    }
  }

  // -- Bijection, direction 2 + per-row provenance + the ledger's job coverage.
  const rowsByJob = new Map<string, CapturedRow<J>[]>();
  for (const row of input.rows) {
    const existing = rowsByJob.get(row.job);
    if (existing === undefined) rowsByJob.set(row.job, [row]);
    else existing.push(row);
  }

  const ledgerByJob = new Map<string, ScenarioRecord<J>[]>();
  for (const scenario of input.scenarios) {
    if (scenario.kind !== "job" || scenario.job === null) continue;
    const existing = ledgerByJob.get(scenario.job);
    if (existing === undefined) ledgerByJob.set(scenario.job, [scenario]);
    else existing.push(scenario);
  }

  const measured: MeasuredRow<J>[] = [];
  for (const job of input.declaredJobs) {
    const ledgerEntries = ledgerByJob.get(job) ?? [];
    if (ledgerEntries.length === 0) {
      failures.push({
        kind: "missing-job",
        subject: job,
        detail:
          "the run's scenario ledger holds no entry for this declared job, so the run " +
          "cannot say whether it executed or was skipped",
      });
    } else if (ledgerEntries.length > 1) {
      failures.push({
        kind: "duplicate-job",
        subject: job,
        detail: `the scenario ledger holds ${ledgerEntries.length} entries for this declared job`,
      });
    }

    const rows = rowsByJob.get(job) ?? [];
    if (rows.length === 0) {
      // Property 32 condition 2 (R8.2, R8.3): named, never skipped over.
      failures.push({
        kind: "missing-job",
        subject: job,
        detail:
          "this declared Job_To_Be_Done emitted no measured row; the effectiveness job " +
          "fails rather than emit a scorecard carrying fewer rows",
      });
      continue;
    }
    if (rows.length > 1) {
      failures.push({
        kind: "duplicate-job",
        subject: job,
        detail: `${rows.length} rows were emitted for this declared job; exactly one is required`,
      });
      continue;
    }

    const row = rows[0];
    if (row === undefined) continue; // Unreachable given length === 1; keeps the walk total.
    const holes = missingStamps(row);
    const { harnessVersion, seed, capturedAt } = row;
    if (
      holes.length > 0 ||
      !isNonBlank(harnessVersion) ||
      !isReplayableSeed(seed) ||
      !isNonBlank(capturedAt)
    ) {
      failures.push({
        kind: "unstamped-row",
        subject: job,
        detail:
          `row lacks a usable ${holes.join(", ")}; a row that cannot name the run that ` +
          "captured it does not show its metrics were measured during that run",
      });
      continue;
    }
    measured.push({
      job: row.job,
      steps: row.steps,
      latencyMs: row.latencyMs,
      errorRate: row.errorRate,
      harnessVersion,
      seed,
      capturedAt,
    });
  }

  // -- Property 32 condition 3 (R8.8): an all-skipped run is a failed run.
  if (counts.executed === 0) {
    failures.push({
      kind: "zero-executed",
      subject: "run",
      detail:
        `${counts.total} scenario(s) recorded, 0 executed and ${counts.skipped} skipped; ` +
        "a run that executed nothing has measured nothing",
    });
  }

  // -- Property 32 condition 4 (R8.6): a skip is a divergence, never informational.
  for (const scenario of input.scenarios) {
    if (scenario.outcome !== "skipped") continue;
    failures.push({
      kind: "skipped-scenario",
      subject: scenario.scenario,
      detail:
        `this ${scenario.kind} scenario was skipped; a skip is recorded as a divergence ` +
        "and is neither informational nor a pass",
    });
  }

  // -- Reported counts are re-derived, never trusted.
  const reported = input.reportedCounts ?? null;
  if (
    reported !== null &&
    (reported.executed !== counts.executed ||
      reported.skipped !== counts.skipped ||
      reported.total !== counts.total)
  ) {
    failures.push({
      kind: "count-mismatch",
      subject: "run",
      detail:
        `the record reports executed=${reported.executed}, skipped=${reported.skipped}, ` +
        `total=${reported.total}, but its own ledger yields executed=${counts.executed}, ` +
        `skipped=${counts.skipped}, total=${counts.total}`,
    });
  }

  if (failures.length === 0) {
    return { outcome: "complete", rows: measured, counts };
  }
  return { outcome: "failed", failures, counts };
}

/** One ASCII line describing a failure, for a console report. */
export function describeEmissionFailure(failure: EmissionFailure): string {
  return `[${failure.kind}] ${failure.subject}: ${failure.detail}`;
}

// ---------------------------------------------------------------------------
// Declared deferrals
// ---------------------------------------------------------------------------

/**
 * A scenario that is DECLARED to be outside the harness suite, with its blockers and
 * their owner named.
 *
 * This exists so an absence is not invisible. It is not an exemption: a deferral is
 * printed by the ratchet on every run as an outstanding divergence, and it clears only
 * when its blockers are gone and the spec joins `HARNESS_SPEC_PATTERN`.
 */
export interface DeferredScenario {
  /** The spec file, relative to `frontend/`. */
  readonly spec: string;
  readonly kind: ScenarioKind;
  /** Why it cannot execute today. */
  readonly reason: string;
  /** Each blocker, named specifically enough to be checked off. */
  readonly blockers: readonly string[];
  /** Who owns removing the blockers. */
  readonly owner: string;
}

/**
 * The one scenario currently declared out of suite.
 *
 * `reconnect-replay.resilience.spec.ts` is deliberately excluded from
 * `HARNESS_SPEC_PATTERN` in `playwright.config.ts`, so it is ABSENT from the harness
 * suite rather than skipped inside it, and it does not participate in the run's
 * executed/skipped partition.
 *
 * Stated plainly (I-7): R8.6 reads "IF a Job_To_Be_Done, a resilience scenario, or a
 * real-stack fidelity comparison is skipped, THEN THE effectiveness job SHALL record
 * that skip as a divergence". This deferral is recorded as a divergence in the
 * ratchet's report, but it does not by itself fail the ratchet, because its three
 * blockers belong to work this task does not own. That is a real gap between the
 * criterion and the enforcement, and it is written down here rather than resolved by
 * quietly dropping the scenario from the declared set.
 */
export const DEFERRED_SCENARIOS: readonly DeferredScenario[] = [
  {
    spec: "tests/e2e/reconnect-replay.resilience.spec.ts",
    kind: "resilience",
    reason:
      "excluded from HARNESS_SPEC_PATTERN: the scenario cannot be driven or asserted yet, " +
      "so running it would report a failure about the wrong thing",
    blockers: [
      "no [data-decision-row] / [data-decision-status] identity exists anywhere in frontend/src/**",
      "driveResilience has no replay-plan driver",
      "src/lib/reconcile.ts is imported only by its own property tests (audit R13)",
    ],
    owner: "task 11.9 (surfaces) and audit R13 (module liveness)",
  },
];
