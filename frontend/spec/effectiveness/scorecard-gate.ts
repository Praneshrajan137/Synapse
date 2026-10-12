/**
 * Effectiveness_Scorecard gate -- the schema of an emitted run record, and the second,
 * independent application of the emission rule (task 11.2; R8.1, R8.2, R8.3, R8.6,
 * R8.8).
 *
 * `spec/effectiveness/scorecard-emission.ts` holds the RULE and no imports.
 * This module binds that rule to the authorities the gate must answer to:
 *
 *   * `JOB_ORDER` from `@lib/effectiveness-scorecard` -- the single source of truth for
 *     the five declared Jobs-To-Be-Done. The Playwright emitter necessarily evaluates
 *     the rule against its own local mirror of that list (every e2e spec in this repo
 *     stays clear of the app's `@`-alias module graph). This module evaluates the SAME
 *     rule against the real `JOB_ORDER`, so a drifted mirror produces a named
 *     `missing-job` / `undeclared-job` failure here instead of a quietly wrong
 *     measurement. That is what keeps one source of truth true.
 *   * the emitted document's own schema -- `.strict()`, so an unexpected key is a shape
 *     failure rather than a silently ignored field.
 *   * the Playwright harness run record -- the only place a SKIPPED resilience scenario
 *     is observable. Those specs are sibling files, so the emitter's ledger structurally
 *     cannot see them (R8.6).
 *
 * Nothing here reads the disk. `spec/effectiveness/run-ratchet.ts` does the I/O and
 * calls in; Property 32 (task 11.3) calls in with strings it builds itself.
 */

import { JOB_ORDER, type JobToBeDone } from "@lib/effectiveness-scorecard";
import { z } from "zod";

import {
  type CapturedRow,
  describeEmissionFailure,
  type EmissionCounts,
  type EmissionFailure,
  type EmissionVerdict,
  evaluateEmission,
  type ScenarioRecord,
} from "./scorecard-emission";

export { describeEmissionFailure };

// ---------------------------------------------------------------------------
// The emitted run record
// ---------------------------------------------------------------------------

/**
 * A row as read from an emitted record. The three stamps are nullable AND optional so
 * an unstamped row is a SEMANTIC failure naming the stamp (`unstamped-row`) rather than
 * an opaque shape error -- the same reason `@lib/effectiveness-baseline` reads its
 * candidate rows loosely and rejects them precisely.
 */
const RecordRowSchema = z
  .object({
    job: z.string().min(1),
    steps: z.number().finite().nonnegative(),
    latencyMs: z.number().finite().nonnegative(),
    errorRate: z.number().finite().min(0).max(1),
    harnessVersion: z.string().nullable().optional(),
    seed: z.number().nullable().optional(),
    capturedAt: z.string().nullable().optional(),
  })
  .strict();

/** One ledger entry as read from an emitted record. */
const RecordScenarioSchema = z
  .object({
    scenario: z.string().min(1),
    kind: z.enum(["job", "resilience", "fidelity"]),
    job: z.string().nullable(),
    outcome: z.enum(["executed", "skipped"]),
  })
  .strict();

/**
 * The record a harness run emits at `SCORECARD_FRESH_RELPATH`.
 *
 * It is a superset of `EffectivenessScorecard` -- structurally assignable to it, so
 * `compareScorecard` consumes it unchanged -- plus the three things R8.8 and Property
 * 32 require and a per-run scorecard did not previously carry:
 *
 *   * `harnessReachable` -- so the gate re-checks Property 32's first condition from the
 *     artifact instead of inferring it from the artifact's existence;
 *   * `executedScenarios` / `skippedScenarios` -- the counts R8.8 requires the emitted
 *     scorecard to report;
 *   * `scenarios` -- the ledger those counts are DERIVED from, so the gate can
 *     re-derive them and name a `count-mismatch` rather than trust two integers.
 *
 * The committed BASELINE deliberately carries none of these: a baseline is not a run.
 * Its schema and its check live in `@lib/effectiveness-baseline` (task 11.7).
 */
