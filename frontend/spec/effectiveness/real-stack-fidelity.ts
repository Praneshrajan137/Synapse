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
 * report. It exits NON-ZERO when a genuine harness-pass / real-stack-fail
 * divergence exists so the (nightly, PR-gate-separate) job goes red and is
 * actionable; a real-stack SKIP is informational (not comparable), never a
 * divergence — this run is entirely separate from the deterministic PR gate so
 * real-stack latency/nondeterminism can never make the PR gate flaky (Req 5.3,
 * 20.3).
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

/** A named harness-pass / real-stack-fail divergence (Req 5.2, 5.4). */
interface Divergence {
  readonly job: string;
  readonly title: string;
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
      "## Divergences\n\nNone — no Job_To_Be_Done that passes under the harness failed " +
        "against the real stack. Harness fixtures remain faithful to real backend behavior " +
        `at backend build \`${report.backendBuildSha}\`.`,
    );
    return `${lines.join("\n")}\n`;
  }

  lines.push(
    `## Divergences (${report.divergences.length}) — harness-pass / real-stack-fail (Req 5.2, 5.4)`,
  );
  lines.push("");
  for (const d of report.divergences) {
    lines.push(`### ${d.title} (\`${d.job}\`)`);
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

    // Divergence = green under the harness AND failed against the real stack.
    // A real-stack SKIP is informational (not comparable), never a divergence.
    if (harnessGreen && outcome === "failed") {
      divergences.push({
        job: binding.job,
        title: binding.titlePrefix,
        contractDifference: detail ? firstLine(detail) : "real-stack test failed (no message captured)",
        fixturesToReconcile: binding.fixtures,
      });
    }
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
    process.stderr.write(
      `\nReal_Stack_Run: ${divergences.length} fidelity divergence(s) — see ${REPORT_MD_RELPATH}.\n`,
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
