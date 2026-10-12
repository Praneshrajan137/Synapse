/**
 * Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
 *
 * Validates: Requirements 8.1, 8.2, 8.3, 8.6, 8.8
 *
 * The audit's finding was not that the scorecard was wrong. It was that a scorecard with
 * `rows: []` was emitted, accepted, compared against nothing, and reported as "the REAL
 * effectiveness signal". So the claim under test is a BICONDITIONAL, universally quantified
 * over harness run outcomes: an Effectiveness_Scorecard is accepted if and only if the run
 * that produced it exhibits a bijection between its emitted rows and the five declared
 * Jobs-To-Be-Done, every row carries the capture metadata of that run, the harness was
 * reachable, at least one scenario executed, and nothing was skipped. Every other run reaches
 * a FAILED verdict. Not a warning on a pass, not an informational note, and — the shape the
 * audit actually found — never a shorter-but-accepted scorecard: the failing branch of
 * `EmissionVerdict` structurally carries no `rows` at all, which the rejecting facets assert
 * directly rather than infer from the outcome tag.
 *
 * The facets exercise the real production rule (`spec/effectiveness/scorecard-emission.ts`),
 * its gate binding against the real `JOB_ORDER` (`spec/effectiveness/scorecard-gate.ts`), and
 * the Playwright run-record review in the same module. They are sufficient because between
 * them they cover every input dimension the verdict is a function of, and each is varied
 * while the others are held intact so a named failure is attributable:
 *
 *   1. Guard — the input space is non-empty and `jobCoverageArb` reaches all four
 *      `JobCoverageKind`s, so no facet below can pass vacuously.
 *   2. Complement (R8.1, R8.2) — a genuinely complete, fully-executed, stamped run is
 *      ACCEPTED, with five rows in `JOB_ORDER` carrying the offered metrics and stamps.
 *   3. Stamps (R8.2) — acceptance tracks stamp presence: a row that cannot name the run that
 *      captured it is rejected naming the absent stamp, at an intact row count.
 *   4. Bijection (R8.1, R8.2, R8.3) — a missing job, a duplicated job, and an empty emitted
 *      row set each fail, naming the job.
 *   5. Empty declared job set — the bijection is vacuous, and an unevaluable rule is not a
 *      satisfied one (I-7).
 *   6. Reachability (R8.1, R8.2) — metamorphic: flipping `harnessReachable` on one otherwise
 *      identical run flips the verdict.
 *   7. Partition (R8.6, R8.8) — `executed` and `skipped` partition the scenario set; a zero
 *      executed count fails, and each skip is charged exactly once.
 *   8. Skip kinds (R8.6) — a skipped job scenario, resilience scenario, or fidelity
 *      comparison each fail IN ISOLATION, naming the scenario and its kind.
 *   9. Gate agreement (R8.3) — the emitted document re-decided against the real `JOB_ORDER`
 *      yields the same verdict as the rule applied at emission time.
 *  10. Doctored counts (R8.8) — reported counts are re-derived from the ledger, never trusted.
 *  11. Run record (R8.6, R8.8) — a suite that selected nothing, an all-skipped suite, and a
 *      skipped job/resilience spec are charged; a skip outside R8.6's three named categories
 *      is reported without being charged.
 *  12. Deferral is not a skip defect — `DEFERRED_SCENARIOS` is absent from a run's ledger, so
 *      a declared deferral does not make a complete run fail.
 *  13. Deferral cannot launder a skip — being on the deferral list buys no exemption: once a
 *      scenario appears in the ledger, or in the run record, reported skipped, it is charged.
 *
 * Browser-driven cases are deliberately out of scope here: this file stays pure and fast
 * (no disk, no clock, no DOM), per task 11.3's split between fast-check in
 * `spec/effectiveness/` and browser-driven cases run in `frontend.yml`.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  EFFECTIVENESS_HARNESS_SEED,
  EFFECTIVENESS_HARNESS_VERSION,
  JOB_ORDER,
  type JobToBeDone,
  SCORECARD_SCHEMA_VERSION,
  SCRIPTED_PROXY_CEILING,
} from "@lib/effectiveness-scorecard";

import {
  baselineCaseArb,
  capturedScorecardRowArb,
  jobArb,
  type JobCoverage,
  jobCoverageArb,
  type JobCoverageKind,
  jobSetArb,
} from "../arbitraries";
import {
  type CapturedRow,
  DEFERRED_SCENARIOS,
  type EmissionFailure,
  type EmissionFailureKind,
  type EmissionInput,
  type EmissionVerdict,
  evaluateEmission,
  type ScenarioKind,
  type ScenarioRecord,
} from "../scorecard-emission";
import {
  checkFreshScorecard,
  type HarnessSpecCategory,
  reviewHarnessRunRecord,
  scanHarnessRunRecord,
} from "../scorecard-gate";

// ---------------------------------------------------------------------------
// Generators — composed from `../arbitraries`, never re-declared
// ---------------------------------------------------------------------------

/**
 * Five FULLY STAMPED rows, one per declared job, in `JOB_ORDER` — the row set a passing run
 * offers.
 *
 * Drawn from the shared `baselineCaseArb` with the one defect that holes a stamp filtered
 * out, rather than by re-declaring `harnessVersion` / `seed` / `capturedAt` generators here:
 * the three stamp generators live in `../arbitraries` and a second copy of a generator is a
 * second thing to drift. `absent-ceiling` and `uniform-metrics` both leave every row stamped
 * (they defect the ceiling statement and the metric spread, which Property 36 owns and
 * Property 32 does not read), so filtering only `missing-stamp` keeps 3 draws in 4.
 */
