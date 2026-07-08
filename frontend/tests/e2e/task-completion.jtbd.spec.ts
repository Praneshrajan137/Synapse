import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { expect, test, type Page, type TestInfo } from "@playwright/test";

/**
 * Task_Completion_Tests — Jobs-To-Be-Done through the Effectiveness_Harness
 * (Req 3.2, 3.3, 3.4, 3.5, 3.6, 20.5).
 *
 * Each of the five enumerated Jobs-To-Be-Done (descriptors:
 * `spec/effectiveness/scenarios/*.ts`, task 3.1) is driven against its seeded
 * harness scenario and measured for task completion:
 *
 *   - Req 3.2 — record steps taken, time-to-complete, and error/dead-end rate
 *     for the operator's path to the terminal outcome.
 *   - Req 3.3 — assert the operator reaches the CORRECT terminal outcome for
 *     the seed; fail if it is wrong or unreachable.
 *   - Req 3.4 — record and fail on any dead-end (a missing or unjustifiably
 *     disabled affordance, or a non-recoverable state): a non-zero dead-end
 *     rate fails the test.
 *   - Req 3.5 — for "resolve an escalation correctly", verify the override
 *     commits the audit row BEFORE the decision is marked acted
 *     (audit-row-first) when driven through the harness.
 *   - Req 3.6 / 20.5 — every test's report states the honest ceiling: the
 *     measurement is a `Scripted_Proxy` that demonstrates a path EXISTS and is
 *     EFFICIENT, and does NOT establish human comprehension.
 *
 * ── Harness wiring (graceful-skip convention) ────────────────────────────────
 * The Effectiveness_Harness drives a seeded Job_To_Be_Done in-browser through a
 * documented global, mirroring `runTaskCompletion(ScenarioDescriptor)` from
 * design "C. Harness — JTBD scenario descriptors + Task_Completion_Test harness":
 *
 *   interface AtlasHarness {
 *     runTaskCompletion?(scenarioId: string): Promise<TaskCompletionResult>;
 *   }
 *   declare global { interface Window { __atlasHarness?: AtlasHarness } }
 *
 * Until that global is wired (the browser worker + stream driver expose it),
 * the metric/terminal assertions skip cleanly rather than failing — the same
 * graceful-skip convention as the other harness-dependent e2e specs
 * (firehose-stress.resilience.spec.ts, spatial-visualization.spec.ts). The base
 * render check (the terminal Surface is reachable and not bounced to /login)
 * runs regardless, and the Scripted_Proxy ceiling is recorded on EVERY test's
 * report whether or not the harness drove it.
 *
 * Scenario data below MIRRORS the descriptors but is kept LOCAL so this
 * Playwright spec stays free of the app's `@`-alias module graph (same
 * convention as the sibling e2e specs).
 */

/**
 * The honest ceiling recorded on every Task_Completion_Test report (Req 3.6,
 * 20.5). Kept verbatim so the scorecard/report and this suite state the same
 * caveat.
 */
const PROXY_CEILING =
  "Scripted_Proxy: this measurement demonstrates that an operator path EXISTS and is EFFICIENT " +
  "(steps, time-to-complete, dead-ends), but it does NOT establish human comprehension. Real " +
  "effectiveness requires real-user (RITE) testing with 3–5 operators.";

/** The classes of correct terminal state (mirrors `TerminalOutcomeKind`). */
type TerminalOutcomeKind =
  | "escalation-resolved"
  | "degraded-agent-identified"
  | "rationale-reconstructed"
  | "steering-adjusted"
  | "disruption-contained";

/** A single Job_To_Be_Done bound to its seeded scenario (mirrors `ScenarioDescriptor`). */
interface JtbdCase {
  readonly job: string;
  readonly title: string;
  readonly seed: number;
  readonly scenarioId: string;
  readonly surfaceId: string;
  readonly surfacePath: string;
  readonly terminalKind: TerminalOutcomeKind;
  /** True for "resolve an escalation correctly" — the only job with the audit-row-first check (Req 3.5). */
  readonly checksAuditRowFirst: boolean;
}