export const FreshScorecardSchema = z
  .object({
    schemaVersion: z.number().int().positive(),
    harnessVersion: z.string().min(1),
    seed: z.number().finite(),
    rows: z.array(RecordRowSchema),
    interruptionPrecision: z.number().finite().min(0).max(1).nullable(),
    proxyCeiling: z.string().min(1),
    harnessReachable: z.boolean(),
    executedScenarios: z.number().int().nonnegative(),
    skippedScenarios: z.number().int().nonnegative(),
    scenarios: z.array(RecordScenarioSchema),
  })
  .strict();

/** The emitted run record, as validated by {@link FreshScorecardSchema}. */
export type FreshScorecard = z.infer<typeof FreshScorecardSchema>;

/** The outcome of checking one emitted record. */
export interface FreshScorecardCheck {
  /** The parsed record, or `null` when the text was not a record at all. */
  readonly document: FreshScorecard | null;
  readonly verdict: EmissionVerdict<JobToBeDone>;
}

/** Whether a string is one of the five declared Jobs-To-Be-Done. */
export function isDeclaredJob(value: string): value is JobToBeDone {
  return (JOB_ORDER as readonly string[]).includes(value);
}

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function failed(failures: readonly EmissionFailure[], counts: EmissionCounts): FreshScorecardCheck {
  return { document: null, verdict: { outcome: "failed", failures, counts } };
}

const ZERO_COUNTS: EmissionCounts = { executed: 0, skipped: 0, total: 0 };

/**
 * Validates an emitted run record and applies the emission rule to it against the real
 * `JOB_ORDER`.
 *
 * Unparseable text and a shape failure are `malformed-record` failures rather than
 * thrown errors, so one caller handles one shape for every outcome. A record naming a
 * job outside `JOB_ORDER` -- the shape a drifted local mirror produces -- is
 * `undeclared-job`, named, and is NOT quietly dropped from the comparison.
 */
export function checkFreshScorecard(text: string): FreshScorecardCheck {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    return failed(
      [
        {
          kind: "malformed-record",
          subject: "record",
          detail: `not parseable as JSON: ${describeError(err)}`,
        },
      ],
      ZERO_COUNTS,
    );
  }

  const result = FreshScorecardSchema.safeParse(parsed);
  if (!result.success) {
    return failed(
      [
        {
          kind: "malformed-record",
          subject: "record",
          detail: `not an emitted effectiveness scorecard: ${result.error.message}`,
        },
      ],
      ZERO_COUNTS,
    );
  }
  const document = result.data;

  // Partition the rows by whether their job is declared. An undeclared job cannot be
  // narrowed to `JobToBeDone`, so it is reported here and excluded from the rule's
  // input -- which then reports the declared job it failed to cover.
  const preFailures: EmissionFailure[] = [];
  const rows: CapturedRow<JobToBeDone>[] = [];
  const seenUndeclared = new Set<string>();
  for (const row of document.rows) {
    if (!isDeclaredJob(row.job)) {
      if (!seenUndeclared.has(row.job)) {
        seenUndeclared.add(row.job);
        preFailures.push({
          kind: "undeclared-job",
          subject: row.job,
          detail:
            `the record carries a row for "${row.job}", which is not in JOB_ORDER ` +
            "(frontend/src/lib/effectiveness-scorecard.ts) -- the emitter's job list has " +
            "drifted from the single source of truth",
        });
      }
      continue;
    }
    rows.push({
      job: row.job,
      steps: row.steps,
      latencyMs: row.latencyMs,
      errorRate: row.errorRate,
      harnessVersion: row.harnessVersion ?? null,
      seed: row.seed ?? null,
      capturedAt: row.capturedAt ?? null,
    });
  }

  const scenarios: ScenarioRecord<JobToBeDone>[] = [];
  for (const entry of document.scenarios) {
    const job = entry.job;
    if (job !== null && !isDeclaredJob(job)) {
      if (!seenUndeclared.has(job)) {
        seenUndeclared.add(job);
        preFailures.push({
          kind: "undeclared-job",
          subject: job,
          detail:
            `the scenario ledger entry "${entry.scenario}" names job "${job}", which is not ` +
            "in JOB_ORDER (frontend/src/lib/effectiveness-scorecard.ts)",
        });
      }
      scenarios.push({
        scenario: entry.scenario,
        kind: entry.kind,
        job: null,
        outcome: entry.outcome,
      });
      continue;
    }
    scenarios.push({
      scenario: entry.scenario,
      kind: entry.kind,
      job: job === null ? null : job,
      outcome: entry.outcome,
    });
  }

  const verdict = evaluateEmission<JobToBeDone>({
    declaredJobs: JOB_ORDER,
    harnessReachable: document.harnessReachable,
    rows,
    scenarios,
    reportedCounts: {
      executed: document.executedScenarios,
      skipped: document.skippedScenarios,
      total: document.executedScenarios + document.skippedScenarios,
    },
  });

  if (preFailures.length === 0) return { document, verdict };
  const merged: readonly EmissionFailure[] =
    verdict.outcome === "failed" ? [...preFailures, ...verdict.failures] : preFailures;
  return { document, verdict: { outcome: "failed", failures: merged, counts: verdict.counts } };
}

