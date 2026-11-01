/**
 * Effectiveness_Baseline -- the schema and the check for the COMMITTED effectiveness
 * baseline (purpose-achievement-audit R8.10; design E6: "the baseline schema gains
 * `harnessVersion`, `seed`, `capturedAt` per row, keeps `proxyCeiling` verbatim [...] and
 * a baseline whose rows all carry identical `steps` and `latencyMs` is rejected as an
 * authored ceiling").
 *
 * ## Why this module exists separately from `@lib/effectiveness-scorecard`
 *
 * A *scorecard* is what one run emits. A *baseline* is what the repository commits and
 * ratchets against, and it is strictly stronger: the audit's finding is that the
 * committed baseline "is not a measurement: all five jobs carry identical `steps: 20`,
 * `latencyMs: 15000`, `errorRate: 0` -- authored ceilings". A hand-typed baseline is
 * byte-indistinguishable from a measured one under the scorecard schema, which accepts
 * any five well-typed numbers. So the baseline gets its own schema and its own check,
 * and `@lib/effectiveness-scorecard` keeps owning the per-run shape.
 *
 * ## The three rules (R8.10, Property 36 - task 11.8 writes the property test)
 *
 *   1. **Per-row provenance.** Every row carries `harnessVersion`, `seed`, and
 *      `capturedAt` (ISO-8601 UTC). A row that cannot name the run that produced it is
 *      not a measurement, so a row missing any stamp is `missing-stamp`. The
 *      document-level stamps already on the scorecard are not enough: they say one run
 *      existed, not that THIS row came from it.
 *   2. **The ceiling is retained.** `proxyCeiling` must be present and non-blank, and it
 *      is kept **verbatim** -- read through untouched, never trimmed, normalized,
 *      re-wrapped, or re-derived from {@link SCRIPTED_PROXY_CEILING}. The audit credits
 *      that disclosure explicitly; silently regenerating it would turn a retained
 *      statement into a manufactured one. `isNonBlank` trims only to TEST, never to
 *      transform. The stricter committed-artifact rule below additionally requires the
 *      retained statement to BE the canonical one.
 *   3. **No authored ceiling.** If the row set shows fewer than `minDistinctSteps`
 *      distinct `steps` values AND fewer than `minDistinctLatencyMs` distinct
 *      `latencyMs` values, the baseline is `uniform-metrics`. Below `minRows` the rule
 *      cannot be evaluated (one row is trivially uniform), which is `insufficient-rows`
 *      -- a rejection, because unevaluable is not a pass (I-7).
 *
 * Every threshold comes from `infrastructure/quality/effectiveness-baseline.json` via
 * {@link parseBaselinePolicy}; this module contains no numeric literal of its own (AD-13).
 *
 * ## What the rules do and do not prove (I-7, stated plainly)
 *
 * No local schema rule can prove a number was measured -- a determined author can type
 * plausible numbers, a real harness version, a real seed, and a well-formed timestamp.
 * What these rules do is remove the *cheap* forgery and make the expensive one
 * checkable elsewhere: the exact shape the audit found (one steps value and one latency
 * value repeated across every row) is now unrepresentable in an accepted baseline, and
 * every row must assert a specific harness version, seed, and capture instant that a
 * CI job comparing the fresh run's stamps against the committed ones can contradict.
 * That cross-run comparison is CI's, not this module's; see the file header of
 * `frontend/spec/effectiveness/check-baseline.ts` for what is deferred and to whom.
 *
 * A rejected baseline is a first-class non-passing state ({@link BaselineVerdict}), never
 * a warning attached to a pass.
 */

import {
  EFFECTIVENESS_HARNESS_SEED,
  EFFECTIVENESS_HARNESS_VERSION,
  type EffectivenessScorecard,
  JOB_ORDER,
  type JobToBeDone,
  SCORECARD_SCHEMA_VERSION,
  SCRIPTED_PROXY_CEILING,
  type ScorecardRow,
} from "@lib/effectiveness-scorecard";
import { canonicalJson } from "@lib/json-canonical";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/**
 * A measured baseline row: a {@link ScorecardRow} that can name the run that produced
 * it (R8.10). The three stamps are REQUIRED here and optional on `ScorecardRow`,
 * which is the whole difference between a per-run scorecard and a committed baseline.
 */
