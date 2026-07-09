/**
 * Effectiveness_Ratchet — CI invocation script (design "Where the Scorecard and
 * Ratchet sit", Req 4.3, 4.4, 4.5, 13.3).
 *
 * This is the thin, I/O-bearing shell around the pure comparator
 * (`@lib/effectiveness-ratchet`): it loads the committed baseline scorecard and
 * the fresh `scorecard.json` the Task_Completion_Tests emit, calls
 * {@link compareScorecard}, prints a human-readable verdict, and exits NON-ZERO
 * naming the regressed job and metric on any regression beyond tolerance (Req
 * 4.3). Because all comparison logic lives in the pure comparator, this script
 * carries no branching to test — it only reads files and reports.
 *
 * A missing or malformed baseline (or fresh) scorecard is a HARD error naming
 * the file, never a silent pass (design "Ratchet and scorecard errors").
 *
 * Paths (relative to the `frontend/` root) come from the shared scorecard
 * module so the emitter and the gate agree on exactly one location each:
 *   • baseline → {@link SCORECARD_BASELINE_RELPATH} (committed, versioned).
 *   • fresh    → {@link SCORECARD_FRESH_RELPATH} (gitignored per-run artifact),
 *     overridable via `argv[2]` or `$SCORECARD_FRESH_PATH` for local runs.
 *
 * Run: `pnpm effectiveness:ratchet` (from `frontend/`) — or
 *      `tsx spec/effectiveness/run-ratchet.ts [freshScorecardPath]`.
 */

import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  compareScorecard,
  DEFAULT_RATCHET_TOLERANCE,
  type RatchetResult,
} from "@lib/effectiveness-ratchet";
import {
  parseScorecard,
  SCORECARD_BASELINE_RELPATH,
  SCORECARD_FRESH_RELPATH,
  type EffectivenessScorecard,
} from "@lib/effectiveness-scorecard";

/** The `frontend/` root: this file lives at `frontend/spec/effectiveness/`. */
const FRONTEND_ROOT = fileURLToPath(new URL("../../", import.meta.url));

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/** Load + validate a scorecard, turning any read/parse failure into a named hard error. */
async function loadScorecardFile(path: string, label: string): Promise<EffectivenessScorecard> {
  let text: string;
  try {
    text = await readFile(path, "utf8");
  } catch (err) {
    throw new Error(`Effectiveness ${label} scorecard not found at ${path}: ${describeError(err)}`);
  }
  try {
    return parseScorecard(text);
  } catch (err) {
    throw new Error(
      `Effectiveness ${label} scorecard at ${path} is malformed: ${describeError(err)}`,
    );
  }
}

/** Render the verdict to stdout/stderr, naming every regressed job + metric (Req 4.3). */
function report(result: RatchetResult): void {
  const tol = DEFAULT_RATCHET_TOLERANCE;
  process.stdout.write(
    "# Effectiveness Ratchet\n\n" +
      `Tolerance: steps ±${(tol.stepsPct * 100).toFixed(0)}%, ` +
      `latency ±${(tol.latencyPct * 100).toFixed(0)}%, ` +
      `errorRate +${tol.errorRateAbs}, ` +
      `interruptionPrecision −${tol.interruptionPrecisionAbs}\n\n`,
  );

  if (result.passed) {
    process.stdout.write(
      "Ratchet: **PASS** — no job's steps/latency/error-rate and no " +
        "Interruption_Precision regressed beyond tolerance.\n",
    );
    process.stdout.write(
      result.canAdvanceBaseline
        ? "Baseline: every metric improved or held — the committed baseline MAY be advanced (Req 4.5).\n"
        : "Baseline: some metric regressed within tolerance — hold the committed baseline.\n",
    );
    return;
  }

  process.stderr.write("Ratchet: **FAIL** — effectiveness regressed beyond tolerance:\n");
  for (const r of result.regressions) {
    process.stderr.write(
      `  • ${r.job} / ${r.metric}: baseline ${r.baseline} → observed ${r.observed}\n`,
    );
  }
}

async function main(): Promise<void> {
  const baselinePath = join(FRONTEND_ROOT, SCORECARD_BASELINE_RELPATH);
  const freshPath =
    process.argv[2] ??
    process.env.SCORECARD_FRESH_PATH ??
    join(FRONTEND_ROOT, SCORECARD_FRESH_RELPATH);

  const [baseline, fresh] = await Promise.all([
    loadScorecardFile(baselinePath, "baseline"),
    loadScorecardFile(freshPath, "fresh"),
  ]);

  const result = compareScorecard(baseline, fresh, DEFAULT_RATCHET_TOLERANCE);
  report(result);

  if (!result.passed) process.exitCode = 1;
}

// Run only when invoked directly (not when imported by a test).
const isDirectRun =
  process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1];

if (isDirectRun) {
  main().catch((err: unknown) => {
    process.stderr.write(`\nEffectiveness ratchet crashed: ${describeError(err)}\n`);
    process.exitCode = 1;
  });
}