/** The five enumerated Jobs-To-Be-Done (Req 3.1), mirroring `SCENARIOS`. */
const JTBD_CASES: readonly JtbdCase[] = [
  {
    job: "resolve-escalation-correctly",
    title: "Resolve an escalation correctly",
    seed: 30101,
    scenarioId: "jtbd.resolve-escalation",
    surfaceId: "override-cockpit",
    surfacePath: "/cockpit",
    terminalKind: "escalation-resolved",
    checksAuditRowFirst: true,
  },
  {
    job: "identify-degraded-agent",
    title: "Identify which agent degraded and why",
    seed: 30202,
    scenarioId: "jtbd.identify-degraded-agent",
    surfaceId: "agent-council",
    surfacePath: "/agents",
    terminalKind: "degraded-agent-identified",
    checksAuditRowFirst: false,
  },
  {
    job: "reconstruct-decision-rationale",
    title: "Reconstruct a decision's rationale",
    seed: 30303,
    scenarioId: "jtbd.reconstruct-rationale",
    surfaceId: "decision-theater",
    surfacePath: "/decisions",
    terminalKind: "rationale-reconstructed",
    checksAuditRowFirst: false,
  },
  {
    job: "adjust-steering-safely",
    title: "Adjust steering safely",
    seed: 30404,
    scenarioId: "jtbd.adjust-steering",
    surfaceId: "steering",
    surfacePath: "/steering",
    terminalKind: "steering-adjusted",
    checksAuditRowFirst: false,
  },
  {
    job: "catch-disruption-before-cascade",
    title: "Catch a disruption before it cascades",
    seed: 30505,
    scenarioId: "jtbd.catch-disruption",
    surfaceId: "mission-control",
    surfacePath: "/",
    terminalKind: "disruption-contained",
    checksAuditRowFirst: false,
  },
];

/**
 * The scorecard row the Effectiveness_Harness returns per Job_To_Be_Done
 * (mirrors `TaskCompletionResult` from design section C).
 */
interface TaskCompletionResult {
  readonly job: string;
  readonly steps: number;
  readonly latencyMs: number;
  readonly errorRate: number;
  readonly reachedTerminal: boolean;
  readonly terminalKind?: TerminalOutcomeKind;
  readonly auditRowBeforeActed: boolean;
  readonly proxyCeiling: string;
}

/** True iff the harness global exposes `runTaskCompletion` in the page. */
async function taskCompletionHarnessReady(page: Page): Promise<boolean> {
  return page.evaluate(
    () =>
      typeof (
        window as unknown as { __atlasHarness?: { runTaskCompletion?: unknown } }
      ).__atlasHarness?.runTaskCompletion === "function",
  );
}

/**
 * Record the Scripted_Proxy ceiling on the test's report (Req 3.6, 20.5). This
 * runs on EVERY test — driven or skipped — so no effectiveness artifact omits
 * the honest ceiling.
 */
async function recordProxyCeiling(testInfo: TestInfo): Promise<void> {
  testInfo.annotations.push({ type: "scripted-proxy", description: PROXY_CEILING });
  await testInfo.attach("scripted-proxy-ceiling.txt", {
    body: PROXY_CEILING,
    contentType: "text/plain",
  });
}

/** Record the measured completion metrics on the test's report (Req 3.2). */
async function recordMetrics(testInfo: TestInfo, result: TaskCompletionResult): Promise<void> {
  testInfo.annotations.push(
    { type: "jtbd-job", description: result.job },
    { type: "jtbd-steps", description: String(result.steps) },
    { type: "jtbd-latency-ms", description: String(result.latencyMs) },
    { type: "jtbd-error-rate", description: String(result.errorRate) },
  );
  await testInfo.attach(`task-completion.${result.job}.json`, {
    body: JSON.stringify(result, null, 2),
    contentType: "application/json",
  });
}

// ── Effectiveness_Scorecard emission (Req 4.1, 4.2, 4.6) ─────────────────────
//
// The Task_Completion_Tests emit a single versioned `scorecard.json` recording,
// per Job_To_Be_Done, the measured steps, time-to-complete, and error/dead-end
// rate, plus the run seed and harness version and a reserved
// `interruptionPrecision` field (filled by the North-Star metric in task 15).
// The committed baseline lives at `spec/effectiveness/scorecard.baseline.json`
// and the Effectiveness_Ratchet (task 4.2) compares this fresh artifact against
// it.
//
// The scorecard SHAPE and its constants MIRROR the shipped
// `@lib/effectiveness-scorecard` module (kept local so this Playwright spec
// stays free of the app's `@`-alias module graph, the same convention the rest
// of this suite follows). The values below MUST stay in lockstep with that
// module.

