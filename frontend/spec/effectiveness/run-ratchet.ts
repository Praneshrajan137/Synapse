/**
 * Effectiveness_Ratchet -- CI invocation script and the effectiveness job's blocking
 * gate (design "Where the Scorecard and Ratchet sit"; purpose-achievement-audit R8.1,
 * R8.2, R8.3, R8.6, R8.8, R8.10).
 *
 * ## What this script decides
 *
 * The audit's finding was that this gate compared nothing against nothing and was
 * described as "the REAL effectiveness signal". Four things had to be true at once for
 * that to happen, and this script now refuses each of them independently. It exits
 * non-zero, naming the subject, when ANY of the following holds:
 *
 *   1. **The committed baseline is not a measurement.** Loaded through
 *      `checkCommittedBaseline` (task 11.7) -- NOT through `parseScorecard`, which
 *      accepts any five well-typed numbers and so accepted an authored ceiling. A
 *      baseline whose rows carry no `harnessVersion`/`seed`/`capturedAt`, or whose rows
 *      all carry an identical `steps` and an identical `latencyMs`, is rejected (R8.10).
 *   2. **The emitted run record is not complete.** Re-checked against the real
 *      `JOB_ORDER` via `checkFreshScorecard`: one stamped row per declared
 *      Job_To_Be_Done, no job missing, none repeated, none undeclared, at least one
 *      scenario executed, no scenario skipped, and the reported executed/skipped counts
 *      re-derived from the record's own ledger (R8.1, R8.2, R8.3, R8.8).
 *   3. **The harness run record shows nothing ran, or shows a skipped job or resilience
 *      scenario.** Read from `artifacts/test-reports/playwright-harness.json` -- the file
 *      `playwright.harness.config.ts` writes and `frontend/spec/check_fe_invariants.py`
 *      already reads. A record holding zero specs is the exact state task 11.1 found in
 *      `frontend.yml::e2e-harness`, and it is now a failure rather than a `not_executed`
 *      that nobody consumed (R8.8). A skipped Job_To_Be_Done or resilience scenario is a
 *      divergence (R8.6); a skipped spec outside R8.6's three named categories is printed
 *      on every run but not charged -- see `HarnessSpecCategory` in `scorecard-gate.ts`.
 *   4. **A metric regressed beyond tolerance**, or the number of per-job comparisons
 *      performed is not the declared job count (R8.3).
 *
 * A missing or unreadable baseline, fresh record, policy file, or harness run record is
 * a HARD error naming the file. Absence of proof is never a pass (I-7).
 *
 * ## Expected state on landing, stated plainly (I-7)
 *
 * This gate is RED the day it lands, at step 1: the committed
 * `spec/effectiveness/scorecard.baseline.json` carries `steps: 20` and
 * `latencyMs: 15000` on all five rows and no per-row stamps, so
 * `checkCommittedBaseline` rejects it with five `missing-stamp` findings and one
 * `uniform-metrics`. That is R8.10's finding becoming mechanical, not a defect in this
 * script. It clears exactly one way: a complete harness run measures the five rows, this
 * script writes them through `buildBaseline` to
 * `test-results/effectiveness/scorecard.baseline.candidate.json` (the
 * `effectiveness-scorecard-baseline-candidate` artifact), and an operator commits that
 * file over the current baseline. Never by editing a number, typing a `capturedAt`, or
 * relaxing a threshold.
 *
 * The candidate is written whenever the run record is complete, BEFORE the blocking
 * decision, precisely so the rejected baseline is replaceable; otherwise step 1 would
 * make its own repair unreachable.
 *
 * ## Paths (relative to the `frontend/` root)
 *
 *   * baseline      -> `SCORECARD_BASELINE_RELPATH` (committed, versioned)
 *   * fresh record  -> `SCORECARD_FRESH_RELPATH`, overridable via `argv[2]` or
 *                      `$SCORECARD_FRESH_PATH`
 *   * harness record-> `HARNESS_RUN_RECORD_RELPATH`, overridable via
 *                      `$HARNESS_RUN_RECORD`
 *   * candidate     -> `SCORECARD_BASELINE_CANDIDATE_RELPATH` (gitignored)
 *
 * Every read passes `utf8` explicitly (E-S13-07) and every line of output is ASCII.
 *
 * Run: `pnpm effectiveness:ratchet` (from `frontend/`) -- or
 *      `tsx spec/effectiveness/run-ratchet.ts [freshScorecardPath]`.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { buildBaseline } from "@lib/effectiveness-baseline";
import {
  compareScorecard,
  DEFAULT_RATCHET_TOLERANCE,
  type RatchetResult,
} from "@lib/effectiveness-ratchet";
import {
  type EffectivenessScorecard,
  JOB_ORDER,
  type JobToBeDone,
  SCORECARD_FRESH_RELPATH,
} from "@lib/effectiveness-scorecard";

import { checkCommittedBaselineFile, committedBaselinePath } from "./check-baseline";
import {
  DEFERRED_SCENARIOS,
  describeEmissionFailure,
  type EmissionFailure,
  HARNESS_RUN_RECORD_RELPATH,
  type MeasuredRow,
  SCORECARD_BASELINE_CANDIDATE_RELPATH,
} from "./scorecard-emission";
import {
  checkFreshScorecard,
  type HarnessSpecOutcome,
  reviewHarnessRunRecord,
  scanHarnessRunRecord,
} from "./scorecard-gate";

/** The `frontend/` root: this file lives at `frontend/spec/effectiveness/`. */
const FRONTEND_ROOT = fileURLToPath(new URL("../../", import.meta.url));

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/** Read a file as utf-8 (E-S13-07), turning any failure into a named hard error. */
function readUtf8(path: string, label: string): string {
  try {
    return readFileSync(path, "utf8");
  } catch (err) {
    throw new Error(`Effectiveness ${label} not readable at ${path}: ${describeError(err)}`);
  }
}

