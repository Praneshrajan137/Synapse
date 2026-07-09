/**
 * Effectiveness_Scorecard — the versioned, committed record of Console
 * effectiveness per Job_To_Be_Done (design "D. lib — Effectiveness_Scorecard
 * emitter + ratchet comparator (Req 4, Req 13)"; Data Models "ScorecardRow" /
 * "EffectivenessScorecard").
 *
 * This is the single shared shape both sides of the effectiveness gate agree on:
 *
 *   • The Task_Completion_Tests (`frontend/tests/e2e/task-completion.jtbd.spec.ts`,
 *     task 3.2) emit a fresh `scorecard.json` per run, recording — per
 *     Job_To_Be_Done — the measured steps, time-to-complete (`latencyMs`), and
 *     error/dead-end rate, plus the run `seed` and `harnessVersion` for
 *     reproducibility (Req 4.1, 4.6) and a reserved `interruptionPrecision`
 *     field filled by the North-Star metric in task 15 (Req 13.2, 13.4).
 *
 *   • The Effectiveness_Ratchet (`@lib/effectiveness-ratchet`, task 4.2 — a
 *     SEPARATE task) consumes this exact shape to compare a fresh scorecard
 *     against the committed baseline and fail on regression (Req 4.3–4.5). This
 *     module deliberately owns only the *type and (de)serialization*; the pure
 *     comparator lives in `effectiveness-ratchet.ts`.
 *
 * `JobToBeDone` is defined here — in the shipped `lib/` layer — because both the
 * shipped comparator and the test-only harness (`spec/effectiveness/scenarios`)
 * bind to it; the harness re-exports it from here so there is exactly one source
 * of truth for the enumerated operator jobs (Req 3.1).
 *
 * Serialization is canonical (sorted keys, deterministic row order) so a fixed
 * seed yields a byte-stable artifact across runs — the same reproducibility rule
 * the harness fixtures obey (Req 1.3, 4.6).
 */

import { z } from "zod";

import { canonicalJson } from "@lib/json-canonical";

/**
 * The named set of operator objectives the Console must support, measured for
 * task completion (Req 3.1). The single source of truth for the enumerated
 * jobs: the test-only harness (`spec/effectiveness/scenarios/types.ts`)
 * re-exports this type rather than redeclaring it.
 */
export type JobToBeDone =
  | "resolve-escalation-correctly"
  | "identify-degraded-agent"
  | "reconstruct-decision-rationale"
  | "adjust-steering-safely"
  | "catch-disruption-before-cascade";

/**
 * The canonical ordering of Jobs-To-Be-Done. Scorecard rows are always sorted
 * by this order so the emitted artifact is byte-stable regardless of the order
 * the Task_Completion_Tests happen to run in (Req 4.6). Ordered by the operator
 * loop: Intervene → Investigate → Configure → Monitor.
 */
export const JOB_ORDER: readonly JobToBeDone[] = [
  "resolve-escalation-correctly",
  "identify-degraded-agent",
  "reconstruct-decision-rationale",
  "adjust-steering-safely",
  "catch-disruption-before-cascade",
];

/** The scorecard schema version; bump on any breaking shape change. */
export const SCORECARD_SCHEMA_VERSION = 1;

/**
 * The harness version stamped on every emitted scorecard for reproducibility
 * (Req 4.6). Bump when a change to the harness could move measurements (e.g. a
 * scenario path, a fixture, or a metric definition changes) so a scorecard is
 * always attributable to the harness that produced it.
 */
export const EFFECTIVENESS_HARNESS_VERSION = "1.0.0";

/**
 * The master seed for an effectiveness harness run (Req 4.6). Per-scenario seeds
 * (`jtbd.resolve-escalation` → 30101, `jtbd.identify-degraded-agent` → 30202, …)
 * derive from this base; the scorecard records the master seed so a whole run is
 * reproducible from a single value.
 */
export const EFFECTIVENESS_HARNESS_SEED = 30000;

/**
 * The honest ceiling recorded on every effectiveness artifact (Req 3.6, 13.5,
 * 20.5). Kept verbatim so the scorecard, the Task_Completion_Test reports, and
 * the JTBD suite all state the identical caveat.
 */
export const SCRIPTED_PROXY_CEILING =
  "Scripted_Proxy: this measurement demonstrates that an operator path EXISTS and is EFFICIENT " +
  "(steps, time-to-complete, dead-ends), but it does NOT establish human comprehension. Real " +
  "effectiveness requires real-user (RITE) testing with 3–5 operators.";

/**
 * Where the committed baseline scorecard lives, relative to the `frontend/`
 * root. The Effectiveness_Ratchet (task 4.2) reads this committed artifact.
 */
export const SCORECARD_BASELINE_RELPATH = "spec/effectiveness/scorecard.baseline.json";

/**
 * Where the Task_Completion_Tests write the fresh, per-run scorecard, relative
 * to the `frontend/` root. Under `test-results/` so it is gitignored (never
 * committed) — only the baseline above is versioned.
 */
export const SCORECARD_FRESH_RELPATH = "test-results/effectiveness/scorecard.json";

/** One measured row per Job_To_Be_Done (Req 4.1). */
export interface ScorecardRow {
  /** The operator objective this row measures. */
  readonly job: JobToBeDone;
  /** Affordance activations to the terminal outcome (measured steps). */
  readonly steps: number;
  /** Time-to-complete in milliseconds. */
  readonly latencyMs: number;
  /** Error/dead-end rate: dead-ends ÷ attempts (0 on a clean golden path). */
  readonly errorRate: number;
}