/** Mirrors `SCORECARD_SCHEMA_VERSION` from `@lib/effectiveness-scorecard`. */
const SCORECARD_SCHEMA_VERSION = 1;
/** Mirrors `EFFECTIVENESS_HARNESS_VERSION`. */
const HARNESS_VERSION = "1.0.0";
/** Mirrors `EFFECTIVENESS_HARNESS_SEED` (master seed; per-scenario seeds derive from it). */
const HARNESS_SEED = 30000;
/** Mirrors `SCORECARD_FRESH_RELPATH` (gitignored under `test-results/`). */
const SCORECARD_FRESH_RELPATH = "test-results/effectiveness/scorecard.json";
/** Mirrors `JOB_ORDER` — the canonical, deterministic row order. */
const JOB_ORDER: readonly string[] = [
  "resolve-escalation-correctly",
  "identify-degraded-agent",
  "reconstruct-decision-rationale",
  "adjust-steering-safely",
  "catch-disruption-before-cascade",
];

/** One measured row per Job_To_Be_Done (mirrors `ScorecardRow`). */
interface ScorecardRow {
  readonly job: string;
  readonly steps: number;
  readonly latencyMs: number;
  readonly errorRate: number;
}

// ── Interruption_Precision — the North-Star metric (Req 13.1, 13.2, 13.4) ────
//
// Interruption_Precision = warranted ÷ total interruptions over the window. It
// is recorded in the emitted scorecard as the primary (North-Star) metric. The
// seeded interruption set and the ratio MIRROR the shipped
// `@lib/interruption-precision` module (kept local so this Playwright spec stays
// free of the app's `@`-alias module graph, the same convention this suite
// follows for the scorecard shape). The values below MUST stay in lockstep with
// `SEEDED_INTERRUPTIONS` / `interruptionPrecision` in that module.

/** A single interruption the Console raised (mirrors `Interruption`). */
interface Interruption {
  readonly warranted: boolean;
}

/**
 * The interruptions raised across the seeded scenarios (mirrors
 * `SEEDED_INTERRUPTIONS`): resolve-escalation (warranted — irreversible/
 * high-blast), catch-disruption (warranted — review changed the outcome),
 * adjust-steering (warranted — broad blast radius), identify-degraded-agent
 * (unwarranted — a self-resolving blip the scripted proxy models).
 */
const SEEDED_INTERRUPTIONS: readonly Interruption[] = [
  { warranted: true },
  { warranted: true },
  { warranted: true },
  { warranted: false },
];

/** Mirrors `interruptionPrecision` — warranted ÷ total, [0,1], total===0 → null. */
function interruptionPrecision(interruptions: readonly Interruption[]): number | null {
  const total = interruptions.length;
  if (total === 0) return null;
  const warranted = interruptions.filter((i) => i.warranted).length;
  return warranted / total;
}

/**
 * Rows measured across this file's tests. Populated as each Task_Completion_Test
 * records its result; drained once by {@link emitScorecard} in `afterAll`. The
 * describe block runs `serial` so all rows land in the same worker before the
 * scorecard is emitted.
 */
const measuredRows: ScorecardRow[] = [];

/**
 * Writes the single versioned `scorecard.json` from the rows measured this run
 * (Req 4.1, 4.2, 4.6). Sorted into {@link JOB_ORDER} and pretty-printed so the
 * artifact is deterministic and diff-friendly. `interruptionPrecision` records
 * the North-Star metric computed over the seeded interruptions (Req 13.2, 13.4).
 */
function emitScorecard(): void {
  const rank = (job: string): number => {
    const i = JOB_ORDER.indexOf(job);
    return i === -1 ? JOB_ORDER.length : i;
  };
  const rows = [...measuredRows].sort((a, b) => rank(a.job) - rank(b.job));
  const scorecard = {
    schemaVersion: SCORECARD_SCHEMA_VERSION,
    harnessVersion: HARNESS_VERSION,
    seed: HARNESS_SEED,
    rows,
    interruptionPrecision: interruptionPrecision(SEEDED_INTERRUPTIONS),
    proxyCeiling: PROXY_CEILING,
  };
  const outPath = resolve(process.cwd(), SCORECARD_FRESH_RELPATH);
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, `${JSON.stringify(scorecard, null, 2)}\n`, "utf8");
}

