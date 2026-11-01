/**
 * Effectiveness_Ratchet -- CI invocation script and the effectiveness job's blocking gate
 * (design "Where the Scorecard and Ratchet sit"; purpose-achievement-audit R8.1, R8.2, R8.3,
 * R8.6, R8.8, R8.10; ADR-059).
 *
 * ## Two modes
 *
 *   * `pnpm effectiveness:ratchet seal` -- on each `e2e-harness` leg, after the harness has
 *     run. Re-checks the emitted `scorecard.json` against the complete-or-failed rule and writes
 *     `scorecard.leg.json`: the same record plus the leg stamp `{ index, count, commitSha }`,
 *     read from `$HARNESS_LEG` (`matrix.leg`), `$HARNESS_LEG_TOTAL` (`strategy.job-total`) and
 *     `$HARNESS_COMMIT_SHA` (`github.sha`). It refuses an incomplete record, a leg index
 *     outside 1..k, a matrix whose size is not k, and a commit that is not a 40-character sha,
 *     so the workflow's matrix and `EFFECTIVENESS_LEG_COUNT` cannot drift apart silently.
 *   * `pnpm effectiveness:ratchet [legsDir]` -- once, in `effectiveness-ratchet`, over the
 *     downloaded `effectiveness-leg-<n>` artifacts.
 *
 * ## What the ratchet refuses
 *
 * It exits non-zero, naming the subject, when ANY of the following holds:
 *
 *   1. **The committed baseline is not a measurement**, through `checkCommittedBaseline`: the
 *      one-run format (refused by name, `one-run-format`), a missing stamp, a sample set other
 *      than legs 1..k, a row latency that is not its samples' median, or an authored ceiling
 *      (R8.10, ADR-059).
 *   2. **A leg's sealed record is missing, malformed, or incomplete** under the emission rule
 *      applied against the real `JOB_ORDER` (R8.1, R8.2, R8.3, R8.8).
 *   3. **The arrival proof fails**: not exactly k sealed scorecards, a leg claimed twice or not
 *      at all, a stamp outside the design, or more than one commit or harness version. A
 *      missing leg is a failure, never a median of fewer.
 *   4. **The legs disagree** on `steps`, `errorRate`, a row's seed or harness version, or
 *      `interruptionPrecision`. The harness claims determinism for those.
 *   5. **A leg's harness run record shows nothing ran, or a skipped job or resilience
 *      scenario** (R8.6, R8.8). All k records are read, not leg 1's alone: a skip that
 *      happens in one leg is visible only in that leg's record, and the medians are taken
 *      over every leg. A skip outside R8.6's three named categories is printed on every run
 *      but not charged -- see `HarnessSpecCategory` in `scorecard-gate.ts`.
 *   6. **A metric regressed**, or the number of per-job comparisons is not the declared job
 *      count (R8.3).
 *
 * Absence of proof is never a pass (I-7).
 *
 * ## Expected state on landing, stated plainly (I-7)
 *
 * RED at step 1. The committed baseline is the one-run placeholder (`schemaVersion: 1`,
 * `steps: 20` and `latencyMs: 15000` on all five rows, no stamps), and the check refuses that
 * format by name before reading its numbers. It clears one way: a run whose k legs arrive,
 * agree and carry clean records writes the k-sample candidate through `buildBaseline` to
 * `test-results/effectiveness/scorecard.baseline.candidate.json` (the
 * `effectiveness-baseline-candidate` artifact), and an operator commits that file over the
 * baseline unedited. Never by editing a number, typing a `capturedAt`, widening `latencyPct`,
 * or relaxing a threshold.
 *
 * The candidate is written BEFORE the blocking decision, so a rejected baseline has a measured
 * replacement, and only from a clean measurement: every leg arrived sealed and complete, with a
 * clean harness record, and the k legs agree. A run with any other finding writes no candidate,
 * so no candidate can be committed from a run that was red for a reason of its own.
 *
 * ## Paths (relative to the `frontend/` root)
 *
 *   * baseline   -> `SCORECARD_BASELINE_RELPATH` (committed, versioned)
 *   * legs       -> `SCORECARD_LEGS_RELPATH`, overridable via `argv[2]` or
 *                   `$SCORECARD_LEGS_DIR`. Each immediate subdirectory is one downloaded leg
 *                   artifact and mirrors that leg's `frontend/` root, so it holds
 *                   `SCORECARD_LEG_RELPATH` and `HARNESS_RUN_RECORD_RELPATH`.
 *   * candidate  -> `SCORECARD_BASELINE_CANDIDATE_RELPATH` (gitignored)
 *
 * Every read passes `utf8` explicitly (E-S13-07) and every line of output is ASCII.
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { buildBaseline } from "@lib/effectiveness-baseline";
import {
  type ArrivalFailure,
  checkLegArrival,
  compareLegMedians,
  DEFAULT_RATCHET_TOLERANCE,
  EFFECTIVENESS_LEG_COUNT,
  LATENCY_NOISE_MULTIPLIER,
  type LatencyJudgement,
  type LegDisagreement,
  type LegScorecard,
  type LegStamp,
  MAD_NORMAL_CONSISTENCY,
  poolLegs,
  type RatchetResult,
} from "@lib/effectiveness-ratchet";
import { JOB_ORDER, SCORECARD_FRESH_RELPATH } from "@lib/effectiveness-scorecard";

import { checkCommittedBaselineFile, committedBaselinePath } from "./check-baseline";
import {
  DEFERRED_SCENARIOS,
  describeEmissionFailure,
  HARNESS_RUN_RECORD_RELPATH,
  SCORECARD_BASELINE_CANDIDATE_RELPATH,
  SCORECARD_LEG_RELPATH,
  SCORECARD_LEGS_RELPATH,
} from "./scorecard-emission";
import {
  checkSealedLegScorecard,
  type HarnessSpecOutcome,
  reviewHarnessRunRecord,
  scanHarnessRunRecord,
  sealLegScorecard,
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

/** A file's utf-8 text, or `null` when it does not exist. Any other read error is a crash. */
function readIfPresent(path: string, label: string): string | null {
  return existsSync(path) ? readUtf8(path, label) : null;
}