/**
 * The versioned, committed effectiveness artifact (Req 4.2, 4.6). Records the
 * per-job measurements plus the reproducibility stamps (`seed`,
 * `harnessVersion`) and the reserved North-Star `interruptionPrecision` field
 * (Req 13.2, 13.4 — filled in task 15, `null` until then).
 */
export interface EffectivenessScorecard {
  /** Scorecard schema version ({@link SCORECARD_SCHEMA_VERSION}). */
  readonly schemaVersion: number;
  /** Harness version that produced the measurement (reproducibility, Req 4.6). */
  readonly harnessVersion: string;
  /** Master seed of the run (reproducibility, Req 4.6). */
  readonly seed: number;
  /** One measured row per Job_To_Be_Done, sorted by {@link JOB_ORDER}. */
  readonly rows: readonly ScorecardRow[];
  /**
   * The North-Star Interruption_Precision over the run (Req 13.2, 13.4).
   * Reserved: `null` until task 15 wires the metric, so the field is present
   * and comparable from the first committed baseline onward.
   */
  readonly interruptionPrecision: number | null;
  /** The Scripted_Proxy honest ceiling ({@link SCRIPTED_PROXY_CEILING}). */
  readonly proxyCeiling: string;
}

/** Zod schema mirroring {@link ScorecardRow}, used to validate a loaded scorecard. */
const ScorecardRowSchema = z
  .object({
    job: z.enum([
      "resolve-escalation-correctly",
      "identify-degraded-agent",
      "reconstruct-decision-rationale",
      "adjust-steering-safely",
      "catch-disruption-before-cascade",
    ]),
    steps: z.number().finite().nonnegative(),
    latencyMs: z.number().finite().nonnegative(),
    errorRate: z.number().finite().min(0).max(1),
  })
  .strict();

/** Zod schema mirroring {@link EffectivenessScorecard} for safe load-time parsing. */
export const EffectivenessScorecardSchema = z
  .object({
    schemaVersion: z.number().int().positive(),
    harnessVersion: z.string().min(1),
    seed: z.number().finite(),
    rows: z.array(ScorecardRowSchema),
    interruptionPrecision: z.number().finite().min(0).max(1).nullable(),
    proxyCeiling: z.string().min(1),
  })
  .strict();

/** Options for {@link buildScorecard}. */
export interface BuildScorecardOptions {
  readonly rows: readonly ScorecardRow[];
  /** Defaults to {@link EFFECTIVENESS_HARNESS_SEED}. */
  readonly seed?: number;
  /** Defaults to {@link EFFECTIVENESS_HARNESS_VERSION}. */
  readonly harnessVersion?: string;
  /** Defaults to `null` (reserved for task 15). */
  readonly interruptionPrecision?: number | null;
}

/**
 * Builds an {@link EffectivenessScorecard} from measured rows, stamping the
 * schema version, seed, harness version, and Scripted_Proxy ceiling and sorting
 * the rows into {@link JOB_ORDER} so the artifact is deterministic (Req 4.1,
 * 4.6). Pure and I/O-free — the emitter (Task_Completion_Tests) and any future
 * caller share one construction path.
 */
export function buildScorecard(opts: BuildScorecardOptions): EffectivenessScorecard {
  const rank = (job: JobToBeDone): number => {
    const i = JOB_ORDER.indexOf(job);
    return i === -1 ? JOB_ORDER.length : i;
  };
  const rows = [...opts.rows].sort((a, b) => rank(a.job) - rank(b.job));
  return {
    schemaVersion: SCORECARD_SCHEMA_VERSION,
    harnessVersion: opts.harnessVersion ?? EFFECTIVENESS_HARNESS_VERSION,
    seed: opts.seed ?? EFFECTIVENESS_HARNESS_SEED,
    rows,
    interruptionPrecision: opts.interruptionPrecision ?? null,
    proxyCeiling: SCRIPTED_PROXY_CEILING,
  };
}

/**
 * Canonical serialization of a scorecard: sorted keys, no incidental
 * whitespace, deterministic bytes for a fixed seed (Req 4.6). Rows are sorted
 * into {@link JOB_ORDER} first so a reordered input still yields identical
 * bytes. Reuses the shared {@link canonicalJson} rule the transport layer uses
 * for hash-stable payloads.
 */
export function serializeScorecard(scorecard: EffectivenessScorecard): string {
  const ordered = buildScorecard({
    rows: scorecard.rows,
    seed: scorecard.seed,
    harnessVersion: scorecard.harnessVersion,
    interruptionPrecision: scorecard.interruptionPrecision,
  });
  return canonicalJson(ordered);
}

/**
 * Parses and validates a scorecard from its JSON text, throwing a descriptive
 * error when the shape is invalid. Used by the ratchet (task 4.2) to load the
 * committed baseline and the fresh artifact safely rather than trusting `JSON.parse`.
 */
export function parseScorecard(text: string): EffectivenessScorecard {
  const parsed: unknown = JSON.parse(text);
  const result = EffectivenessScorecardSchema.safeParse(parsed);
  if (!result.success) {
    throw new Error(`Invalid EffectivenessScorecard: ${result.error.message}`);
  }
  return result.data;
}