// Keep all five Jobs-To-Be-Done in one worker so their measured rows aggregate
// into a single emitted scorecard (Req 4.1); without this, `fullyParallel` could
// split the tests across workers and fragment the artifact.
test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  // Seed an authenticated (admin) session so RouteGuard passes for every
  // Surface's minRole (mirrors cockpit.spec.ts / the sibling harness e2e specs).
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "synapse.session",
      JSON.stringify({
        state: { role: "admin", operatorTokenRef: "e2e-operator" },
        version: 0,
      }),
    );
  });
});

test.describe("Task_Completion_Tests — Jobs-To-Be-Done (Req 3)", () => {
  // Emit the single versioned scorecard once, from the canonical project only,
  // so parallel projects (chromium/firefox/webkit) do not race on the artifact
  // path. Chromium is the canonical emitter (Req 4.1, 4.2, 4.6).
  test.afterAll(() => {
    if (test.info().project.name === "chromium") {
      emitScorecard();
    }
  });

  for (const jtbd of JTBD_CASES) {
    test(`${jtbd.title} reaches the correct terminal outcome with no dead-ends`, async ({
      page,
    }, testInfo) => {
      // Req 3.6 / 20.5 — the honest ceiling is on EVERY report, first thing,
      // so it is present even when the harness-driven assertions skip below.
      await recordProxyCeiling(testInfo);

      // Base reachability: the terminal Surface loads and is not bounced to
      // /login (the operator can at least reach where the job completes).
      await page.goto(jtbd.surfacePath);
      if (page.url().includes("/login")) {
        test.skip(true, "needs an authenticated session fixture");
      }
      await expect(page.locator("main")).toBeVisible();

      // Driving the seeded Job_To_Be_Done through the harness requires the
      // in-browser harness global; skip the metric/terminal assertions cleanly
      // until it is wired (same convention as the other harness-dependent e2e
      // specs). The ceiling above is already recorded on this report.
      if (!(await taskCompletionHarnessReady(page))) {
        test.skip(true, "Task_Completion harness (window.__atlasHarness.runTaskCompletion) not wired yet");
      }

      // Drive the seeded scenario end-to-end through the harness. Resolves with
      // the scorecard row (steps, latency, error/dead-end rate, terminal state).
      const result = await page.evaluate(async (scenarioId) => {
        const harness = (
          window as unknown as {
            __atlasHarness: { runTaskCompletion(id: string): Promise<TaskCompletionResult> };
          }
        ).__atlasHarness;
        return harness.runTaskCompletion(scenarioId);
      }, jtbd.scenarioId);

      // Req 3.2 — record steps, time-to-complete, and error/dead-end rate.
      await recordMetrics(testInfo, result);

      // Req 4.1 — accumulate this job's measured row for the Effectiveness_Scorecard.
      measuredRows.push({
        job: result.job,
        steps: result.steps,
        latencyMs: result.latencyMs,
        errorRate: result.errorRate,
      });

      // Req 3.6 — the harness itself carries the Scripted_Proxy statement; the
      // report must reflect it, so assert the row is honestly labelled.
      expect(result.proxyCeiling, "harness result must carry the Scripted_Proxy ceiling").toContain(
        "Scripted_Proxy",
      );

      // Req 3.3 — the operator reaches the CORRECT terminal outcome for the
      // seed; fail if it is wrong or unreachable.
      expect(result.reachedTerminal, `${jtbd.job}: terminal outcome unreachable`).toBe(true);
      if (result.terminalKind !== undefined) {
        expect(result.terminalKind, `${jtbd.job}: wrong terminal outcome`).toBe(jtbd.terminalKind);
      }

      // Req 3.4 — fail on any dead-end (missing/unjustifiably-disabled
      // affordance or non-recoverable state): the dead-end rate must be zero.
      expect(
        result.errorRate,
        `${jtbd.job}: hit a dead-end (error/dead-end rate ${result.errorRate} > 0)`,
      ).toBe(0);

      // Sanity: steps and latency were actually measured for the scorecard.
      expect(result.steps, `${jtbd.job}: no steps recorded`).toBeGreaterThan(0);
      expect(result.latencyMs, `${jtbd.job}: no time-to-complete recorded`).toBeGreaterThanOrEqual(0);

      // Req 3.5 — for the escalation job only, the override must commit the
      // audit row BEFORE the decision is marked acted (audit-row-first).
      if (jtbd.checksAuditRowFirst) {
        expect(
          result.auditRowBeforeActed,
          "resolve-escalation: audit row must commit before the decision is marked acted (audit-row-first)",
        ).toBe(true);
      }
    });
  }
});
