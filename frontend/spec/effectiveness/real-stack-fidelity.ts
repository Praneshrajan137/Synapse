/**
 * Real_Stack_Run — fidelity divergence reporter (Req 5.1–5.5, 20.3).
 *
 * The nightly Real_Stack_Run (`.github/workflows/integration.yml`, on cron)
 * boots the real SYNAPSE docker stack (gateway/nginx + orchestrator +
 * datastores) and runs the IDENTICAL Task_Completion_Test suite
 * (`tests/e2e/task-completion.jtbd.spec.ts`) against it with the MSW browser
 * worker DISABLED — the suite drives the real gateway (PLAYWRIGHT_BASE_URL),
 * so no fixture is served. This script reads:
 *
 *   1. the committed harness baseline scorecard
 *      (`spec/effectiveness/scorecard.baseline.json`) — the set of Jobs-To-Be-
 *      Done that are GREEN under the deterministic Effectiveness_Harness; and
 *   2. the Playwright JSON results the real-stack run emitted;
 *
 * and reports any Job_To_Be_Done that PASSES under the harness but FAILS
 * against the real stack (Req 5.2). For each such divergence it names:
 *
 *   • the job (the failing Task_Completion_Test),
 *   • the observed contract difference (the real-stack failure message), and
 *   • the MSW_Fixture(s) requiring reconciliation (the scenario's seed schema
 *     ids — the fixtures the harness serves for that job) (Req 5.4).
 *
 * It records the backend build SHA the stack ran against (Req 5.5, from
 * `$BACKEND_BUILD_SHA`, falling back to `$GITHUB_SHA`) so a fidelity divergence
 * is traceable to a backend version, and writes a machine- and human-readable
 * report. It exits NON-ZERO when ANY declared fidelity comparison did not come
 * back comparable-and-green, so the (nightly, PR-gate-separate) job goes red and
 * is actionable. This run is entirely separate from the deterministic PR gate so
 * real-stack latency/nondeterminism can never make the PR gate flaky (Req 5.3,
 * 20.3).
 *
 * ── The removed rule (purpose-achievement-audit R8.6, task 11.2) ──────────────
 * This file used to carry: "a real-stack SKIP is informational (not comparable),
 * never a divergence." That rule is REMOVED, and its removal is the fix rather
 * than a side effect. It was the reason the nightly Real_Stack_Run was green:
 * every Task_Completion_Test skipped on its first line, every comparison was
 * therefore "not comparable", and a job that compared nothing reported no
 * divergence. R8.6 is explicit -- "IF a Job_To_Be_Done, a resilience scenario, or
 * a real-stack fidelity comparison is skipped, THEN THE effectiveness job SHALL
 * record that skip as a divergence and SHALL NOT record it as informational or as
 * a pass" -- and `CLAUDE.md` is explicit: a SKIP is not a PASS, absence of proof
 * is never a pass (I-7).
 *
 * So a comparison that did not happen is now a first-class divergence with its own
 * {@link DivergenceKind}, named in the report and counted toward the non-zero exit:
 *
 *   * `real-stack-failure`    -- green under the harness, failed against the real
 *     stack. The original, genuine fidelity divergence (Req 5.2).
 *   * `skipped-comparison`    -- the real-stack spec reported skipped. Formerly
 *     "informational"; now a divergence (R8.6).
 *   * `missing-comparison`    -- the real-stack results contain no spec for this
 *     job at all, so the comparison was never attempted. Structurally the same
 *     absence of evidence, and treated the same.
 *   * `uncomparable-baseline` -- the job is not green under the harness, so there
 *     is no harness verdict to compare the real stack against. Unevaluable is not
 *     a pass.
 *
 * Run (from `frontend/`): `pnpm effectiveness:real-stack-fidelity` — or
 *   `tsx spec/effectiveness/real-stack-fidelity.ts [playwrightResultsPath]`.
 *
 * NOTE: the Job_To_Be_Done ↔ title/fixture mapping is kept LOCAL here (mirroring
 * `spec/effectiveness/scenarios/*` and the `JTBD_CASES` in the e2e spec) so this
 * reporter stays free of the app's `@`-alias module graph and runs under plain
 * `tsx` with zero app dependencies — the same convention the sibling e2e specs
 * follow. The five jobs and their seed-schema fixtures are asserted to match the
 * committed baseline's job set at run time, so a drift between this map and the
 * scenarios/baseline fails loudly rather than silently mis-reporting.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** The `frontend/` root: this file lives at `frontend/spec/effectiveness/`. */
