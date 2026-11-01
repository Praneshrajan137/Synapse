/**
 * Effectiveness_Baseline check -- the I/O-bearing shell around the pure validator
 * (`@lib/effectiveness-baseline`), per R8.10: "THE committed baseline SHALL record, for
 * each row, the `harnessVersion`, the `seed`, and the timestamp of the run that produced
 * that row, SHALL retain the `proxyCeiling` statement, and IF every row carries an
 * identical `steps` value and an identical `latencyMs` value, THEN THE baseline check
 * SHALL fail the baseline as an authored ceiling rather than accept it as a measurement."
 *
 * This module reads two files and reports. All rule logic lives in the pure validator so
 * the property test (task 11.8, Property 36) can drive the rules without touching disk:
 *   * the committed thresholds, `infrastructure/quality/effectiveness-baseline.json`
 *   * the committed baseline, `frontend/spec/effectiveness/scorecard.baseline.json`
 *     (path from {@link SCORECARD_BASELINE_RELPATH}, so the emitter, the ratchet, and
 *     this check name one location).
 *
 * Both reads pass `utf8` explicitly (E-S13-07). A missing or malformed policy file is a
 * hard error naming the file, never a relaxed default: a check that cannot read its own
 * thresholds has not passed (I-7).
 *
 * Run: `tsx spec/effectiveness/check-baseline.ts [baselinePath]` from `frontend/`.
 *
 * ## Expected state on landing, stated plainly (I-7)
 *
 * The baseline committed today carries `steps: 20` and `latencyMs: 15000` on all five
 * rows and no per-row stamps, so this check FAILS it: five `missing-stamp` rejections
 * plus one `uniform-metrics`. That is R8.10's finding becoming mechanical. It clears when
 * the browser harness (task 11.1) and the complete-or-failed emitter (task 11.2) produce
 * a measured baseline through `buildBaseline`; nothing here should be softened to make
 * the current artifact pass, and no stamp may be typed in by hand to satisfy it.
 *
 * ## Deferred, and to whom
 *
 * Two things this check deliberately does NOT do:
 *
 *   1. **Run in CI.** `.github/workflows/frontend.yml` is owned by tasks 11.1/11.2 (they
 *      are removing `|| true` from `:163` and `:288` under R8.9). This check needs one
 *      blocking step in the `effectiveness-ratchet` job. Until that step exists the rule
 *      is authored and locally runnable but not enforced -- which is the honest status,
 *      not a pass.
 *   2. **Cross-check a row's stamps against the run that emitted the fresh scorecard.**
 *      A stamp proves a claim was made, not that a measurement happened; only a job
 *      holding both artifacts can compare the fresh run's `harnessVersion`/`seed` against
 *      the committed ones. That comparison belongs beside the ratchet invocation in the
 *      same workflow job (R8.3/R8.4 territory), and is noted rather than faked here.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  type BaselinePolicy,
  type BaselineVerdict,
  checkCommittedBaseline,
  parseBaselinePolicy,
} from "@lib/effectiveness-baseline";
import { SCORECARD_BASELINE_RELPATH } from "@lib/effectiveness-scorecard";

/**
 * Root resolution, and why it is no longer a module-level `fileURLToPath` (R2.6).
 *
 * This module previously resolved both roots at import time with
 * `fileURLToPath(new URL("../../", import.meta.url))`. That works when the file runs as a
 * CLI script under Node, where `import.meta.url` is a `file:` URL. It does **not** work
 * when a vitest test imports it: Vite serves the module from its own graph, so
 * `import.meta.url` carries an `http:` origin, `fileURLToPath` throws
 * `ERR_INVALID_URL_SCHEME` **at import time**, and the importing suite dies during
 * collection.
 *
 * That is not a hypothetical. It is why
 * `__tests__/baseline-measurement.property.test.ts` reported "0 test" as a failed suite:
 * Property 36 is authored, declared in the inventory, and had **never executed** — the
 * exact "authored but not executed" state R2.12 requires a document to disclose rather
 * than round up to coverage.
 *
 * So: resolution is lazy (an import can no longer throw), it prefers the `file:` URL when
 * there is one, and it otherwise walks up from the working directory looking for the two
 * directories that identify this repository root — which makes it independent of the
 * directory the runner happened to start in.
 */
function repoRootFromFileUrl(): string | null {
  try {
    const here = new URL(import.meta.url);
    if (here.protocol !== "file:") {
      return null;
    }
    return fileURLToPath(new URL("../../../", here));
  } catch {
    return null;
  }
}