function out(text: string): void {
  process.stdout.write(text);
}

function err(text: string): void {
  process.stderr.write(text);
}

function percent(fraction: number): string {
  return `${(fraction * 100).toFixed(0)}%`;
}

function ms(value: number): string {
  return value.toFixed(2);
}

// ---------------------------------------------------------------------------
// Seal mode: one leg names itself
// ---------------------------------------------------------------------------

/** A positive integer read from an environment variable, or `null`. */
function positiveInteger(raw: string | undefined): number | null {
  if (raw === undefined || !/^[1-9][0-9]*$/.test(raw)) return null;
  return Number(raw);
}

type StampRead =
  | { readonly ok: true; readonly stamp: LegStamp }
  | { readonly ok: false; readonly problems: readonly string[] };

/**
 * The leg stamp from the three variables the workflow sets on the seal step. Only presence and
 * integer syntax are checked here; whether the stamp fits the k-leg design is
 * `sealLegScorecard`'s question.
 */
function legStampFromEnvironment(env: Readonly<Record<string, string | undefined>>): StampRead {
  const problems: string[] = [];
  const index = positiveInteger(env.HARNESS_LEG);
  if (index === null) {
    problems.push(`HARNESS_LEG is "${env.HARNESS_LEG ?? ""}", not a positive integer (matrix.leg)`);
  }
  const count = positiveInteger(env.HARNESS_LEG_TOTAL);
  if (count === null) {
    problems.push(
      `HARNESS_LEG_TOTAL is "${env.HARNESS_LEG_TOTAL ?? ""}", not a positive integer ` +
        "(strategy.job-total)",
    );
  }
  const commitSha = env.HARNESS_COMMIT_SHA ?? "";
  if (commitSha.length === 0) problems.push("HARNESS_COMMIT_SHA is not set (github.sha)");
  if (index === null || count === null || problems.length > 0) return { ok: false, problems };
  return { ok: true, stamp: { index, count, commitSha } };
}