const FRONTEND_ROOT = fileURLToPath(new URL("../../", import.meta.url));

/** Committed harness baseline (the jobs GREEN under the deterministic harness). */
const BASELINE_RELPATH = "spec/effectiveness/scorecard.baseline.json";
/** Default Playwright JSON results the real-stack run emits (gitignored). */
const DEFAULT_RESULTS_RELPATH = "test-results/real-stack/results.json";
/** Where this reporter writes its fidelity report (gitignored). */
const REPORT_JSON_RELPATH = "test-results/real-stack/fidelity-report.json";
const REPORT_MD_RELPATH = "test-results/real-stack/fidelity-report.md";

/**
 * A Job_To_Be_Done bound to its e2e test title and the MSW_Fixture schema ids
 * the harness serves for it. MIRRORS `spec/effectiveness/scenarios/*` and the
 * `JTBD_CASES` local mirror in `tests/e2e/task-completion.jtbd.spec.ts`; the
 * `titlePrefix` is the leading `${jtbd.title}` of that spec's test title
 * (`"<title> reaches the correct terminal outcome with no dead-ends"`).
 */
interface JtbdFixtureBinding {
  readonly job: string;
  readonly titlePrefix: string;
  /** The MSW_Fixture(s) (seed Domain_Schema ids) the harness serves for this job. */
  readonly fixtures: readonly string[];
}

const JTBD_FIXTURES: readonly JtbdFixtureBinding[] = [
  {
    job: "resolve-escalation-correctly",
    titlePrefix: "Resolve an escalation correctly",
    fixtures: ["EscalationMessage", "DecisionEnvelope", "OverrideApiResponse", "AuditListResponse"],
  },
  {
    job: "identify-degraded-agent",
    titlePrefix: "Identify which agent degraded and why",
    fixtures: ["AgentHealthResponse", "SystemPosture"],
  },
  {
    job: "reconstruct-decision-rationale",
    titlePrefix: "Reconstruct a decision's rationale",
    fixtures: ["DecisionDetailResponse", "ConsensusDecision", "DecisionEnvelope"],
  },
  {
    job: "adjust-steering-safely",
    titlePrefix: "Adjust steering safely",
    fixtures: ["SteeringResponse"],
  },
  {
    job: "catch-disruption-before-cascade",
    titlePrefix: "Catch a disruption before it cascades",
    fixtures: ["DisruptionAlert", "RoutePlan"],
  },
];

/** The comparable outcome of a Task_Completion_Test against the real stack. */
type RealStackOutcome = "passed" | "failed" | "skipped" | "missing";

interface JobResult {
  readonly outcome: RealStackOutcome;
  /** The observed contract difference (real-stack failure message), when failed. */
  readonly detail: string;
}

/**
 * Why a declared fidelity comparison did not come back comparable-and-green. See the
 * file header for what each value means and why `skipped-comparison` exists at all
 * (purpose-achievement-audit R8.6).
 */
type DivergenceKind =
  | "real-stack-failure"
  | "skipped-comparison"
  | "missing-comparison"
  | "uncomparable-baseline";

/** A named fidelity divergence (Req 5.2, 5.4; R8.6). */
interface Divergence {
  readonly kind: DivergenceKind;
  readonly job: string;
  readonly title: string;
  /**
   * The observed contract difference for `real-stack-failure`; for every other kind,
   * a statement of what was not compared and why. Never blank: a divergence that
   * cannot say what it observed is not actionable.
   */
  readonly contractDifference: string;
  readonly fixturesToReconcile: readonly string[];
}

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// ── Playwright JSON walking ──────────────────────────────────────────────────
//
// The Playwright JSON reporter nests specs under (optionally nested) suites.
// We only need each spec's title and a collapsed pass/fail/skip outcome plus any
// failure message, so we walk defensively over an `unknown`-typed tree.

interface PwSpecView {
  readonly title: string;
  readonly outcome: RealStackOutcome;
  readonly detail: string;
}

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