export interface BaselineRow extends ScorecardRow {
  /** Harness version that measured this row (traceability, R8.10). */
  readonly harnessVersion: string;
  /** Seed of the scenario run that measured this row. */
  readonly seed: number;
  /** ISO-8601 UTC instant at which this row was captured. */
  readonly capturedAt: string;
}

/**
 * The committed baseline document: an {@link EffectivenessScorecard} whose rows are all
 * stamped. Assignable to `EffectivenessScorecard`, so the existing ratchet comparator
 * (`@lib/effectiveness-ratchet`) consumes an accepted baseline unchanged.
 */
export interface EffectivenessBaseline extends EffectivenessScorecard {
  readonly rows: readonly BaselineRow[];
}

/** The committed thresholds for the authored-ceiling rule (AD-13). */
export interface BaselinePolicy {
  /** Policy file schema version. */
  readonly version: number;
  /** Row count below which the distinctness rule is unevaluable. */
  readonly minRows: number;
  /** Distinct `steps` values the row set must exhibit. */
  readonly minDistinctSteps: number;
  /** Distinct `latencyMs` values the row set must exhibit. */
  readonly minDistinctLatencyMs: number;
}

/**
 * Why a baseline was rejected. `missing-stamp`, `absent-ceiling` and `uniform-metrics`
 * are the three modes R8.10 and Property 36 name; `insufficient-rows` is the
 * unevaluable case that would otherwise let a one-row baseline pass the distinctness
 * rule vacuously; `malformed` is a shape failure; `altered-ceiling` is raised only by
 * {@link checkCommittedBaseline}, which requires the canonical statement rather than
 * merely a present one.
 */
export type BaselineRejectionKind =
  | "malformed"
  | "missing-stamp"
  | "absent-ceiling"
  | "altered-ceiling"
  | "uniform-metrics"
  | "insufficient-rows";

/** One named reason a baseline is not a measurement. */
export interface BaselineRejection {
  readonly kind: BaselineRejectionKind;
  /** The row's job when the rejection is attributable to a row, else `null`. */
  readonly job: JobToBeDone | null;
  /** Human-readable detail naming what was observed. */
  readonly detail: string;
}

/**
 * The verdict of a baseline check. A rejection carries EVERY reason found, so one run
 * of the check reports the whole gap rather than the first one.
 */
export type BaselineVerdict =
  | {
      readonly outcome: "accepted";
      readonly baseline: EffectivenessBaseline;
      /**
       * Whether the retained statement is {@link SCRIPTED_PROXY_CEILING} itself.
       * Reported rather than enforced here: a generated or fixture baseline may carry
       * its own wording, while the COMMITTED artifact must carry the canonical one
       * (see {@link checkCommittedBaseline}).
       */
      readonly proxyCeilingIsCanonical: boolean;
    }
  | { readonly outcome: "rejected"; readonly rejections: readonly BaselineRejection[] };

// ---------------------------------------------------------------------------
// Policy (committed thresholds)
// ---------------------------------------------------------------------------

/**
 * Schema for `infrastructure/quality/effectiveness-baseline.json`. Both distinctness
 * minima and the row minimum are floored at 2: a committed `1` would satisfy any
 * single-valued column and switch the rule off from configuration, so the policy file
 * cannot weaken the rule below the point where it still catches an authored ceiling.
 */
const BaselinePolicySchema = z
  .object({
    $comment: z.array(z.string()).optional(),
    version: z.number().int().positive(),
    authored_ceiling: z
      .object({
        min_rows: z.number().int().min(2),
        min_distinct_steps: z.number().int().min(2),
        min_distinct_latency_ms: z.number().int().min(2),
      })
      .strict(),
  })
  .strict();

/**
 * Parses the committed policy from its JSON text, throwing a descriptive error rather
 * than falling back to a default: a missing or weakened policy file must stop the
 * check, never silently relax it (I-7).
 */
export function parseBaselinePolicy(text: string): BaselinePolicy {
  const parsed: unknown = JSON.parse(text);
  const result = BaselinePolicySchema.safeParse(parsed);
  if (!result.success) {
    throw new Error(`Invalid BaselinePolicy: ${result.error.message}`);
  }
  const rule = result.data.authored_ceiling;
  return {
    version: result.data.version,
    minRows: rule.min_rows,
    minDistinctSteps: rule.min_distinct_steps,
    minDistinctLatencyMs: rule.min_distinct_latency_ms,
  };
}