function sealMain(): void {
  const read = legStampFromEnvironment(process.env);
  if (!read.ok) {
    err("Leg seal: **REFUSED** -- this leg cannot name itself:\n");
    for (const problem of read.problems) err(`  * ${problem}\n`);
    process.exitCode = 1;
    return;
  }
  const freshPath = join(FRONTEND_ROOT, SCORECARD_FRESH_RELPATH);
  const sealed = sealLegScorecard(
    readUtf8(freshPath, "fresh scorecard"),
    read.stamp,
    EFFECTIVENESS_LEG_COUNT,
  );
  if (sealed.outcome === "refused") {
    err(`Leg seal: **REFUSED** -- leg ${read.stamp.index} cannot be sealed (ADR-059):\n`);
    for (const failure of sealed.emission) err(`  * ${describeEmissionFailure(failure)}\n`);
    for (const problem of sealed.stamp) err(`  * [leg-stamp] ${problem}\n`);
    process.exitCode = 1;
    return;
  }
  const sealedPath = join(FRONTEND_ROOT, SCORECARD_LEG_RELPATH);
  mkdirSync(dirname(sealedPath), { recursive: true });
  writeFileSync(sealedPath, sealed.text, "utf8");
  out(
    `Leg ${read.stamp.index} of ${read.stamp.count} at ${read.stamp.commitSha} sealed to ` +
      `${SCORECARD_LEG_RELPATH}\n`,
  );
}

// ---------------------------------------------------------------------------
// Ratchet mode: reading the k legs
// ---------------------------------------------------------------------------

/** One downloaded leg artifact: a directory that mirrors one leg's `frontend/` root. */
interface LegSlot {
  readonly name: string;
  readonly root: string;
}

/** What one slot proved, and every reason it did not prove more. */
interface SlotReading {
  readonly slot: LegSlot;
  /** The leg this slot proved, or `null` when its sealed record is unusable. */
  readonly scorecard: LegScorecard | null;
  /** Why the slot's sealed record is unusable. */
  readonly recordProblems: readonly string[];
  /** The harness run record's per-spec outcomes, or `null` when it could not be read. */
  readonly outcomes: readonly HarnessSpecOutcome[] | null;
  /** Blocking findings from the harness run record (R8.6, R8.8). */
  readonly harnessProblems: readonly string[];
  /** Skips outside R8.6's three named categories: reported, not charged. */
  readonly unnamedSkips: readonly HarnessSpecOutcome[];
}

function listLegSlots(legsDir: string): readonly LegSlot[] {
  if (!existsSync(legsDir)) return [];
  return readdirSync(legsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => ({ name: entry.name, root: join(legsDir, entry.name) }))
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
}

function readSealedScorecard(slot: LegSlot): {
  readonly scorecard: LegScorecard | null;
  readonly problems: readonly string[];
} {
  const sealedPath = join(slot.root, SCORECARD_LEG_RELPATH);
  const text = readIfPresent(sealedPath, "sealed leg scorecard");
  if (text === null) {
    return {
      scorecard: null,
      problems: [
        `no sealed scorecard at ${sealedPath}: the leg's seal step did not write one, or ` +
          "its artifact does not carry it",
      ],
    };
  }
  const check = checkSealedLegScorecard(text);
  if (check.verdict.outcome === "failed") {
    return { scorecard: null, problems: check.verdict.failures.map(describeEmissionFailure) };
  }
  if (check.document === null || check.leg === null) {
    return { scorecard: null, problems: ["a complete verdict carried no record or leg stamp"] };
  }
  return {
    scorecard: {
      leg: check.leg,
      harnessVersion: check.document.harnessVersion,
      seed: check.document.seed,
      rows: check.verdict.rows,
      interruptionPrecision: check.document.interruptionPrecision,
    },
    problems: [],
  };
}