/** Collapse a spec's tests/results into one outcome + a failure detail string. */
function collapseSpec(spec: Record<string, unknown>): PwSpecView {
  const title = typeof spec.title === "string" ? spec.title : "";
  const tests = asArray(spec.tests);

  let anyFailed = false;
  let anyPassed = false;
  let allSkipped = tests.length > 0;
  const details: string[] = [];

  for (const t of tests) {
    const test = asRecord(t);
    const status = typeof test.status === "string" ? test.status : "";
    if (status !== "skipped") allSkipped = false;
    if (status === "unexpected" || status === "flaky") anyFailed = true;
    if (status === "expected") anyPassed = true;

    for (const r of asArray(test.results)) {
      const result = asRecord(r);
      const rStatus = typeof result.status === "string" ? result.status : "";
      if (rStatus === "failed" || rStatus === "timedOut" || rStatus === "interrupted") {
        anyFailed = true;
      }
      const err = asRecord(result.error);
      if (typeof err.message === "string" && err.message.trim()) {
        details.push(err.message.trim());
      }
      for (const e of asArray(result.errors)) {
        const errItem = asRecord(e);
        if (typeof errItem.message === "string" && errItem.message.trim()) {
          details.push(errItem.message.trim());
        }
      }
    }
  }

  const outcome: RealStackOutcome = anyFailed
    ? "failed"
    : allSkipped
      ? "skipped"
      : anyPassed
        ? "passed"
        : "skipped";

  return { title, outcome, detail: details.join("\n") };
}

/** Recursively collect every spec view from the Playwright JSON report tree. */
function collectSpecs(node: unknown, out: PwSpecView[]): void {
  const rec = asRecord(node);
  for (const s of asArray(rec.specs)) {
    out.push(collapseSpec(asRecord(s)));
  }
  for (const child of asArray(rec.suites)) {
    collectSpecs(child, out);
  }
}

/** First non-empty line of a failure message — a compact "contract difference". */
function firstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim().length > 0);
  return (line ?? text).trim();
}

// ── Loading ──────────────────────────────────────────────────────────────────

function loadBaselineJobs(path: string): Set<string> {
  let raw: string;
  try {
    raw = readFileSync(path, "utf8");
  } catch (err) {
    throw new Error(`Harness baseline scorecard not found at ${path}: ${describeError(err)}`);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`Harness baseline scorecard at ${path} is malformed: ${describeError(err)}`);
  }
  const rows = asArray(asRecord(parsed).rows);
  // A job is "green under the harness" when its baseline row records no
  // error/dead-end (errorRate === 0) — the only jobs whose real-stack failure is
  // a genuine fidelity divergence rather than a known-red job.
  const green = new Set<string>();
  for (const r of rows) {
    const row = asRecord(r);
    if (typeof row.job === "string" && row.errorRate === 0) green.add(row.job);
  }
  return green;
}

function loadResultsSpecs(path: string): PwSpecView[] {
  let raw: string;
  try {
    raw = readFileSync(path, "utf8");
  } catch (err) {
    throw new Error(
      `Real-stack Playwright results not found at ${path} — the real-stack run must emit a ` +
        `JSON report (PLAYWRIGHT_JSON_OUTPUT_NAME) before fidelity can be assessed: ${describeError(err)}`,
    );
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`Real-stack Playwright results at ${path} are malformed: ${describeError(err)}`);
  }
  const specs: PwSpecView[] = [];
  collectSpecs(parsed, specs);
  return specs;
}

/** Match a Job_To_Be_Done to its real-stack spec outcome by title prefix. */
function resolveJobResult(binding: JtbdFixtureBinding, specs: readonly PwSpecView[]): JobResult {
  const match = specs.find((s) => s.title.startsWith(binding.titlePrefix));
  if (!match) return { outcome: "missing", detail: "" };
  return { outcome: match.outcome, detail: match.detail };
}

/**
 * Classifies one declared fidelity comparison, returning `null` only when the
 * comparison actually happened and the real stack agreed with the harness.
 *
 * Total over `RealStackOutcome` x `harnessGreen`, so there is no combination that falls
 * through to an implicit pass -- which is precisely how the removed
 * "SKIP is informational" rule worked (R8.6, I-7).
 */