const stampedRowsArb = baselineCaseArb
  .filter((candidate) => candidate.defect !== "missing-stamp")
  .map((candidate): readonly CapturedRow<JobToBeDone>[] => candidate.rows);

/**
 * Five rows, one per declared job, each of which MAY be missing one of its three stamps —
 * `capturedScorecardRowArb`'s own drop mode, which drops at most one stamp per row.
 *
 * The accept side of the stamp biconditional is NOT reachable here at any useful rate (each
 * row is fully stamped 1 draw in 4, so all five are 1 in 1024). Facet 2 owns that side with a
 * generator that always stamps; facet 3 owns the reject side, where this generator lands
 * essentially always. The guard test asserts the drop mode really is reached, so facet 3
 * cannot pass by never holing a stamp.
 */
const offeredRowsArb = fc
  .tuple(...JOB_ORDER.map((job) => capturedScorecardRowArb(job)))
  .map((rows): readonly CapturedRow<JobToBeDone>[] => rows);

/** The coverage a passing run has: exactly one row for each of the five declared jobs. */
const COMPLETE_COVERAGE: JobCoverage = { kind: "complete", emitted: [...JOB_ORDER], missing: [] };

/** The harness spec that drives the Jobs-To-Be-Done (R8.6's `job` category). */
const JOB_SPEC = "tests/e2e/task-completion.jtbd.spec.ts";

/** A resilience scenario that is NOT on the deferral list, so it is always in suite. */
const LIVE_RESILIENCE_SPEC = "tests/e2e/fault-transition.resilience.spec.ts";

/** The resilience scenario id used in a generated emission ledger. */
const RESILIENCE_SCENARIO = `${LIVE_RESILIENCE_SPEC} :: fault transition is contained`;

/** The real-stack fidelity comparison id used in a generated emission ledger. */
const FIDELITY_SCENARIO = "spec/effectiveness/real-stack-fidelity.ts :: harness-vs-real-stack";

/**
 * Every declared deferral's spec, plus one spec that is NOT declared deferred.
 *
 * Non-empty by construction, so facet 12 stays meaningful on the day `DEFERRED_SCENARIOS`
 * clears: the claim is that a `skipped` ledger entry is charged whether or not its subject
 * appears on the deferral list, and the non-deferred member keeps that claim falsifiable.
 */
const deferralSubjectArb: fc.Arbitrary<string> = fc.constantFrom<string>(
  ...DEFERRED_SCENARIOS.map((deferred) => deferred.spec),
  LIVE_RESILIENCE_SPEC,
);

/** One of R8.6's three named scenario categories. */
const scenarioKindArb = fc.constantFrom<ScenarioKind>("job", "resilience", "fidelity");

// ---------------------------------------------------------------------------
// Run construction
// ---------------------------------------------------------------------------

/** The ledger id a job scenario reports: its spec file plus its title. */
function jobScenarioId(job: JobToBeDone): string {
  return `${JOB_SPEC} :: ${job}`;
}

/**
 * A run's scenario ledger: one `kind: "job"` entry per EMITTED job — so a duplicated
 * emission duplicates its ledger entry too — plus the resilience scenario and the real-stack
 * fidelity comparison, the two of R8.6's three categories that live in sibling files the
 * emitter's own ledger would otherwise never see.
 */