// ---------------------------------------------------------------------------
// Candidate document schema
// ---------------------------------------------------------------------------

/**
 * A declared Job_To_Be_Done, validated against `JOB_ORDER` rather than a second copy
 * of the five literals -- the enumerated job set keeps exactly one source of truth.
 */
const jobSchema: z.ZodType<JobToBeDone> = z.custom<JobToBeDone>(
  (value) => typeof value === "string" && (JOB_ORDER as readonly string[]).includes(value),
  { message: "not a declared Job_To_Be_Done" },
);

/**
 * A row as READ from a candidate baseline: the stamps are nullable and optional here so
 * that an unstamped row is a *semantic* rejection naming the missing stamp, rather than
 * an opaque shape error. `.strict()` keeps an unexpected key a shape failure.
 */
const CandidateRowSchema = z
  .object({
    job: jobSchema,
    steps: z.number().finite().nonnegative(),
    latencyMs: z.number().finite().nonnegative(),
    errorRate: z.number().finite().min(0).max(1),
    harnessVersion: z.string().nullable().optional(),
    seed: z.number().nullable().optional(),
    capturedAt: z.string().nullable().optional(),
  })
  .strict();

/** A candidate baseline document. `proxyCeiling` is nullable for the same reason. */
const CandidateBaselineSchema = z
  .object({
    schemaVersion: z.number().int().positive(),
    harnessVersion: z.string().min(1),
    seed: z.number().finite(),
    rows: z.array(CandidateRowSchema),
    interruptionPrecision: z.number().finite().min(0).max(1).nullable(),
    proxyCeiling: z.string().nullable().optional(),
  })
  .strict();

type CandidateRow = z.infer<typeof CandidateRowSchema>;

// ---------------------------------------------------------------------------
// Stamp predicates
// ---------------------------------------------------------------------------