function classifyComparison(
  binding: JtbdFixtureBinding,
  harnessGreen: boolean,
  outcome: RealStackOutcome,
  detail: string,
): Divergence | null {
  const base = {
    job: binding.job,
    title: binding.titlePrefix,
    fixturesToReconcile: binding.fixtures,
  };
  if (!harnessGreen) {
    return {
      ...base,
      kind: "uncomparable-baseline",
      contractDifference:
        "the committed harness baseline records no green row for this job, so the real-stack " +
        "outcome has no harness verdict to be compared against; unevaluable is not a pass",
    };
  }
  if (outcome === "failed") {
    return {
      ...base,
      kind: "real-stack-failure",
      contractDifference: detail
        ? firstLine(detail)
        : "real-stack test failed (no message captured)",
    };
  }
  if (outcome === "skipped") {
    return {
      ...base,
      kind: "skipped-comparison",
      contractDifference:
        "the real-stack run reported this Task_Completion_Test as skipped, so the fidelity " +
        "comparison did not happen; a skip is recorded as a divergence, never as " +
        "informational and never as a pass (R8.6)",
    };
  }
  if (outcome === "missing") {
    return {
      ...base,
      kind: "missing-comparison",
      contractDifference:
        "the real-stack Playwright results contain no spec whose title starts with " +
        `"${binding.titlePrefix}", so the fidelity comparison was never attempted`,
    };
  }
  return null;
}

// ── Report rendering ──────────────────────────────────────────────────────────

interface FidelityReport {
  readonly kind: "real-stack-fidelity";
  readonly backendBuildSha: string;
  readonly orchestratorImage: string;
  readonly generatedAt: string;
  readonly resultsPath: string;
  readonly jobs: ReadonlyArray<{
    readonly job: string;
    readonly title: string;
    readonly harnessGreen: boolean;
    readonly realStackOutcome: RealStackOutcome;
    readonly fixtures: readonly string[];
  }>;
  readonly divergences: readonly Divergence[];
}

function renderMarkdown(report: FidelityReport): string {
  const lines: string[] = [];
  lines.push("# Real_Stack_Run — Fidelity Report");
  lines.push("");
  lines.push(`- Backend build SHA: \`${report.backendBuildSha}\` (Req 5.5)`);
  lines.push(`- Orchestrator image: \`${report.orchestratorImage}\``);
  lines.push(`- Generated: ${report.generatedAt}`);
  lines.push(`- Real-stack Playwright results: \`${report.resultsPath}\``);
  lines.push("");
  lines.push(
    "This run executes the identical Task_Completion_Test suite against the real " +
      "SYNAPSE docker stack with the MSW worker disabled (Req 5.1). It is separate " +
      "from the deterministic PR gate so real-stack latency/nondeterminism can never " +
      "make the PR gate flaky (Req 5.3, 20.3).",
  );
  lines.push("");
  lines.push("## Per-job fidelity");
  lines.push("");
  lines.push("| Job_To_Be_Done | Harness | Real stack | MSW_Fixtures |");
  lines.push("| --- | --- | --- | --- |");
  for (const j of report.jobs) {
    lines.push(
      `| ${j.title} | ${j.harnessGreen ? "green" : "not-green"} | ${j.realStackOutcome} | ${j.fixtures.join(", ")} |`,
    );
  }
  lines.push("");

  if (report.divergences.length === 0) {
    lines.push(
      "## Divergences\n\nNone — every declared fidelity comparison was made, and no " +
        "Job_To_Be_Done that passes under the harness failed against the real stack. " +
        "Harness fixtures remain faithful to real backend behavior at backend build " +
        `\`${report.backendBuildSha}\`.`,
    );
    return `${lines.join("\n")}\n`;
  }

  lines.push(
    `## Divergences (${report.divergences.length}) — a comparison that failed OR did not ` +
      "happen (Req 5.2, 5.4; R8.6)",
  );
  lines.push("");
  for (const d of report.divergences) {
    lines.push(`### ${d.title} (\`${d.job}\`) — \`${d.kind}\``);
    lines.push("");
    lines.push(`- Observed contract difference: ${d.contractDifference}`);
    lines.push(
      `- MSW_Fixture(s) requiring reconciliation: ${d.fixturesToReconcile.map((f) => `\`${f}\``).join(", ")}`,
    );
    lines.push(`- Traceable to backend build SHA: \`${report.backendBuildSha}\``);
    lines.push("");
  }
  return `${lines.join("\n")}\n`;
}