function out(text: string): void {
  process.stdout.write(text);
}

function err(text: string): void {
  process.stderr.write(text);
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------

function reportTolerance(): void {
  const tol = DEFAULT_RATCHET_TOLERANCE;
  out(
    "# Effectiveness Ratchet\n\n" +
      `Tolerance: steps +/-${(tol.stepsPct * 100).toFixed(0)}%, ` +
      `latency +/-${(tol.latencyPct * 100).toFixed(0)}%, ` +
      `errorRate +${tol.errorRateAbs}, ` +
      `interruptionPrecision -${tol.interruptionPrecisionAbs}\n\n`,
  );
}

/**
 * Prints every declared out-of-suite deferral. Printed on every run, pass or fail, so an
 * absent scenario stays visible rather than becoming invisible by being excluded.
 */
function reportDeferrals(): void {
  if (DEFERRED_SCENARIOS.length === 0) return;
  out(`## Declared deferrals (${DEFERRED_SCENARIOS.length}) -- recorded as outstanding\n\n`);
  for (const deferred of DEFERRED_SCENARIOS) {
    out(`  * ${deferred.spec} (${deferred.kind}): ${deferred.reason}\n`);
    for (const blocker of deferred.blockers) {
      out(`      - blocker: ${blocker}\n`);
    }
    out(`      - owner: ${deferred.owner}\n`);
  }
  out(
    "\nA deferral is an outstanding divergence, not a pass. It clears when its blockers " +
      "are gone and the spec joins HARNESS_SPEC_PATTERN in playwright.config.ts.\n\n",
  );
}

function reportHarnessRecord(outcomes: readonly HarnessSpecOutcome[]): void {
  const executed = outcomes.filter((outcome) => outcome.outcome === "executed").length;
  const skipped = outcomes.length - executed;
  const failedSpecs = outcomes.filter((outcome) => outcome.failed).length;
  out(
    `## Harness run record\n\n${outcomes.length} spec(s): ${executed} executed, ` +
      `${skipped} skipped, ${failedSpecs} reporting a failed test.\n\n`,
  );
}

function reportFailures(heading: string, failures: readonly EmissionFailure[]): void {
  if (failures.length === 0) return;
  err(`${heading}\n`);
  for (const failure of failures) {
    err(`  * ${describeEmissionFailure(failure)}\n`);
  }
  err("\n");
}

function reportRatchet(result: RatchetResult): void {
  if (result.passed) {
    out(
      "Ratchet: **PASS** -- no job's steps/latency/error-rate and no " +
        "Interruption_Precision regressed beyond tolerance.\n",
    );
    out(
      result.canAdvanceBaseline
        ? "Baseline: every metric improved or held -- the committed baseline MAY be advanced (Req 4.5).\n"
        : "Baseline: some metric regressed within tolerance -- hold the committed baseline.\n",
    );
    return;
  }
  err("Ratchet: **FAIL** -- effectiveness regressed beyond tolerance:\n");
  for (const regression of result.regressions) {
    err(
      `  * ${regression.job} / ${regression.metric}: baseline ${regression.baseline} -> ` +
        `observed ${regression.observed}\n`,
    );
  }
}

// ---------------------------------------------------------------------------
// Baseline candidate
// ---------------------------------------------------------------------------

/** The document-level stamps a baseline candidate inherits from the run that measured it. */
interface CandidateHeader {
  readonly seed: number;
  readonly harnessVersion: string;
  readonly interruptionPrecision: number | null;
}

/**
 * Writes the measured baseline candidate from a complete run, constructed through
 * `buildBaseline` -- the only intended construction path for a baseline. `buildBaseline`
 * cannot manufacture a stamp: each row's `harnessVersion`, `seed`, and `capturedAt`
 * comes from the run, which is the whole point of R8.10.
 *
 * `rows` are the rows the emission rule ACCEPTED (`MeasuredRow`, stamps required), not
 * the loosely-typed rows of the document. That is deliberate: a cast from the document's
 * optional stamps would let a blank stamp reach `buildBaseline`, and `buildBaseline`
 * validates nothing -- it trusts its caller to have measured.
 *
 * Pretty-printed to match the committed artifact's style, because this file is meant to
 * be reviewed in a diff and then committed as-is.
 */
function writeBaselineCandidate(
  rows: readonly MeasuredRow<JobToBeDone>[],
  header: CandidateHeader,
  path: string,
): void {
  const candidate = buildBaseline({
    rows,
    seed: header.seed,
    harnessVersion: header.harnessVersion,
    interruptionPrecision: header.interruptionPrecision,
  });
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${JSON.stringify(candidate, null, 2)}\n`, "utf8");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main(): void {
  const baselinePath = committedBaselinePath();
  const freshPath =
    process.argv[2] ??
    process.env.SCORECARD_FRESH_PATH ??
    join(FRONTEND_ROOT, SCORECARD_FRESH_RELPATH);
  const recordPath =
    process.env.HARNESS_RUN_RECORD ?? join(FRONTEND_ROOT, HARNESS_RUN_RECORD_RELPATH);
  const candidatePath = join(FRONTEND_ROOT, SCORECARD_BASELINE_CANDIDATE_RELPATH);

  reportTolerance();
  reportDeferrals();

  // 1 -- the committed baseline must be a measurement (R8.10, task 11.7).
  const baselineVerdict = checkCommittedBaselineFile(baselinePath);

  // 2 -- the emitted run record must be complete (R8.1, R8.2, R8.3, R8.8).
  const freshCheck = checkFreshScorecard(readUtf8(freshPath, "fresh scorecard"));

  // The candidate is written from a complete run BEFORE the blocking decision, so a
  // rejected baseline has a measured replacement to be superseded by.
  if (freshCheck.verdict.outcome === "complete" && freshCheck.document !== null) {
    const measured = freshCheck.document;
    writeBaselineCandidate(
      freshCheck.verdict.rows,
      {
        seed: measured.seed,
        harnessVersion: measured.harnessVersion,
        interruptionPrecision: measured.interruptionPrecision,
      },
      candidatePath,
    );
    out(`Measured baseline candidate written to ${SCORECARD_BASELINE_CANDIDATE_RELPATH}\n\n`);
  }

  // 3 -- the harness run record must show that something ran, and no skip (R8.6, R8.8).
  const recordText = readUtf8(recordPath, "harness run record");
  let outcomes: readonly HarnessSpecOutcome[];
  try {
    outcomes = scanHarnessRunRecord(recordText);
  } catch (parseErr) {
    throw new Error(
      `Effectiveness harness run record at ${recordPath} is malformed: ${describeError(parseErr)}`,
    );
  }
  reportHarnessRecord(outcomes);
  const review = reviewHarnessRunRecord(outcomes);
  const recordFailures = review.failures;
  if (review.unnamedSkips.length > 0) {
    // Reported, not charged. R8.6 names a Job_To_Be_Done, a resilience scenario, and a
    // real-stack fidelity comparison; these specs are none of the three, so charging them
    // here would be this gate inventing an obligation the requirement never took on. The
    // skip is still printed on every run, so it cannot become invisible.
    out(
      `### Skipped harness specs outside R8.6's three named categories ` +
        `(${review.unnamedSkips.length}) -- reported, not charged\n\n`,
    );
    for (const skipped of review.unnamedSkips) {
      out(`  * ${skipped.file} :: ${skipped.title}\n`);
    }
    out("\n");
  }

  const baselineRejected = baselineVerdict.outcome === "rejected";
  const emissionFailed = freshCheck.verdict.outcome === "failed";

  if (baselineRejected || emissionFailed || recordFailures.length > 0) {
    if (baselineVerdict.outcome === "rejected") {
      err(
        `Baseline: **REJECTED** -- ${baselinePath} is not a measurement (R8.10):\n`,
      );
      for (const rejection of baselineVerdict.rejections) {
        const subject = rejection.job === null ? "baseline" : rejection.job;
        err(`  * [${rejection.kind}] ${subject}: ${rejection.detail}\n`);
      }
      err("\n");
    }
    if (freshCheck.verdict.outcome === "failed") {
      reportFailures(
        `Emission: **FAILED** -- ${freshPath} is not a complete scorecard (R8.1, R8.2, R8.3, R8.8):`,
        freshCheck.verdict.failures,
      );
    }
    reportFailures(
      `Harness run: **FAILED** -- ${recordPath} (R8.6, R8.8):`,
      recordFailures,
    );
    err(
      "The effectiveness job records a FAILED result. A skipped job, resilience scenario, " +
        "or fidelity comparison is a failed result -- never a shorter scorecard, never an " +
        "informational note on a pass (I-7). Fix it by making the harness run produce the " +
        "measurement, not by relaxing this gate.\n",
    );
    process.exitCode = 1;
    return;
  }

  // Unreachable given the guard above; keeps the narrowing total rather than asserted.
  if (baselineVerdict.outcome !== "accepted" || freshCheck.verdict.outcome !== "complete") {
    err("Effectiveness ratchet: internal verdict narrowing failed.\n");
    process.exitCode = 1;
    return;
  }
  const document = freshCheck.document;
  if (document === null) {
    err("Effectiveness ratchet: a complete verdict carried no document.\n");
    process.exitCode = 1;
    return;
  }

  const baseline = baselineVerdict.baseline;
  const freshRows = freshCheck.verdict.rows;

  // 4a -- R8.3: the count of per-job comparisons must equal the declared job count. It
  // is DERIVED from the two row sets, never asserted: a job present in one side only
  // would silently reduce the comparison count, which is how zero comparisons once read
  // as a pass.
  const baselineJobs = new Set(baseline.rows.map((row) => row.job));
  const missingFromBaseline = JOB_ORDER.filter((job) => !baselineJobs.has(job));
  const comparisons = freshRows.filter((row) => baselineJobs.has(row.job)).length;
  if (missingFromBaseline.length > 0 || comparisons !== JOB_ORDER.length) {
    err(
      `Comparison coverage: **FAILED** -- ${comparisons} per-job comparison(s) against ` +
        `${JOB_ORDER.length} declared Job(s)-To-Be-Done (R8.3).\n`,
    );
    for (const job of missingFromBaseline) {
      err(`  * ${job}: the committed baseline holds no row for this declared job\n`);
    }
    process.exitCode = 1;
    return;
  }

  const fresh: EffectivenessScorecard = {
    schemaVersion: document.schemaVersion,
    harnessVersion: document.harnessVersion,
    seed: document.seed,
    rows: freshRows,
    interruptionPrecision: document.interruptionPrecision,
    proxyCeiling: document.proxyCeiling,
  };

  out(
    `## Completeness\n\n${freshRows.length} measured row(s) for ${JOB_ORDER.length} declared ` +
      `Job(s)-To-Be-Done; ${document.executedScenarios} scenario(s) executed, ` +
      `${document.skippedScenarios} skipped; ${comparisons} per-job comparison(s) performed.\n\n`,
  );

  const result = compareScorecard(baseline, fresh, DEFAULT_RATCHET_TOLERANCE);
  reportRatchet(result);
  if (!result.passed) process.exitCode = 1;
}

// Run only when invoked directly (not when imported by a test).
const isDirectRun =
  process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1];

if (isDirectRun) {
  try {
    main();
  } catch (crash: unknown) {
    err(`\nEffectiveness ratchet crashed: ${describeError(crash)}\n`);
    process.exitCode = 1;
  }
}