function readSlot(slot: LegSlot): SlotReading {
  const sealed = readSealedScorecard(slot);
  const recordPath = join(slot.root, HARNESS_RUN_RECORD_RELPATH);
  const recordText = readIfPresent(recordPath, "harness run record");
  const base = { slot, scorecard: sealed.scorecard, recordProblems: sealed.problems };
  if (recordText === null) {
    return {
      ...base,
      outcomes: null,
      harnessProblems: [`no harness run record at ${recordPath}`],
      unnamedSkips: [],
    };
  }
  let outcomes: readonly HarnessSpecOutcome[];
  try {
    outcomes = scanHarnessRunRecord(recordText);
  } catch (parseErr) {
    return {
      ...base,
      outcomes: null,
      harnessProblems: [
        `the harness run record at ${recordPath} is malformed: ${describeError(parseErr)}`,
      ],
      unnamedSkips: [],
    };
  }
  const review = reviewHarnessRunRecord(outcomes);
  return {
    ...base,
    outcomes,
    harnessProblems: review.failures.map(describeEmissionFailure),
    unnamedSkips: review.unnamedSkips,
  };
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------

function reportRules(): void {
  const tol = DEFAULT_RATCHET_TOLERANCE;
  out(
    "# Effectiveness Ratchet (ADR-059)\n\n" +
      `Legs: exactly ${EFFECTIVENESS_LEG_COUNT}, legs 1..${EFFECTIVENESS_LEG_COUNT} of one ` +
      "commit and one harness version.\n" +
      `Exact metrics, identical in every leg: steps +${percent(tol.stepsPct)}, ` +
      `errorRate +${tol.errorRateAbs}, interruptionPrecision -${tol.interruptionPrecisionAbs}.\n` +
      `Latency: a row regresses iff med_f - med_b > max(${percent(tol.latencyPct)} x med_b, ` +
      `${LATENCY_NOISE_MULTIPLIER} x ${MAD_NORMAL_CONSISTENCY} x MAD_b), with med_b and MAD_b ` +
      "from the baseline's own samples, never pooled with the fresh ones.\n\n",
  );
}

/**
 * Prints every declared out-of-suite deferral. Printed on every run, pass or fail, so an absent
 * scenario stays visible rather than becoming invisible by being excluded.
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

function describeRecord(outcomes: readonly HarnessSpecOutcome[] | null): string {
  if (outcomes === null) return "harness run record unreadable";
  const executed = outcomes.filter((outcome) => outcome.outcome === "executed").length;
  const failedSpecs = outcomes.filter((outcome) => outcome.failed).length;
  return (
    `${outcomes.length} spec(s): ${executed} executed, ${outcomes.length - executed} ` +
    `skipped, ${failedSpecs} reporting a failed test`
  );
}

function reportLegs(legsDir: string, readings: readonly SlotReading[]): void {
  out(`## Legs (${readings.length} artifact(s) under ${legsDir})\n\n`);
  for (const reading of readings) {
    const scorecard = reading.scorecard;
    const identity =
      scorecard === null
        ? "no usable sealed scorecard"
        : `leg ${scorecard.leg.index} of ${scorecard.leg.count} at ${scorecard.leg.commitSha}, ` +
          `harness ${scorecard.harnessVersion}`;
    out(`  * ${reading.slot.name}: ${identity}; ${describeRecord(reading.outcomes)}\n`);
  }
  out("\n");
  const skipping = readings.filter((reading) => reading.unnamedSkips.length > 0);
  if (skipping.length === 0) return;
  // Reported, not charged. R8.6 names a Job_To_Be_Done, a resilience scenario, and a real-stack
  // fidelity comparison; these specs are none of the three, so charging them here would be this
  // gate inventing an obligation the requirement never took on. The skip is still printed on
  // every run, per leg, so it cannot become invisible.
  out("### Skipped harness specs outside R8.6's three named categories -- reported, not charged\n\n");
  for (const reading of skipping) {
    for (const skipped of reading.unnamedSkips) {
      out(`  * ${reading.slot.name}: ${skipped.file} :: ${skipped.title}\n`);
    }
  }
  out("\n");
}

function reportList(heading: string, lines: readonly string[]): void {
  if (lines.length === 0) return;
  err(`${heading}\n`);
  for (const line of lines) err(`  * ${line}\n`);
  err("\n");
}

function describeArrival(failure: ArrivalFailure): string {
  return `[${failure.kind}] ${failure.subject}: ${failure.detail}`;
}

function describeDisagreement(disagreement: LegDisagreement): string {
  const values = disagreement.values
    .map((entry) => `leg ${entry.leg} ${String(entry.value)}`)
    .join(", ");
  return `[legs-disagree] ${disagreement.subject} / ${disagreement.metric}: ${values}`;
}

function reportLatency(judgements: readonly LatencyJudgement[]): void {
  out(
    `## Latency: the median of ${EFFECTIVENESS_LEG_COUNT} legs against the baseline's ` +
      `${EFFECTIVENESS_LEG_COUNT} samples (ms)\n\n`,
  );
  for (const judgement of judgements) {
    const delta = judgement.freshMedian - judgement.baselineMedian;
    out(
      `  * ${judgement.job}: med_b ${ms(judgement.baselineMedian)}, MAD_b ` +
        `${ms(judgement.baselineMad)}; allowance max(${ms(judgement.relativeAllowance)}, ` +
        `${ms(judgement.noiseAllowance)}) = ${ms(judgement.allowance)}; med_f ` +
        `${ms(judgement.freshMedian)} (${delta >= 0 ? "+" : ""}${ms(delta)}) -> ` +
        `${judgement.regressed ? "REGRESSED" : "held"}\n`,
    );
  }
  const active = judgements.filter((judgement) => judgement.baselineMad > 0).length;
  out(
    active === 0
      ? "\nMAD_b is 0 on every row: the band is the relative term alone on every row " +
          "(ADR-059, AK4).\n\n"
      : `\nThe noise term is live (MAD_b > 0) on ${active} of ${judgements.length} row(s).\n\n`,
  );
}

function reportRatchet(result: RatchetResult): void {
  if (result.passed) {
    out(
      "Ratchet: **PASS** -- no job's steps, error-rate or median latency and no " +
        "Interruption_Precision regressed beyond tolerance.\n",
    );
    out(
      result.canAdvanceBaseline
        ? "Baseline: every metric improved or held -- the committed baseline MAY be advanced (Req 4.5).\n"
        : "Baseline: some metric worsened within tolerance -- hold the committed baseline.\n",
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
// Ratchet mode: the decision
// ---------------------------------------------------------------------------

function ratchetMain(): void {
  const legsDir =
    process.argv[2] ??
    process.env.SCORECARD_LEGS_DIR ??
    join(FRONTEND_ROOT, SCORECARD_LEGS_RELPATH);
  const baselinePath = committedBaselinePath();
  const candidatePath = join(FRONTEND_ROOT, SCORECARD_BASELINE_CANDIDATE_RELPATH);

  reportRules();
  reportDeferrals();

  // 1 -- the committed baseline must be a measurement (R8.10, ADR-059).
  const baselineVerdict = checkCommittedBaselineFile(baselinePath);

  // 2 and 5 -- every leg's sealed record and harness run record.
  const readings = listLegSlots(legsDir).map(readSlot);
  reportLegs(legsDir, readings);
  const recordProblems = readings.flatMap((reading) =>
    reading.recordProblems.map((problem) => `${reading.slot.name}: ${problem}`),
  );
  const harnessProblems = readings.flatMap((reading) =>
    reading.harnessProblems.map((problem) => `${reading.slot.name}: ${problem}`),
  );

  // 3 and 4 -- the arrival proof, then the identical-across-legs rule.
  const legs = readings.flatMap((reading) =>
    reading.scorecard === null ? [] : [reading.scorecard],
  );
  const arrival = checkLegArrival(legs, EFFECTIVENESS_LEG_COUNT);
  const pool = arrival.outcome === "arrived" ? poolLegs(arrival) : null;
  const arrivalProblems = arrival.outcome === "refused" ? arrival.failures : [];
  const disagreements = pool !== null && pool.outcome === "disagreed" ? pool.disagreements : [];
  if (arrival.outcome === "arrived") {
    out(
      `Arrival: **PROVEN** -- legs 1..${arrival.legs.length} at ${arrival.commitSha}, ` +
        `harness ${arrival.harnessVersion}, master seed ${arrival.seed}.\n`,
    );
  }
  if (pool !== null && pool.outcome === "pooled") {
    out(
      "Agreement: every leg reports identical steps, errorRate, row seeds, row harness " +
        "versions and interruptionPrecision.\n\n",
    );
  }

  // The candidate is written from a clean measurement BEFORE the blocking decision, so a
  // rejected baseline has a measured replacement to be superseded by.
  const measurementClean =
    recordProblems.length === 0 &&
    harnessProblems.length === 0 &&
    pool !== null &&
    pool.outcome === "pooled";
  const buildProblems: string[] = [];
  if (measurementClean) {
    const built = buildBaseline(legs);
    if (built.outcome === "built") {
      mkdirSync(dirname(candidatePath), { recursive: true });
      // Pretty-printed to match the committed artifact's style: this file is reviewed in a diff
      // and then committed as-is.
      writeFileSync(candidatePath, `${JSON.stringify(built.baseline, null, 2)}\n`, "utf8");
      out(
        `Measured baseline candidate (${EFFECTIVENESS_LEG_COUNT} legs at ` +
          `${built.baseline.commitSha}) written to ${SCORECARD_BASELINE_CANDIDATE_RELPATH}\n\n`,
      );
    } else {
      // Unreachable while the same legs proved arrival and agreement above; kept total.
      buildProblems.push(...built.arrival.map(describeArrival));
      buildProblems.push(...built.disagreements.map(describeDisagreement));
    }
  } else {
    out("No baseline candidate written: this run's measurement is not clean (see below).\n\n");
  }

  const measurementFailed = !measurementClean || buildProblems.length > 0;
  if (baselineVerdict.outcome === "rejected" || measurementFailed) {
    if (baselineVerdict.outcome === "rejected") {
      err(`Baseline: **REJECTED** -- ${baselinePath} is not a measurement (R8.10, ADR-059):\n`);
      for (const rejection of baselineVerdict.rejections) {
        const subject = rejection.job === null ? "baseline" : rejection.job;
        err(`  * [${rejection.kind}] ${subject}: ${rejection.detail}\n`);
      }
      err("\n");
    }
    reportList(
      "Sealed leg records: **FAILED** (R8.1, R8.2, R8.3, R8.8):",
      recordProblems,
    );
    reportList(
      `Arrival: **REFUSED** -- not exactly ${EFFECTIVENESS_LEG_COUNT} legs of one commit (ADR-059):`,
      arrivalProblems.map(describeArrival),
    );
    reportList(
      "Agreement: **FAILED** -- the legs disagree on a metric the harness claims is deterministic:",
      disagreements.map(describeDisagreement),
    );
    reportList("Harness run records: **FAILED** (R8.6, R8.8):", harnessProblems);
    reportList("Baseline candidate: **NOT BUILT**:", buildProblems);
    err(
      "The effectiveness job records a FAILED result. A missing leg, a skipped job, " +
        "resilience scenario or fidelity comparison, or legs that disagree is a failed result -- " +
        "never a median of fewer, never an informational note on a pass (I-7). Fix it by " +
        "making the harness legs produce the measurement, not by relaxing this gate.\n",
    );
    process.exitCode = 1;
    return;
  }

  // Unreachable given the guard above; keeps the narrowing total rather than asserted.
  if (baselineVerdict.outcome !== "accepted" || pool === null || pool.outcome !== "pooled") {
    err("Effectiveness ratchet: internal verdict narrowing failed.\n");
    process.exitCode = 1;
    return;
  }
  const baseline = baselineVerdict.baseline;
  const fresh = pool.measurement;
  out(
    `Baseline measured by ${baseline.legCount} legs at ${baseline.commitSha}; fresh legs ` +
      `measured ${fresh.commitSha}.\n\n`,
  );

  // 6a -- R8.3: the count of per-job comparisons must equal the declared job count. It is
  // DERIVED from the two row sets, never asserted: a job present on one side only would
  // silently reduce the comparison count, which is how zero comparisons once read as a pass.
  const baselineJobs = new Set(baseline.rows.map((row) => row.job));
  const missingFromBaseline = JOB_ORDER.filter((job) => !baselineJobs.has(job));
  const comparisons = fresh.rows.filter((row) => baselineJobs.has(row.job)).length;
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
  out(
    `## Completeness\n\n${legs.length} legs x ${fresh.rows.length} measured row(s) for ` +
      `${JOB_ORDER.length} declared Job(s)-To-Be-Done; ${comparisons} per-job comparison(s) ` +
      "performed.\n\n",
  );

  // 6b -- the comparison itself.
  const result = compareLegMedians(baseline, fresh, DEFAULT_RATCHET_TOLERANCE);
  reportLatency(result.latency);
  reportRatchet(result);
  if (!result.passed) process.exitCode = 1;
}

function main(): void {
  if (process.argv[2] === "seal") {
    sealMain();
    return;
  }
  ratchetMain();
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