function repoRootByWalkingUp(): string {
  let directory = process.cwd();
  for (;;) {
    if (
      existsSync(join(directory, "frontend", "package.json")) &&
      existsSync(join(directory, BASELINE_POLICY_RELPATH))
    ) {
      return directory;
    }
    const parent = dirname(directory);
    if (parent === directory) {
      throw new Error(
        "could not locate the repository root: no ancestor of " +
          `${process.cwd()} contains both frontend/package.json and ` +
          `${BASELINE_POLICY_RELPATH}`,
      );
    }
    directory = parent;
  }
}

let cachedRepoRoot: string | null = null;

/** The repository root, one level above `frontend/`. Resolved once, lazily. */
function repoRoot(): string {
  cachedRepoRoot ??= repoRootFromFileUrl() ?? repoRootByWalkingUp();
  return cachedRepoRoot;
}

/** The `frontend/` root. */
function frontendRoot(): string {
  return join(repoRoot(), "frontend");
}

/**
 * The committed thresholds, relative to the repository root. Under
 * `infrastructure/quality/` with every other machine-read gate configuration (AD-13), so
 * a threshold change is a reviewable diff in the file the whole repo already watches.
 */
export const BASELINE_POLICY_RELPATH = "infrastructure/quality/effectiveness-baseline.json";

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/** Read a file as utf-8 (E-S13-07), turning any failure into a named hard error. */
function readUtf8(path: string, label: string): string {
  try {
    return readFileSync(path, "utf8");
  } catch (err) {
    throw new Error(
      `Effectiveness baseline ${label} not readable at ${path}: ${describeError(err)}`,
    );
  }
}

/**
 * Loads the committed authored-ceiling thresholds. Throws (naming the file) on a missing,
 * unparseable, or rule-disabling policy -- the validator has no fallback numbers.
 */
export function loadBaselinePolicy(policyPath?: string): BaselinePolicy {
  const path = policyPath ?? join(repoRoot(), BASELINE_POLICY_RELPATH);
  return parseBaselinePolicy(readUtf8(path, "policy"));
}

/** The committed baseline's absolute path. */
export function committedBaselinePath(): string {
  return join(frontendRoot(), SCORECARD_BASELINE_RELPATH);
}

/**
 * Checks the committed baseline against the committed policy and returns the verdict.
 * Exported so a test or a future CI wrapper reuses the same path resolution rather than
 * re-deriving it.
 */
export function checkCommittedBaselineFile(
  baselinePath?: string,
  policyPath?: string,
): BaselineVerdict {
  const policy = loadBaselinePolicy(policyPath);
  const path = baselinePath ?? committedBaselinePath();
  return checkCommittedBaseline(readUtf8(path, "artifact"), policy);
}

/** ASCII-only report (Windows console safe). */
function report(path: string, verdict: BaselineVerdict): void {
  process.stdout.write(`# Effectiveness Baseline Check (R8.10)\n\nArtifact: ${path}\n\n`);
  if (verdict.outcome === "accepted") {
    process.stdout.write(
      `Baseline: **ACCEPTED** -- ${verdict.baseline.rows.length} rows, each naming the ` +
        "harness version, seed, and capture instant that produced it; the Scripted_Proxy " +
        "statement is retained verbatim; steps and latencyMs are not uniform across rows.\n",
    );
    process.stdout.write(
      "Note: an accepted baseline is a well-formed, traceable measurement record. It is " +
        "not evidence of human comprehension -- see the retained Scripted_Proxy ceiling.\n",
    );
    return;
  }
  process.stderr.write(
    "Baseline: **REJECTED** -- this artifact is not a measurement (R8.10):\n",
  );
  for (const rejection of verdict.rejections) {
    const subject = rejection.job === null ? "baseline" : rejection.job;
    process.stderr.write(`  * [${rejection.kind}] ${subject}: ${rejection.detail}\n`);
  }
  process.stderr.write(
    "\nA rejected baseline is a failed check, never a warning on a pass. Fix it by " +
      "emitting a measured baseline from a harness run (buildBaseline), not by editing " +
      "the numbers or the thresholds.\n",
  );
}

function main(): void {
  const path = process.argv[2] ?? committedBaselinePath();
  const verdict = checkCommittedBaselineFile(path);
  report(path, verdict);
  if (verdict.outcome === "rejected") process.exitCode = 1;
}

// Run only when invoked directly (not when imported by a test).
const isDirectRun =
  process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1];

if (isDirectRun) {
  try {
    main();
  } catch (err: unknown) {
    process.stderr.write(`\nEffectiveness baseline check crashed: ${describeError(err)}\n`);
    process.exitCode = 1;
  }
}