// ---------------------------------------------------------------------------
// The Playwright harness run record
// ---------------------------------------------------------------------------

/**
 * Which of R8.6's three named categories a harness spec belongs to.
 *
 * R8.6 names exactly three things whose skip is a divergence: a Job_To_Be_Done, a
 * resilience scenario, and a real-stack fidelity comparison. The harness suite also
 * carries specs that are none of those -- `spatial-visualization.spec.ts` (Req 10) and
 * `a11y/assistive-tech-flow.spec.ts` (Req 16). Their skips are REPORTED but are not
 * charged against R8.6, because the criterion does not name them and inventing an
 * obligation the requirement never took on would make this gate less credible, not more.
 * `spatial-visualization.spec.ts` in particular carries a deliberate, documented
 * `test.skip(!!process.env.CI, ...)` for a real reason (no GPU/WebGL on a headless
 * runner) with its own stated ratchet.
 */
export type HarnessSpecCategory = "job" | "resilience" | "other";

/** One spec's collapsed outcome in the harness run record. */
export interface HarnessSpecOutcome {
  /** The spec file as the reporter recorded it. */
  readonly file: string;
  readonly title: string;
  readonly category: HarnessSpecCategory;
  /** `skipped` iff every test of the spec reported `skipped`. */
  readonly outcome: "executed" | "skipped";
  /** True when at least one test reported an unexpected or flaky status. */
  readonly failed: boolean;
}

/** What a harness run record shows, split by what R8.6 charges and what it does not. */
export interface HarnessRunReview {
  /** Blocking: zero execution, and every skipped job or resilience scenario (R8.6, R8.8). */
  readonly failures: readonly EmissionFailure[];
  /** Reported, not charged: skipped specs outside R8.6's three named categories. */
  readonly unnamedSkips: readonly HarnessSpecOutcome[];
}