/** Present, a string, and not whitespace-only. The trim TESTS; it never transforms. */
function isNonBlank(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

/** Present, numeric, and finite -- a seed that cannot be replayed is not a seed. */
function isReplayableSeed(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * ISO-8601 UTC to at most millisecond precision, e.g. `2026-06-17T09:41:02.184Z`. A
 * date-only string is rejected: "the timestamp of the run that produced that row"
 * (R8.10) identifies an instant, and a bare date is what a hand-authored stamp looks
 * like.
 */
const ISO_8601_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/;

function isCaptureInstant(value: unknown): value is string {
  return typeof value === "string" && ISO_8601_UTC.test(value) && !Number.isNaN(Date.parse(value));
}

/** The stamps this row cannot supply, named for the rejection detail. */
function stampProblems(row: CandidateRow): readonly string[] {
  const problems: string[] = [];
  if (!isNonBlank(row.harnessVersion)) problems.push("harnessVersion");
  if (!isReplayableSeed(row.seed)) problems.push("seed");
  if (!isCaptureInstant(row.capturedAt)) problems.push("capturedAt");
  return problems;
}

/** Narrows a candidate row to a {@link BaselineRow}, or `null` if a stamp is unusable. */
function asBaselineRow(row: CandidateRow): BaselineRow | null {
  const { harnessVersion, seed, capturedAt } = row;
  if (!isNonBlank(harnessVersion)) return null;
  if (!isReplayableSeed(seed)) return null;
  if (!isCaptureInstant(capturedAt)) return null;
  return {
    job: row.job,
    steps: row.steps,
    latencyMs: row.latencyMs,
    errorRate: row.errorRate,
    harnessVersion,
    seed,
    capturedAt,
  };
}

// ---------------------------------------------------------------------------
// The check
// ---------------------------------------------------------------------------

function distinctCount(values: readonly number[]): number {
  return new Set(values).size;
}

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/**
 * Validates a candidate baseline against R8.10. Pure and I/O-free: the shell that reads
 * the committed files is `frontend/spec/effectiveness/check-baseline.ts`, and the
 * property test (task 11.8, Property 36) drives this function directly.
 *
 * All applicable rejections are collected, so a baseline that is both unstamped and
 * uniform reports both.
 */
export function validateBaseline(candidate: unknown, policy: BaselinePolicy): BaselineVerdict {
  const parsed = CandidateBaselineSchema.safeParse(candidate);
  if (!parsed.success) {
    return {
      outcome: "rejected",
      rejections: [
        {
          kind: "malformed",
          job: null,
          detail: `not a baseline document: ${parsed.error.message}`,
        },
      ],
    };
  }
  const doc = parsed.data;
  const rejections: BaselineRejection[] = [];
  const stamped: BaselineRow[] = [];

  // Rule 1 -- per-row provenance.
  for (const row of doc.rows) {
    const measured = asBaselineRow(row);
    if (measured === null) {
      rejections.push({
        kind: "missing-stamp",
        job: row.job,
        detail:
          `row lacks a usable ${stampProblems(row).join(", ")}; a row that cannot name the ` +
          "run that produced it is not a measurement",
      });
      continue;
    }
    stamped.push(measured);
  }

  // Rule 2 -- the ceiling is retained, verbatim.
  const statement = isNonBlank(doc.proxyCeiling) ? doc.proxyCeiling : null;
  if (statement === null) {
    rejections.push({
      kind: "absent-ceiling",
      job: null,
      detail:
        "proxyCeiling is absent or blank; the Scripted_Proxy statement is part of the " +
        "artifact, not commentary about it",
    });
  }

  // Rule 3 -- no authored ceiling.
  if (doc.rows.length < policy.minRows) {
    rejections.push({
      kind: "insufficient-rows",
      job: null,
      detail:
        `${doc.rows.length} row(s) is below min_rows=${policy.minRows}, so the ` +
        "authored-ceiling rule cannot be evaluated; unevaluable is not a pass",
    });
  } else {
    const steps = distinctCount(doc.rows.map((row) => row.steps));
    const latency = distinctCount(doc.rows.map((row) => row.latencyMs));
    if (steps < policy.minDistinctSteps && latency < policy.minDistinctLatencyMs) {
      rejections.push({
        kind: "uniform-metrics",
        job: null,
        detail:
          `${doc.rows.length} rows show ${steps} distinct steps value(s) and ${latency} ` +
          `distinct latencyMs value(s), below min_distinct_steps=${policy.minDistinctSteps} ` +
          `and min_distinct_latency_ms=${policy.minDistinctLatencyMs}; identical steps and ` +
          "identical millisecond latencies on every row is an authored ceiling, not a measurement",
      });
    }
  }

  // `statement === null` implies a rejection above, so this is the accepted path only.
  if (rejections.length === 0 && statement !== null) {
    return {
      outcome: "accepted",
      baseline: {
        schemaVersion: doc.schemaVersion,
        harnessVersion: doc.harnessVersion,
        seed: doc.seed,
        rows: stamped,
        interruptionPrecision: doc.interruptionPrecision,
        // Verbatim: the string as read, untrimmed and never re-derived.
        proxyCeiling: statement,
      },
      proxyCeilingIsCanonical: statement === SCRIPTED_PROXY_CEILING,
    };
  }
  return { outcome: "rejected", rejections };
}

/**
 * {@link validateBaseline} over JSON text. Unparseable text is `malformed` rather than a
 * thrown error, so a caller reporting a verdict handles one shape for every failure.
 */
export function validateBaselineText(text: string, policy: BaselinePolicy): BaselineVerdict {
  let candidate: unknown;
  try {
    candidate = JSON.parse(text);
  } catch (err) {
    return {
      outcome: "rejected",
      rejections: [
        { kind: "malformed", job: null, detail: `not parseable as JSON: ${describeError(err)}` },
      ],
    };
  }
  return validateBaseline(candidate, policy);
}

/**
 * The rule for the COMMITTED artifact: everything {@link validateBaselineText} requires,
 * plus the retained statement must BE {@link SCRIPTED_PROXY_CEILING}. There is exactly
 * one correct Scripted_Proxy wording for the versioned baseline, and an edited one would
 * let the disclosure the audit credits be watered down a clause at a time while the
 * check kept passing.
 */
export function checkCommittedBaseline(text: string, policy: BaselinePolicy): BaselineVerdict {
  const verdict = validateBaselineText(text, policy);
  if (verdict.outcome === "rejected") return verdict;
  if (!verdict.proxyCeilingIsCanonical) {
    return {
      outcome: "rejected",
      rejections: [
        {
          kind: "altered-ceiling",
          job: null,
          detail:
            "proxyCeiling is present but is not the canonical SCRIPTED_PROXY_CEILING " +
            "statement; the committed baseline retains that statement verbatim",
        },
      ],
    };
  }
  return verdict;
}

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

/** Options for {@link buildBaseline}. */
export interface BuildBaselineOptions {
  readonly rows: readonly BaselineRow[];
  /** Defaults to {@link EFFECTIVENESS_HARNESS_SEED}. */
  readonly seed?: number;
  /** Defaults to {@link EFFECTIVENESS_HARNESS_VERSION}. */
  readonly harnessVersion?: string;
  /** Defaults to `null`. */
  readonly interruptionPrecision?: number | null;
}

/**
 * Builds a committed-baseline document from measured, stamped rows -- the only intended
 * way a baseline is produced. Rows are sorted into `JOB_ORDER` and the canonical
 * Scripted_Proxy statement is written verbatim, so the artifact this emits is exactly
 * what {@link checkCommittedBaseline} accepts. It cannot manufacture a stamp: the caller
 * must supply `harnessVersion`, `seed`, and `capturedAt` per row, and only a run has
 * them.
 */
export function buildBaseline(opts: BuildBaselineOptions): EffectivenessBaseline {
  const rank = (job: JobToBeDone): number => {
    const index = JOB_ORDER.indexOf(job);
    return index === -1 ? JOB_ORDER.length : index;
  };
  return {
    schemaVersion: SCORECARD_SCHEMA_VERSION,
    harnessVersion: opts.harnessVersion ?? EFFECTIVENESS_HARNESS_VERSION,
    seed: opts.seed ?? EFFECTIVENESS_HARNESS_SEED,
    rows: [...opts.rows].sort((a, b) => rank(a.job) - rank(b.job)),
    interruptionPrecision: opts.interruptionPrecision ?? null,
    proxyCeiling: SCRIPTED_PROXY_CEILING,
  };
}

/**
 * Canonical serialization of a baseline: sorted keys, no incidental whitespace, rows in
 * `JOB_ORDER`, so re-emitting the same measurement yields identical bytes (Req 4.6).
 */
export function serializeBaseline(baseline: EffectivenessBaseline): string {
  return canonicalJson(
    buildBaseline({
      rows: baseline.rows,
      seed: baseline.seed,
      harnessVersion: baseline.harnessVersion,
      interruptionPrecision: baseline.interruptionPrecision,
    }),
  );
}

/**
 * Packages loose parts into a candidate baseline document for {@link validateBaseline}.
 *
 * The interop seam for the Property 36 test (task 11.8): `baselineCaseArb` in
 * `frontend/spec/effectiveness/arbitraries.ts` yields `{ defect, rows, proxyCeiling }`,
 * where `rows` may be deliberately unstamped and `proxyCeiling` may be `null`. Neither
 * is a valid `BaselineRow`/`string`, which is the point -- so `rows` is `unknown[]` here
 * and the document is returned as `unknown`: the defects must survive as far as the
 * validator, not be typed out of existence on the way in.
 *
 * `defect` is generator metadata, not a document field, so it is deliberately absent
 * from the packaged document; the document schema is `.strict()` and would report an
 * unexpected key as `malformed`, masking the defect under test.
 */
export function assembleBaselineDocument(parts: {
  readonly rows: readonly unknown[];
  readonly proxyCeiling: string | null;
  readonly schemaVersion?: number;
  readonly harnessVersion?: string;
  readonly seed?: number;
  readonly interruptionPrecision?: number | null;
}): unknown {
  return {
    schemaVersion: parts.schemaVersion ?? SCORECARD_SCHEMA_VERSION,
    harnessVersion: parts.harnessVersion ?? EFFECTIVENESS_HARNESS_VERSION,
    seed: parts.seed ?? EFFECTIVENESS_HARNESS_SEED,
    rows: parts.rows,
    interruptionPrecision: parts.interruptionPrecision ?? null,
    proxyCeiling: parts.proxyCeiling,
  };
}