function ledgerFor(opts: {
  readonly emitted: readonly JobToBeDone[];
  readonly skippedJobs: ReadonlySet<JobToBeDone>;
  readonly skipResilience: boolean;
  readonly skipFidelity: boolean;
}): readonly ScenarioRecord<JobToBeDone>[] {
  const jobs = opts.emitted.map((job): ScenarioRecord<JobToBeDone> => ({
    scenario: jobScenarioId(job),
    kind: "job",
    job,
    outcome: opts.skippedJobs.has(job) ? "skipped" : "executed",
  }));
  return [
    ...jobs,
    {
      scenario: RESILIENCE_SCENARIO,
      kind: "resilience",
      job: null,
      outcome: opts.skipResilience ? "skipped" : "executed",
    },
    {
      scenario: FIDELITY_SCENARIO,
      kind: "fidelity",
      job: null,
      outcome: opts.skipFidelity ? "skipped" : "executed",
    },
  ];
}

/**
 * The rows a run with this coverage offers: one row per emitted job, in emission order, so
 * the `duplicated` mode offers the repeated job's row twice and the `empty` mode offers none.
 */
function rowsFor(
  coverage: JobCoverage,
  stamped: readonly CapturedRow<JobToBeDone>[],
): readonly CapturedRow<JobToBeDone>[] {
  const byJob = new Map<JobToBeDone, CapturedRow<JobToBeDone>>();
  for (const row of stamped) byJob.set(row.job, row);
  const offered: CapturedRow<JobToBeDone>[] = [];
  for (const job of coverage.emitted) {
    const row = byJob.get(job);
    if (row !== undefined) offered.push(row);
  }
  return offered;
}

/** A fully-executed run whose only varied dimensions are its coverage and its reachability. */
function inputFor(opts: {
  readonly coverage: JobCoverage;
  readonly stamped: readonly CapturedRow<JobToBeDone>[];
  readonly harnessReachable: boolean;
}): EmissionInput<JobToBeDone> {
  return {
    declaredJobs: JOB_ORDER,
    harnessReachable: opts.harnessReachable,
    rows: rowsFor(opts.coverage, opts.stamped),
    scenarios: ledgerFor({
      emitted: opts.coverage.emitted,
      skippedJobs: new Set<JobToBeDone>(),
      skipResilience: false,
      skipFidelity: false,
    }),
    reportedCounts: null,
  };
}

// ---------------------------------------------------------------------------
// Verdict readers
// ---------------------------------------------------------------------------

function failuresOf(verdict: EmissionVerdict<JobToBeDone>): readonly EmissionFailure[] {
  return verdict.outcome === "failed" ? verdict.failures : [];
}

function kindsOf(failures: readonly EmissionFailure[]): readonly EmissionFailureKind[] {
  return failures.map((failure) => failure.kind);
}

function subjectsOf(
  failures: readonly EmissionFailure[],
  kind: EmissionFailureKind,
): readonly string[] {
  return failures.filter((failure) => failure.kind === kind).map((failure) => failure.subject);
}

function sortedKinds(failures: readonly EmissionFailure[]): readonly string[] {
  return [...kindsOf(failures)].sort();
}

// ---------------------------------------------------------------------------
// The emitted document
// ---------------------------------------------------------------------------

/** The shape a harness run writes, as `FreshScorecardSchema` validates it. */
interface EmittedDocument {
  readonly schemaVersion: number;
  readonly harnessVersion: string;
  readonly seed: number;
  readonly rows: readonly CapturedRow<JobToBeDone>[];
  readonly interruptionPrecision: number | null;
  readonly proxyCeiling: string;
  readonly harnessReachable: boolean;
  readonly executedScenarios: number;
  readonly skippedScenarios: number;
  readonly scenarios: readonly ScenarioRecord<JobToBeDone>[];
}

/**
 * Serializes a run as the document the gate re-reads. `reported` overrides the counts a
 * doctored artifact would claim; `null` reports the counts the ledger actually yields.
 */
function emitDocument(
  input: EmissionInput<JobToBeDone>,
  reported: { readonly executed: number; readonly skipped: number } | null,
): string {
  const executed = input.scenarios.filter((scenario) => scenario.outcome === "executed").length;
  const counted = reported ?? { executed, skipped: input.scenarios.length - executed };
  const document: EmittedDocument = {
    schemaVersion: SCORECARD_SCHEMA_VERSION,
    harnessVersion: EFFECTIVENESS_HARNESS_VERSION,
    seed: EFFECTIVENESS_HARNESS_SEED,
    rows: input.rows,
    interruptionPrecision: null,
    proxyCeiling: SCRIPTED_PROXY_CEILING,
    harnessReachable: input.harnessReachable,
    executedScenarios: counted.executed,
    skippedScenarios: counted.skipped,
    scenarios: input.scenarios,
  };
  return JSON.stringify(document);
}