/** Classify a spec file into one of R8.6's categories by its declared filename. */
function categorize(file: string): HarnessSpecCategory {
  if (/task-completion\.jtbd\.spec\.ts$/.test(file)) return "job";
  if (/\.resilience\.spec\.ts$/.test(file)) return "resilience";
  return "other";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringOr(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function collapseSpec(spec: Record<string, unknown>, file: string): HarnessSpecOutcome {
  const tests = asArray(spec.tests);
  let allSkipped = tests.length > 0;
  let failedAny = false;
  for (const candidate of tests) {
    const test = asRecord(candidate);
    const status = typeof test.status === "string" ? test.status : "";
    if (status !== "skipped") allSkipped = false;
    if (status === "unexpected" || status === "flaky") failedAny = true;
  }
  // A spec carrying no test at all produced nothing, which is not an execution.
  const skipped = tests.length === 0 || allSkipped;
  const resolvedFile = stringOr(spec.file, file);
  return {
    file: resolvedFile,
    title: stringOr(spec.title, "(untitled spec)"),
    category: categorize(resolvedFile),
    outcome: skipped ? "skipped" : "executed",
    failed: failedAny,
  };
}

function walkSuites(node: unknown, file: string, out: HarnessSpecOutcome[]): void {
  const suite = asRecord(node);
  const suiteFile = stringOr(suite.file, file);
  for (const spec of asArray(suite.specs)) {
    out.push(collapseSpec(asRecord(spec), suiteFile));
  }
  for (const child of asArray(suite.suites)) {
    walkSuites(child, suiteFile, out);
  }
}

/**
 * Collapses a Playwright JSON run record into one outcome per spec.
 *
 * Walked defensively over `unknown`: the reporter nests specs under optionally nested
 * suites, and a gate that throws on an unfamiliar shape is a gate that stops asking the
 * question. Unparseable text throws, because a record that cannot be read is
 * unavailable, and unavailable is not a pass (I-7) -- the caller turns it into a named
 * hard error.
 */
export function scanHarnessRunRecord(text: string): readonly HarnessSpecOutcome[] {
  const parsed: unknown = JSON.parse(text);
  const out: HarnessSpecOutcome[] = [];
  for (const suite of asArray(asRecord(parsed).suites)) {
    walkSuites(suite, "(unknown file)", out);
  }
  return out;
}

/**
 * Reviews a harness run record (R8.6, R8.8).
 *
 * Three conditions, all three of which the audit found live:
 *
 *   * **The record selected no spec at all.** This is exactly the state task 11.1 found
 *     in `frontend.yml::e2e-harness`: the job ran `pnpm test:e2e --project=chromium
 *     task-completion.jtbd resilience.spec`, and because the `chromium` project carries
 *     `testIgnore: HARNESS_SPEC_PATTERN`, those positional filters matched nothing
 *     runnable. A run record holding zero specs is a `zero-executed` failure, so the
 *     gate can never again report `not_executed` as a pass.
 *   * **Every spec was skipped.** An all-skipped run is a non-passing run (I-7), whatever
 *     the specs were.
 *   * **A Job_To_Be_Done or a resilience scenario was skipped.** Named, and charged. The
 *     scorecard's own ledger sees the jobs; only this record sees the resilience
 *     scenarios, which live in sibling spec files.
 *
 * Skips outside R8.6's three named categories are returned in `unnamedSkips` rather than
 * `failures` -- reported, but not charged against a criterion that does not name them.
 * See {@link HarnessSpecCategory}.
 */
export function reviewHarnessRunRecord(
  outcomes: readonly HarnessSpecOutcome[],
): HarnessRunReview {
  const failures: EmissionFailure[] = [];
  const unnamedSkips: HarnessSpecOutcome[] = [];
  if (outcomes.length === 0) {
    failures.push({
      kind: "zero-executed",
      subject: "harness-run-record",
      detail:
        "the Playwright harness run record contains no spec; the harness suite selected " +
        "nothing runnable, so no effectiveness assertion executed",
    });
    return { failures, unnamedSkips };
  }
  if (outcomes.every((outcome) => outcome.outcome === "skipped")) {
    failures.push({
      kind: "zero-executed",
      subject: "harness-run-record",
      detail: `all ${outcomes.length} harness spec(s) reported skipped`,
    });
  }
  for (const outcome of outcomes) {
    if (outcome.outcome !== "skipped") continue;
    if (outcome.category === "other") {
      unnamedSkips.push(outcome);
      continue;
    }
    failures.push({
      kind: "skipped-scenario",
      subject: `${outcome.file} :: ${outcome.title}`,
      detail:
        `this ${outcome.category} scenario was skipped; a skipped Job_To_Be_Done or ` +
        "resilience scenario is a divergence, not an informational note on a pass (R8.6)",
    });
  }
  return { failures, unnamedSkips };
}