function main(): void {
  const resultsPath =
    process.argv[2] ??
    process.env.REAL_STACK_RESULTS ??
    join(FRONTEND_ROOT, DEFAULT_RESULTS_RELPATH);
  const baselinePath = join(FRONTEND_ROOT, BASELINE_RELPATH);

  const backendBuildSha =
    process.env.BACKEND_BUILD_SHA ?? process.env.GITHUB_SHA ?? "unknown";
  const orchestratorImage = process.env.ORCHESTRATOR_IMAGE ?? "unknown";

  const harnessGreenJobs = loadBaselineJobs(baselinePath);

  // Guard: this reporter's local job map must match the baseline's job set, so a
  // drift between the map and the scenarios/baseline fails loudly (never silently
  // mis-reports fidelity).
  const mappedJobs = new Set(JTBD_FIXTURES.map((b) => b.job));
  const missingFromMap = [...harnessGreenJobs].filter((j) => !mappedJobs.has(j));
  if (missingFromMap.length > 0) {
    throw new Error(
      `Fidelity reporter job map is out of sync with the baseline — unmapped green job(s): ` +
        `${missingFromMap.join(", ")}. Update JTBD_FIXTURES to mirror scenarios/*.`,
    );
  }

  const specs = loadResultsSpecs(resultsPath);

  const jobs: FidelityReport["jobs"] = [];
  const divergences: Divergence[] = [];

  for (const binding of JTBD_FIXTURES) {
    const harnessGreen = harnessGreenJobs.has(binding.job);
    const { outcome, detail } = resolveJobResult(binding, specs);
    jobs.push({
      job: binding.job,
      title: binding.titlePrefix,
      harnessGreen,
      realStackOutcome: outcome,
      fixtures: binding.fixtures,
    });

    // R8.6: every declared comparison must come back comparable AND green. A skip, an
    // absent spec, and a non-green harness row are all divergences now -- the
    // "a real-stack SKIP is informational" rule this file used to carry is what kept
    // the nightly green while nothing was ever compared.
    const divergence = classifyComparison(binding, harnessGreen, outcome, detail);
    if (divergence !== null) divergences.push(divergence);
  }

  const report: FidelityReport = {
    kind: "real-stack-fidelity",
    backendBuildSha,
    orchestratorImage,
    generatedAt: new Date().toISOString(),
    resultsPath,
    jobs,
    divergences,
  };

  const jsonOut = join(FRONTEND_ROOT, REPORT_JSON_RELPATH);
  const mdOut = join(FRONTEND_ROOT, REPORT_MD_RELPATH);
  mkdirSync(dirname(jsonOut), { recursive: true });
  writeFileSync(jsonOut, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  writeFileSync(mdOut, renderMarkdown(report), "utf8");

  process.stdout.write(renderMarkdown(report));

  if (divergences.length > 0) {
    const byKind = divergences.reduce<Record<string, number>>((tally, d) => {
      tally[d.kind] = (tally[d.kind] ?? 0) + 1;
      return tally;
    }, {});
    const summary = Object.keys(byKind)
      .sort()
      .map((kind) => `${kind}=${byKind[kind] ?? 0}`)
      .join(", ");
    process.stderr.write(
      `\nReal_Stack_Run: ${divergences.length} fidelity divergence(s) (${summary}) — see ` +
        `${REPORT_MD_RELPATH}. A comparison that was skipped or never attempted is a ` +
        "divergence, not an informational note on a pass (R8.6, I-7).\n",
    );
    process.exitCode = 1;
  } else {
    process.stdout.write("\nReal_Stack_Run: no fidelity divergence.\n");
  }
}

const isDirectRun =
  process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1];

if (isDirectRun) {
  try {
    main();
  } catch (err) {
    process.stderr.write(`\nReal_Stack_Run fidelity reporter crashed: ${describeError(err)}\n`);
    process.exitCode = 1;
  }
}