// ---------------------------------------------------------------------------
// The Playwright harness run record
// ---------------------------------------------------------------------------

/** One spec as a generated Playwright run record reports it. */
interface RecordedSpec {
  readonly file: string;
  readonly title: string;
  readonly skipped: boolean;
}

/** A recorded spec plus the category R8.6 puts it in, for the classification assertion. */
interface CategorizedSpec extends RecordedSpec {
  readonly category: HarnessSpecCategory;
}

interface PwTestJson {
  readonly status: string;
}

interface PwSpecJson {
  readonly file: string;
  readonly title: string;
  readonly tests: readonly PwTestJson[];
}

interface PwSuiteJson {
  readonly file: string;
  readonly specs: readonly PwSpecJson[];
  readonly suites: readonly PwSuiteJson[];
}

interface PwRecordJson {
  readonly suites: readonly PwSuiteJson[];
}

/** A Playwright JSON run record reporting exactly these specs, in order. */
function harnessRecord(specs: readonly RecordedSpec[]): string {
  const record: PwRecordJson = {
    suites: specs.map((spec) => ({
      file: spec.file,
      specs: [
        {
          file: spec.file,
          title: spec.title,
          tests: [{ status: spec.skipped ? "skipped" : "expected" }],
        },
      ],
      suites: [],
    })),
  };
  return JSON.stringify(record);
}

/** A real harness spec file bound to the R8.6 category its filename puts it in. */
interface HarnessSpecFile {
  readonly file: string;
  readonly category: HarnessSpecCategory;
}

/** The harness suite's real spec files, covering all three of the gate's categories. */
const HARNESS_SPECS: readonly HarnessSpecFile[] = [
  { file: JOB_SPEC, category: "job" },
  { file: LIVE_RESILIENCE_SPEC, category: "resilience" },
  { file: "tests/e2e/firehose-stress.resilience.spec.ts", category: "resilience" },
  { file: "tests/e2e/scale-virtualization.resilience.spec.ts", category: "resilience" },
  { file: "tests/e2e/spatial-visualization.spec.ts", category: "other" },
  { file: "tests/e2e/a11y/assistive-tech-flow.spec.ts", category: "other" },
];

const recordedSpecArb: fc.Arbitrary<CategorizedSpec> = fc
  .tuple(
    fc.constantFrom<HarnessSpecFile>(...HARNESS_SPECS),
    fc.boolean(),
    fc.integer({ min: 1, max: 9 }),
  )
  .map(([spec, skipped, ordinal]): CategorizedSpec => ({
    file: spec.file,
    title: `scenario ${ordinal}`,
    category: spec.category,
    skipped,
  }));

// ---------------------------------------------------------------------------

describe("Property 32: the scorecard is complete or the job fails", () => {
  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("guards the input space is non-empty and reaches every JobCoverageKind", () => {
    // R8.1 names five jobs for five rows; the whole bijection claim is about this set.
    expect(JOB_ORDER.length).toBe(5);
    expect(new Set(JOB_ORDER).size).toBe(JOB_ORDER.length);

    // `jobCoverageArb` must actually reach all four modes, or every facet quantified over
    // it would be silently testing one branch.
    const reached = new Set<JobCoverageKind>();
    for (const coverage of fc.sample(jobCoverageArb, 400)) {
      reached.add(coverage.kind);
      if (coverage.kind === "complete") {
        expect(coverage.emitted.length).toBe(JOB_ORDER.length);
        expect(coverage.missing.length).toBe(0);
      }
      if (coverage.kind === "empty") {
        expect(coverage.emitted.length).toBe(0);
        expect(coverage.missing.length).toBe(JOB_ORDER.length);
      }
      if (coverage.kind === "missing") {
        expect(coverage.missing.length).toBeGreaterThan(0);
        expect(coverage.emitted.length).toBeLessThan(JOB_ORDER.length);
      }
      if (coverage.kind === "duplicated") {
        expect(coverage.emitted.length).toBe(JOB_ORDER.length + 1);
        expect(new Set(coverage.emitted).size).toBe(JOB_ORDER.length);
      }
    }
    expect([...reached].sort()).toEqual(["complete", "duplicated", "empty", "missing"]);

    // The accepting generator really does produce five fully stamped rows, so facet 2 is
    // capable of reaching `complete` rather than passing because nothing ever does.
    for (const rows of fc.sample(stampedRowsArb, 40)) {
      expect(rows.map((row) => row.job)).toEqual([...JOB_ORDER]);
      for (const row of rows) {
        expect(row.harnessVersion).not.toBeNull();
        expect(row.seed).not.toBeNull();
        expect(row.capturedAt).not.toBeNull();
      }
    }

    // ...and the row generator that MAY drop a stamp really does drop one, so facet 3's
    // `unstamped-row` claim cannot pass by never holing a stamp.
    const holed = fc
      .sample(capturedScorecardRowArb(), 200)
      .filter((row) => row.harnessVersion === null || row.seed === null || row.capturedAt === null);
    expect(holed.length).toBeGreaterThan(0);

    // The deferral list is a declaration with named blockers and an owner, not an exemption.
    for (const deferred of DEFERRED_SCENARIOS) {
      expect(deferred.spec.length).toBeGreaterThan(0);
      expect(deferred.blockers.length).toBeGreaterThan(0);
      expect(deferred.owner.length).toBeGreaterThan(0);
    }
    expect(fc.sample(deferralSubjectArb, 200)).toContain(LIVE_RESILIENCE_SPEC);
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("accepts a complete, fully-executed, stamped run and carries its capture metadata", () => {
    fc.assert(
      fc.property(stampedRowsArb, (stamped) => {
        const input = inputFor({ coverage: COMPLETE_COVERAGE, stamped, harnessReachable: true });
        const verdict = evaluateEmission(input);

        // The complement direction. A property that can only ever fail things proves nothing
        // about the rule, so a genuinely complete run must be ACCEPTED.
        expect(verdict.outcome).toBe("complete");
        if (verdict.outcome !== "complete") return;

        // R8.1: exactly one row per declared job, in declared order — five for five.
        expect(verdict.rows.map((row) => row.job)).toEqual([...JOB_ORDER]);
        // R8.2: the accepted rows are the offered rows, metrics AND capture stamps intact,
        // so every row's metrics carry the metadata of the run that emitted it.
        expect(verdict.rows).toEqual(input.rows);
        for (const row of verdict.rows) {
          expect(typeof row.harnessVersion).toBe("string");
          expect(typeof row.seed).toBe("number");
          expect(typeof row.capturedAt).toBe("string");
        }
        // R8.8: the counts partition the scenario set, and the run executed something.
        expect(verdict.counts.total).toBe(JOB_ORDER.length + 2);
        expect(verdict.counts.executed).toBe(verdict.counts.total);
        expect(verdict.counts.skipped).toBe(0);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("rejects a row that cannot name the run that captured it, naming the absent stamp", () => {
    fc.assert(
      fc.property(offeredRowsArb, (offered) => {
        const input: EmissionInput<JobToBeDone> = {
          declaredJobs: JOB_ORDER,
          harnessReachable: true,
          rows: offered,
          scenarios: ledgerFor({
            emitted: [...JOB_ORDER],
            skippedJobs: new Set<JobToBeDone>(),
            skipResilience: false,
            skipFidelity: false,
          }),
          reportedCounts: null,
        };
        const verdict = evaluateEmission(input);
        const holed = offered.filter(
          (row) => row.harnessVersion === null || row.seed === null || row.capturedAt === null,
        );

        // R8.2: acceptance tracks stamp presence exactly. The row COUNT is a bijection here
        // either way, so a shorter-but-accepted scorecard is not what is being rejected —
        // an unattributable measurement is.
        expect(verdict.outcome).toBe(holed.length === 0 ? "complete" : "failed");
        if (verdict.outcome !== "failed") return;

        const failures = failuresOf(verdict);
        // Isolation: the stamps are the only defect, so every failure is an unstamped row.
        expect(failures.every((failure) => failure.kind === "unstamped-row")).toBe(true);
        expect(subjectsOf(failures, "unstamped-row").length).toBe(holed.length);
        expect("rows" in verdict).toBe(false);

        for (const row of holed) {
          const named = failures.find((failure) => failure.subject === row.job);
          expect(named).toBeDefined();
          if (named === undefined) return;
          // The absent stamp is NAMED, so the failure is actionable rather than opaque.
          if (row.harnessVersion === null) expect(named.detail).toContain("harnessVersion");
          if (row.seed === null) expect(named.detail).toContain("seed");
          if (row.capturedAt === null) expect(named.detail).toContain("capturedAt");
        }
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("emits only on a bijection: a missing, duplicated, or empty job set is a failed result", () => {
    fc.assert(
      fc.property(jobCoverageArb, stampedRowsArb, (coverage, stamped) => {
        const verdict = evaluateEmission(inputFor({ coverage, stamped, harnessReachable: true }));

        if (coverage.kind === "complete") {
          expect(verdict.outcome).toBe("complete");
          if (verdict.outcome !== "complete") return;
          expect(verdict.rows.map((row) => row.job)).toEqual([...JOB_ORDER]);
          return;
        }

        // R8.1, R8.2, R8.3: anything other than a bijection FAILS, and the failed verdict
        // structurally carries no rows — there is no shorter-but-accepted scorecard.
        expect(verdict.outcome).toBe("failed");
        expect("rows" in verdict).toBe(false);

        const failures = failuresOf(verdict);
        if (coverage.kind === "duplicated") {
          expect(kindsOf(failures)).toContain("duplicate-job");
          return;
        }

        // R8.3: an absent declared job is NAMED, never skipped over. `empty` is the
        // `rows: []` artifact the audit found, and it names all five.
        expect(kindsOf(failures)).toContain("missing-job");
        const named = subjectsOf(failures, "missing-job");
        for (const job of coverage.missing) expect(named).toContain(job);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("rejects an empty declared job set: a vacuous bijection is not a satisfied one", () => {
    fc.assert(
      fc.property(stampedRowsArb, (stamped) => {
        const verdict = evaluateEmission<JobToBeDone>({
          declaredJobs: [],
          harnessReachable: true,
          rows: rowsFor(COMPLETE_COVERAGE, stamped),
          scenarios: ledgerFor({
            emitted: [...JOB_ORDER],
            skippedJobs: new Set<JobToBeDone>(),
            skipResilience: false,
            skipFidelity: false,
          }),
          reportedCounts: null,
        });

        // I-7: an unevaluable completeness rule reports a failure, not a pass.
        expect(verdict.outcome).toBe("failed");
        expect(kindsOf(failuresOf(verdict))).toContain("no-declared-jobs");
        expect("rows" in verdict).toBe(false);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("fails an unreachable harness: flipping reachability alone flips the verdict", () => {
    fc.assert(
      fc.property(stampedRowsArb, (stamped) => {
        const reachable = evaluateEmission(
          inputFor({ coverage: COMPLETE_COVERAGE, stamped, harnessReachable: true }),
        );
        const unreachable = evaluateEmission(
          inputFor({ coverage: COMPLETE_COVERAGE, stamped, harnessReachable: false }),
        );

        // R8.1, R8.2: the two runs differ in nothing but whether the harness was observed.
        expect(reachable.outcome).toBe("complete");
        expect(unreachable.outcome).toBe("failed");
        expect(kindsOf(failuresOf(unreachable))).toEqual(["harness-unreachable"]);
        expect("rows" in unreachable).toBe(false);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("partitions scenarios into executed and skipped, and fails on zero executed or any skip", () => {
    fc.assert(
      fc.property(
        stampedRowsArb,
        jobSetArb(),
        fc.boolean(),
        fc.boolean(),
        (stamped, skippedJobs, skipResilience, skipFidelity) => {
          const skipped = new Set<JobToBeDone>(skippedJobs);
          const input: EmissionInput<JobToBeDone> = {
            declaredJobs: JOB_ORDER,
            harnessReachable: true,
            rows: rowsFor(COMPLETE_COVERAGE, stamped),
            scenarios: ledgerFor({
              emitted: [...JOB_ORDER],
              skippedJobs: skipped,
              skipResilience,
              skipFidelity,
            }),
            reportedCounts: null,
          };
          const verdict = evaluateEmission(input);
          const expectedSkips = skipped.size + (skipResilience ? 1 : 0) + (skipFidelity ? 1 : 0);

          // R8.8: `executed` and `skipped` PARTITION the scenario set — no third state.
          expect(verdict.counts.total).toBe(JOB_ORDER.length + 2);
          expect(verdict.counts.executed + verdict.counts.skipped).toBe(verdict.counts.total);
          expect(verdict.counts.skipped).toBe(expectedSkips);

          if (expectedSkips === 0) {
            expect(verdict.outcome).toBe("complete");
            return;
          }

          // R8.6: every skip is charged, exactly once, and never as informational.
          expect(verdict.outcome).toBe("failed");
          const failures = failuresOf(verdict);
          expect(subjectsOf(failures, "skipped-scenario").length).toBe(expectedSkips);
          // R8.8: an all-skipped run executed nothing, so it measured nothing.
          expect(kindsOf(failures).includes("zero-executed")).toBe(verdict.counts.executed === 0);
          expect("rows" in verdict).toBe(false);
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("charges a skipped job, resilience, or fidelity scenario in isolation, naming it", () => {
    fc.assert(
      fc.property(stampedRowsArb, scenarioKindArb, jobArb, (stamped, kind, job) => {
        const input: EmissionInput<JobToBeDone> = {
          declaredJobs: JOB_ORDER,
          harnessReachable: true,
          rows: rowsFor(COMPLETE_COVERAGE, stamped),
          scenarios: ledgerFor({
            emitted: [...JOB_ORDER],
            skippedJobs: kind === "job" ? new Set<JobToBeDone>([job]) : new Set<JobToBeDone>(),
            skipResilience: kind === "resilience",
            skipFidelity: kind === "fidelity",
          }),
          reportedCounts: null,
        };
        const verdict = evaluateEmission(input);
        const failures = failuresOf(verdict);

        // R8.6 names exactly these three categories, and each one alone is enough to fail.
        expect(verdict.outcome).toBe("failed");
        // Isolation: coverage, stamps, reachability and counts are all intact, so the skip
        // is the ONLY defect and the failure is attributable to it.
        expect(kindsOf(failures)).toEqual(["skipped-scenario"]);

        const expectedSubject =
          kind === "job"
            ? jobScenarioId(job)
            : kind === "resilience"
              ? RESILIENCE_SCENARIO
              : FIDELITY_SCENARIO;
        expect(subjectsOf(failures, "skipped-scenario")).toEqual([expectedSubject]);
        for (const failure of failures) expect(failure.detail).toContain(kind);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("re-decides an emitted document against the real JOB_ORDER and reaches the same verdict", () => {
    fc.assert(
      fc.property(
        jobCoverageArb,
        stampedRowsArb,
        fc.boolean(),
        (coverage, stamped, harnessReachable) => {
          const input = inputFor({ coverage, stamped, harnessReachable });
          const atEmission = evaluateEmission(input);
          const atGate = checkFreshScorecard(emitDocument(input, null));

          // The document is a valid emitted record, so any failure below is SEMANTIC.
          expect(atGate.document).not.toBeNull();

          // R8.3: the gate binds the same rule to the single source of truth for the job
          // set, so one run cannot be complete at emission and complete-by-omission here.
          expect(atGate.verdict.outcome).toBe(atEmission.outcome);
          expect(sortedKinds(failuresOf(atGate.verdict))).toEqual(
            sortedKinds(failuresOf(atEmission)),
          );

          const acceptable = coverage.kind === "complete" && harnessReachable;
          expect(atGate.verdict.outcome).toBe(acceptable ? "complete" : "failed");
        },
      ),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("re-derives reported counts from the ledger: a doctored count is a named failure", () => {
    fc.assert(
      fc.property(stampedRowsArb, fc.integer({ min: 1, max: 9 }), (stamped, inflation) => {
        const input = inputFor({ coverage: COMPLETE_COVERAGE, stamped, harnessReachable: true });
        const honestExecuted = input.scenarios.length;
        const doctored = emitDocument(input, {
          executed: honestExecuted + inflation,
          skipped: 0,
        });

        // R8.8: the emitted scorecard REPORTS the counts, so the gate must not trust them.
        // The same run with honest counts is accepted (facet 9), which is what makes the
        // count the sole difference here.
        const atGate = checkFreshScorecard(doctored);
        expect(atGate.verdict.outcome).toBe("failed");
        expect(kindsOf(failuresOf(atGate.verdict))).toEqual(["count-mismatch"]);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("charges a harness run that selected nothing, ran nothing, or skipped a named scenario", () => {
    fc.assert(
      fc.property(fc.array(recordedSpecArb, { minLength: 0, maxLength: 6 }), (specs) => {
        const outcomes = scanHarnessRunRecord(harnessRecord(specs));
        expect(outcomes.length).toBe(specs.length);

        // The gate's own classifier agrees with R8.6's categories for every real spec file.
        for (const [index, spec] of specs.entries()) {
          const outcome = outcomes[index];
          expect(outcome).toBeDefined();
          if (outcome === undefined) return;
          expect(outcome.file).toBe(spec.file);
          expect(outcome.category).toBe(spec.category);
          expect(outcome.outcome).toBe(spec.skipped ? "skipped" : "executed");
        }

        const review = reviewHarnessRunRecord(outcomes);

        // R8.8: a suite that selected nothing runnable, or ran nothing, executed nothing.
        const anyExecuted = specs.some((spec) => !spec.skipped);
        expect(kindsOf(review.failures).includes("zero-executed")).toBe(!anyExecuted);

        // R8.6: every skipped job or resilience scenario is charged, and named.
        const charged = specs.filter((spec) => spec.skipped && spec.category !== "other");
        const subjects = subjectsOf(review.failures, "skipped-scenario");
        expect(subjects.length).toBe(charged.length);
        for (const spec of charged) {
          expect(subjects.some((subject) => subject.includes(spec.file))).toBe(true);
        }

        // A skip outside R8.6's three named categories is REPORTED, not charged: inventing
        // an obligation the criterion never took on would make this gate less credible.
        const unnamed = specs.filter((spec) => spec.skipped && spec.category === "other");
        expect(review.unnamedSkips.length).toBe(unnamed.length);
        expect(
          review.failures.every(
            (failure) =>
              failure.kind === "zero-executed" || failure.kind === "skipped-scenario",
          ),
        ).toBe(true);
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("does not treat a declared deferral as a skip: it is absent from the run's partition", () => {
    fc.assert(
      fc.property(stampedRowsArb, (stamped) => {
        const input = inputFor({ coverage: COMPLETE_COVERAGE, stamped, harnessReachable: true });

        // A DEFERRED scenario is excluded from HARNESS_SPEC_PATTERN, so it is absent from
        // the suite rather than skipped inside it, and it does not join the partition.
        const ledgerIds = input.scenarios.map((scenario) => scenario.scenario);
        for (const deferred of DEFERRED_SCENARIOS) {
          expect(ledgerIds.some((id) => id.includes(deferred.spec))).toBe(false);
        }

        // So a complete run stays complete: the deferral is an outstanding divergence the
        // ratchet prints, not a defect this rule invents against the run that did measure.
        expect(evaluateEmission(input).outcome).toBe("complete");
      }),
    );
  });

  // Feature: purpose-achievement-audit, Property 32: The scorecard is complete or the job fails
  it("does not let a deferral launder a skip: a skipped ledger entry is charged regardless", () => {
    fc.assert(
      fc.property(
        stampedRowsArb,
        deferralSubjectArb,
        fc.constantFrom<ScenarioKind>("resilience", "fidelity"),
        (stamped, spec, kind) => {
          const base = inputFor({ coverage: COMPLETE_COVERAGE, stamped, harnessReachable: true });
          const input: EmissionInput<JobToBeDone> = {
            ...base,
            scenarios: [
              ...base.scenarios,
              { scenario: spec, kind, job: null, outcome: "skipped" },
            ],
          };
          const verdict = evaluateEmission(input);
          const failures = failuresOf(verdict);

          // R8.6: appearing on the deferral list buys no exemption. Once a scenario is IN
          // the ledger reporting `skipped`, it is a divergence like any other.
          expect(verdict.outcome).toBe("failed");
          expect(kindsOf(failures)).toEqual(["skipped-scenario"]);
          expect(subjectsOf(failures, "skipped-scenario")).toEqual([spec]);

          // Same claim on the other side of the gate: a deferred spec that the Playwright
          // record reports skipped is charged when it falls in one of R8.6's categories.
          const outcomes = scanHarnessRunRecord(
            harnessRecord([
              { file: JOB_SPEC, title: "every job", skipped: false },
              { file: spec, title: "deferred scenario", skipped: true },
            ]),
          );
          const recorded = outcomes.find((outcome) => outcome.file === spec);
          expect(recorded).toBeDefined();
          if (recorded === undefined) return;
          const review = reviewHarnessRunRecord(outcomes);
          if (recorded.category === "other") {
            expect(review.unnamedSkips.map((outcome) => outcome.file)).toContain(spec);
          } else {
            expect(
              subjectsOf(review.failures, "skipped-scenario").some((subject) =>
                subject.includes(spec),
              ),
            ).toBe(true);
          }
        },
      ),
    );
  });
});
