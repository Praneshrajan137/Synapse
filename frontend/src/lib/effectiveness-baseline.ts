/**
 * Effectiveness_Baseline -- the schema and the check for the COMMITTED effectiveness
 * baseline (purpose-achievement-audit R8.10; design E6; ADR-059).
 *
 * ## Why this module exists separately from `@lib/effectiveness-scorecard`
 *
 * A *scorecard* is what one run emits. A *baseline* is what the repository commits and
 * ratchets against, and it is strictly stronger: the audit's finding is that the committed
 * baseline "is not a measurement: all five jobs carry identical `steps: 20`,
 * `latencyMs: 15000`, `errorRate: 0` -- authored ceilings". A hand-typed baseline is
 * byte-indistinguishable from a measured one under the scorecard schema, which accepts any
 * five well-typed numbers. So the baseline gets its own schema and its own check, and
 * `@lib/effectiveness-scorecard` keeps owning the per-run shape.
 *
 * ## The format: k legs of one commit (schema version 2, ADR-059)
 *
 * A baseline is measured by `EFFECTIVENESS_LEG_COUNT` (k) harness legs of one commit, and it
 * keeps what the ratchet's median rule recomputes: each row's k latency samples, one per leg,
 * each with the instant its leg captured the row. The row's `latencyMs` is the median of those
 * samples. It is kept so that the authored-ceiling rule, and every reader of `rows[].latencyMs`,
 * see the value the ratchet compares. `steps` and `errorRate` are single values because the k
 * legs had to agree on them (`poolLegs` in `@lib/effectiveness-ratchet`). The document names the
 * commit the legs measured (`commitSha`) and the leg count (`legCount`).
 *
 * The one-run format, schema version 1, is REFUSED BY NAME (`one-run-format`) and never read:
 * one run's millisecond latency cannot carry a 10% comparison (finding 88's strict A/A moved two
 * of five JTBD latencies by more than that at one sha), so accepting it would restore the
 * comparison ADR-059 retires.
 *
 * ## The rules (R8.10, Property 36)
 *
 *   1. **Provenance.** Every row carries `harnessVersion` and `seed`, every latency sample
 *      carries `capturedAt` (ISO-8601 UTC), and the document carries a 40-character
 *      `commitSha`. Something that cannot name the run that produced it is not a measurement,
 *      so a missing stamp is `missing-stamp`. R8.10's capture stamp per row became one per
 *      sample: k instants where there was one, which is stricter, not weaker.
 *   2. **The leg set.** `legCount` is k, and every row holds exactly one sample from each of
 *      legs 1..k (`leg-set`).
 *   3. **The median.** A row's `latencyMs` is the median of its samples (`median-mismatch`). Not
 *      evaluated on a row whose leg set already failed: the median of the wrong samples means
 *      nothing.
 *   4. **The ceiling is retained.** `proxyCeiling` must be present and non-blank, and it is kept
 *      **verbatim** -- read through untouched, never trimmed, normalized, re-wrapped, or
 *      re-derived from {@link SCRIPTED_PROXY_CEILING}. The audit credits that disclosure;
 *      silently regenerating it would turn a retained statement into a manufactured one.
 *      `isNonBlank` trims only to TEST, never to transform. The stricter committed-artifact rule
 *      additionally requires the retained statement to BE the canonical one.
 *   5. **No authored ceiling.** If the row set shows fewer than `minDistinctSteps` distinct
 *      `steps` values AND fewer than `minDistinctLatencyMs` distinct `latencyMs` values, the
 *      baseline is `uniform-metrics`. Below `minRows` the rule cannot be evaluated (one row is
 *      trivially uniform), which is `insufficient-rows` -- a rejection, because unevaluable is not
 *      a pass (I-7).
 *
 * Every threshold of rule 5 comes from `infrastructure/quality/effectiveness-baseline.json` via
 * {@link parseBaselinePolicy} (AD-13). k comes from `@lib/effectiveness-ratchet`, the module whose
 * rule needs it, so this check and the comparator cannot disagree about it.
 *
 * ## What the rules do and do not prove (I-7, stated plainly)
 *
 * No local schema rule can prove a number was measured -- a determined author can type plausible
 * numbers, a real harness version, a real seed, a real commit and well-formed timestamps. What
 * these rules do is remove the *cheap* forgery and make the expensive one checkable elsewhere: the
 * exact shape the audit found is unrepresentable in an accepted baseline, a one-run baseline is
 * refused by name, and every sample asserts a leg, an instant and a commit that a reader can hold
 * against the CI run whose `effectiveness-baseline-candidate` artifact the file came from.
 * {@link buildBaseline} is the only intended way a baseline is made, and it refuses anything but
 * k agreeing legs that passed the arrival proof.
 *
 * A rejected baseline is a first-class non-passing state ({@link BaselineVerdict}), never a
 * warning attached to a pass.
 */

import {
  type ArrivalFailure,
  EFFECTIVENESS_LEG_COUNT,
  type LatencySample,
  type LegDisagreement,
  type LegScorecard,
  checkLegArrival,
  isCommitSha,
  median,
  poolLegs,
} from "@lib/effectiveness-ratchet";
import {
  EFFECTIVENESS_HARNESS_SEED,
  EFFECTIVENESS_HARNESS_VERSION,
  type EffectivenessScorecard,
  JOB_ORDER,
  type JobToBeDone,
  SCRIPTED_PROXY_CEILING,
  type ScorecardRow,
} from "@lib/effectiveness-scorecard";
import { canonicalJson } from "@lib/json-canonical";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/** The committed baseline's schema version: k legs of one commit (ADR-059). */
export const BASELINE_SCHEMA_VERSION = 2;

/**
 * The superseded one-run format. A document carrying it is refused by name
 * (`one-run-format`) before any of its numbers is read.
 */
export const ONE_RUN_BASELINE_SCHEMA_VERSION = 1;

/**
 * A measured baseline row: one job measured by k legs that agreed on everything but latency
 * (R8.10, ADR-059). `latencyMs` is the median of `latencySamples`.
 */
export interface BaselineRow extends ScorecardRow {
  /** Harness version that measured this row. */
  readonly harnessVersion: string;
  /** Seed of the scenario that measured this row, identical in every leg. */
  readonly seed: number;
  /** One sample per leg 1..k, each with the instant its leg captured the row. */
  readonly latencySamples: readonly LatencySample[];
}

/**
 * The committed baseline document. Assignable to `EffectivenessScorecard`, and to the
 * `KSampleMeasurement` that `compareLegMedians` reads.
 */
export interface EffectivenessBaseline extends EffectivenessScorecard {
  /** The commit all k legs measured. */
  readonly commitSha: string;
  /** k, the number of legs behind every row. */
  readonly legCount: number;
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
 * Why a baseline was rejected. `missing-stamp`, `absent-ceiling` and `uniform-metrics` are the
 * three modes R8.10 and Property 36 name. `one-run-format`, `leg-set` and `median-mismatch` are
 * ADR-059's: the superseded format, a sample set other than legs 1..k, and a row latency that is
 * not its samples' median. `insufficient-rows` is the unevaluable case that would otherwise let a
 * one-row baseline pass the distinctness rule vacuously; `malformed` is a shape failure;
 * `altered-ceiling` is raised only by {@link checkCommittedBaseline}, which requires the canonical
 * statement rather than merely a present one.
 */
export type BaselineRejectionKind =
  | "malformed"
  | "one-run-format"
  | "missing-stamp"
  | "leg-set"
  | "median-mismatch"
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
 * The verdict of a baseline check. A rejection carries EVERY reason found, so one run of the
 * check reports the whole gap rather than the first one.
 */
export type BaselineVerdict =
  | {
      readonly outcome: "accepted";
      readonly baseline: EffectivenessBaseline;
      /**
       * Whether the retained statement is {@link SCRIPTED_PROXY_CEILING} itself. Reported rather
       * than enforced here: a generated or fixture baseline may carry its own wording, while the
       * COMMITTED artifact must carry the canonical one (see {@link checkCommittedBaseline}).
       */
      readonly proxyCeilingIsCanonical: boolean;
    }
  | { readonly outcome: "rejected"; readonly rejections: readonly BaselineRejection[] };

// ---------------------------------------------------------------------------
// Policy (committed thresholds)
// ---------------------------------------------------------------------------

/**
 * Schema for `infrastructure/quality/effectiveness-baseline.json`. Both distinctness minima and
 * the row minimum are floored at 2: a committed `1` would satisfy any single-valued column and
 * switch the rule off from configuration, so the policy file cannot weaken the rule below the
 * point where it still catches an authored ceiling.
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
 * Parses the committed policy from its JSON text, throwing a descriptive error rather than
 * falling back to a default: a missing or weakened policy file must stop the check, never
 * silently relax it (I-7).
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
 * A declared Job_To_Be_Done, validated against `JOB_ORDER` rather than a second copy of the five
 * literals -- the enumerated job set keeps exactly one source of truth.
 */
const jobSchema: z.ZodType<JobToBeDone> = z.custom<JobToBeDone>(
  (value) => typeof value === "string" && (JOB_ORDER as readonly string[]).includes(value),
  { message: "not a declared Job_To_Be_Done" },
);

/**
 * A latency sample as READ from a candidate. `leg` is any number and `capturedAt` is nullable and
 * optional, so a wrong leg or a missing instant is a *semantic* rejection that names it rather
 * than an opaque shape error.
 */
const CandidateSampleSchema = z
  .object({
    leg: z.number(),
    latencyMs: z.number().finite().nonnegative(),
    capturedAt: z.string().nullable().optional(),
  })
  .strict();

/**
 * A row as READ from a candidate baseline: the stamps are nullable and optional for the same
 * reason. `.strict()` keeps an unexpected key a shape failure, so a one-run row carrying its own
 * `capturedAt` and no samples is `malformed` under the k-leg version, never half-read.
 */
const CandidateRowSchema = z
  .object({
    job: jobSchema,
    steps: z.number().finite().nonnegative(),
    latencyMs: z.number().finite().nonnegative(),
    errorRate: z.number().finite().min(0).max(1),
    harnessVersion: z.string().nullable().optional(),
    seed: z.number().nullable().optional(),
    latencySamples: z.array(CandidateSampleSchema),
  })
  .strict();

/** A candidate k-leg baseline document. `commitSha` and `proxyCeiling` are loose for the same reason. */
const CandidateBaselineSchema = z
  .object({
    schemaVersion: z.literal(BASELINE_SCHEMA_VERSION),
    harnessVersion: z.string().min(1),
    seed: z.number().finite(),
    commitSha: z.string().nullable().optional(),
    legCount: z.number().int(),
    rows: z.array(CandidateRowSchema),
    interruptionPrecision: z.number().finite().min(0).max(1).nullable(),
    proxyCeiling: z.string().nullable().optional(),
  })
  .strict();

/** Matches any object whose `schemaVersion` is the one-run format's, whatever else it holds. */
const OneRunFormatProbe = z.object({ schemaVersion: z.literal(ONE_RUN_BASELINE_SCHEMA_VERSION) });

type CandidateRow = z.infer<typeof CandidateRowSchema>;
type CandidateSample = z.infer<typeof CandidateSampleSchema>;

/** Why the one-run format is refused, for the rejection detail. */
const ONE_RUN_DETAIL = `schemaVersion ${ONE_RUN_BASELINE_SCHEMA_VERSION} is the one-run baseline format, which ADR-059 retires: one run's millisecond latency cannot carry a 10% comparison. Commit the k-leg candidate (the effectiveness-baseline-candidate artifact) instead`;

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
 * ISO-8601 UTC to at most millisecond precision, e.g. `2026-06-17T09:41:02.184Z`. A date-only
 * string is rejected: "the timestamp of the run that produced that row" (R8.10) identifies an
 * instant, and a bare date is what a hand-authored stamp looks like.
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
  const unstamped = row.latencySamples
    .filter((sample) => !isCaptureInstant(sample.capturedAt))
    .map((sample) => sample.leg);
  if (unstamped.length > 0) {
    problems.push(`capturedAt on the sample(s) of leg(s) ${unstamped.join(", ")}`);
  }
  return problems;
}

/** Why a row's samples are not exactly one from each of legs 1..k, or `null` when they are. */
function legSetProblem(samples: readonly CandidateSample[], legCount: number): string | null {
  const legs = samples.map((sample) => sample.leg);
  const sorted = [...legs].sort((a, b) => a - b);
  if (sorted.length === legCount && sorted.every((leg, at) => leg === at + 1)) return null;
  return (
    `the row's samples name legs [${legs.join(", ")}]; a ${legCount}-leg baseline holds ` +
    `exactly one sample from each of legs 1..${legCount}`
  );
}

/** Narrows a candidate row to a {@link BaselineRow}, or `null` if any stamp is unusable. */
function asBaselineRow(row: CandidateRow): BaselineRow | null {
  const { harnessVersion, seed } = row;
  if (!isNonBlank(harnessVersion)) return null;
  if (!isReplayableSeed(seed)) return null;
  const latencySamples: LatencySample[] = [];
  for (const sample of row.latencySamples) {
    const { capturedAt } = sample;
    if (!isCaptureInstant(capturedAt)) return null;
    latencySamples.push({ leg: sample.leg, latencyMs: sample.latencyMs, capturedAt });
  }
  return {
    job: row.job,
    steps: row.steps,
    latencyMs: row.latencyMs,
    errorRate: row.errorRate,
    harnessVersion,
    seed,
    latencySamples,
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
 * Validates a candidate baseline against R8.10 and ADR-059. Pure and I/O-free: the shell that
 * reads the committed files is `frontend/spec/effectiveness/check-baseline.ts`, and the property
 * test (Property 36) drives this function directly.
 *
 * A one-run document is refused by name before anything else is read. Otherwise every
 * applicable rejection is collected, so a baseline that is both unstamped and uniform reports
 * both.
 */
export function validateBaseline(candidate: unknown, policy: BaselinePolicy): BaselineVerdict {
  if (OneRunFormatProbe.safeParse(candidate).success) {
    return {
      outcome: "rejected",
      rejections: [{ kind: "one-run-format", job: null, detail: ONE_RUN_DETAIL }],
    };
  }
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

  // Rules 1 and 2, document level -- the commit, and the design's leg count.
  const commitSha =
    typeof doc.commitSha === "string" && isCommitSha(doc.commitSha) ? doc.commitSha : null;
  if (commitSha === null) {
    rejections.push({
      kind: "missing-stamp",
      job: null,
      detail:
        "commitSha is absent or not a 40-character lowercase hex sha; a baseline that cannot " +
        "name the commit its legs measured is not a measurement",
    });
  }
  if (doc.legCount !== EFFECTIVENESS_LEG_COUNT) {
    rejections.push({
      kind: "leg-set",
      job: null,
      detail: `legCount is ${doc.legCount} and this gate judges ${EFFECTIVENESS_LEG_COUNT} legs per row (ADR-059); a baseline measured under another design is not comparable`,
    });
  }

  // Rules 1, 2 and 3, per row -- provenance, the leg set, and the median.
  for (const row of doc.rows) {
    const holes = stampProblems(row);
    if (holes.length > 0) {
      rejections.push({
        kind: "missing-stamp",
        job: row.job,
        detail: `row lacks a usable ${holes.join(", ")}; a row that cannot name the run that produced it is not a measurement`,
      });
    }
    const legProblem = legSetProblem(row.latencySamples, EFFECTIVENESS_LEG_COUNT);
    if (legProblem !== null) {
      rejections.push({ kind: "leg-set", job: row.job, detail: legProblem });
    } else {
      const center = median(row.latencySamples.map((sample) => sample.latencyMs));
      if (row.latencyMs !== center) {
        rejections.push({
          kind: "median-mismatch",
          job: row.job,
          detail: `latencyMs is ${row.latencyMs} and the median of its samples is ${center}; a row's latency is the median the ratchet compares, never a separate number`,
        });
      }
    }
    const measured = asBaselineRow(row);
    if (measured !== null) stamped.push(measured);
  }

  // Rule 4 -- the ceiling is retained, verbatim.
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

  // Rule 5 -- no authored ceiling.
  if (doc.rows.length < policy.minRows) {
    rejections.push({
      kind: "insufficient-rows",
      job: null,
      detail: `${doc.rows.length} row(s) is below min_rows=${policy.minRows}, so the authored-ceiling rule cannot be evaluated; unevaluable is not a pass`,
    });
  } else {
    const steps = distinctCount(doc.rows.map((row) => row.steps));
    const latency = distinctCount(doc.rows.map((row) => row.latencyMs));
    if (steps < policy.minDistinctSteps && latency < policy.minDistinctLatencyMs) {
      rejections.push({
        kind: "uniform-metrics",
        job: null,
        detail: `${doc.rows.length} rows show ${steps} distinct steps value(s) and ${latency} distinct latencyMs value(s), below min_distinct_steps=${policy.minDistinctSteps} and min_distinct_latency_ms=${policy.minDistinctLatencyMs}; identical steps and identical millisecond latencies on every row is an authored ceiling, not a measurement`,
      });
    }
  }

  // `statement` and `commitSha` are null only after a rejection above, so this is the accepted
  // path only, and every row narrowed because no `missing-stamp` was recorded.
  if (rejections.length === 0 && statement !== null && commitSha !== null) {
    return {
      outcome: "accepted",
      baseline: {
        schemaVersion: doc.schemaVersion,
        harnessVersion: doc.harnessVersion,
        seed: doc.seed,
        commitSha,
        legCount: doc.legCount,
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
 * {@link validateBaseline} over JSON text. Unparseable text is `malformed` rather than a thrown
 * error, so a caller reporting a verdict handles one shape for every failure.
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
 * The rule for the COMMITTED artifact: everything {@link validateBaselineText} requires, plus the
 * retained statement must BE {@link SCRIPTED_PROXY_CEILING}. There is exactly one correct
 * Scripted_Proxy wording for the versioned baseline, and an edited one would let the disclosure
 * the audit credits be watered down a clause at a time while the check kept passing.
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

/** What {@link buildBaseline} made, or why it would not make one. */
export type BaselineBuild =
  | { readonly outcome: "built"; readonly baseline: EffectivenessBaseline }
  | {
      readonly outcome: "refused";
      /** Why the legs did not prove arrival; empty when they did. */
      readonly arrival: readonly ArrivalFailure[];
      /** Where the arrived legs disagreed; empty when they agreed or did not arrive. */
      readonly disagreements: readonly LegDisagreement[];
    };

/**
 * Builds a committed-baseline document from k legs' scorecards -- the only intended way a
 * baseline is made (ADR-059). It runs the arrival proof and the pooling itself, so it cannot be
 * fed fewer than k legs, a repeated leg, two commits, or legs that disagree on a deterministic
 * metric. Rows come out in `JOB_ORDER`, samples in leg order, each row's `latencyMs` is the
 * median of its samples, and the canonical Scripted_Proxy statement is written verbatim, so the
 * document is exactly what {@link checkCommittedBaseline} accepts. It cannot manufacture a stamp:
 * every harness version, seed, capture instant and the commit come from the legs, and only a run
 * has them.
 */
export function buildBaseline(legs: readonly LegScorecard[]): BaselineBuild {
  const arrival = checkLegArrival(legs, EFFECTIVENESS_LEG_COUNT);
  if (arrival.outcome === "refused") {
    return { outcome: "refused", arrival: arrival.failures, disagreements: [] };
  }
  const pooled = poolLegs(arrival);
  if (pooled.outcome === "disagreed") {
    return { outcome: "refused", arrival: [], disagreements: pooled.disagreements };
  }
  const measurement = pooled.measurement;
  return {
    outcome: "built",
    baseline: {
      schemaVersion: BASELINE_SCHEMA_VERSION,
      harnessVersion: measurement.harnessVersion,
      seed: measurement.seed,
      commitSha: measurement.commitSha,
      legCount: measurement.legCount,
      rows: measurement.rows.map((row) => ({
        job: row.job,
        steps: row.steps,
        latencyMs: median(row.latencySamples.map((sample) => sample.latencyMs)),
        errorRate: row.errorRate,
        harnessVersion: row.harnessVersion,
        seed: row.seed,
        latencySamples: row.latencySamples,
      })),
      interruptionPrecision: measurement.interruptionPrecision,
      proxyCeiling: SCRIPTED_PROXY_CEILING,
    },
  };
}

/**
 * Canonical serialization of a baseline: sorted keys, no incidental whitespace, rows in
 * `JOB_ORDER` and samples in leg order, so re-emitting the same measurement yields identical
 * bytes (Req 4.6).
 */
export function serializeBaseline(baseline: EffectivenessBaseline): string {
  const rank = (job: JobToBeDone): number => {
    const index = JOB_ORDER.indexOf(job);
    return index === -1 ? JOB_ORDER.length : index;
  };
  return canonicalJson({
    ...baseline,
    rows: [...baseline.rows]
      .sort((a, b) => rank(a.job) - rank(b.job))
      .map((row) => ({
        ...row,
        latencySamples: [...row.latencySamples].sort((a, b) => a.leg - b.leg),
      })),
  });
}

/**
 * Packages loose parts into a candidate baseline document for {@link validateBaseline}.
 *
 * The interop seam for the Property 36 test: the test spreads `baselineCaseArb`'s rows
 * (`frontend/spec/effectiveness/arbitraries.ts`) over k samples and may leave a stamp, a sample
 * or the commit deliberately unusable. None of that is a valid `BaselineRow`, which is the point
 * -- so `rows` is `unknown[]` here and the document is returned as `unknown`: the defects must
 * survive as far as the validator, not be typed out of existence on the way in. `commitSha` has
 * no default, because a default commit would be a stamp this module manufactured.
 */
export function assembleBaselineDocument(parts: {
  readonly rows: readonly unknown[];
  readonly proxyCeiling: string | null;
  readonly commitSha: string | null;
  readonly schemaVersion?: number;
  readonly legCount?: number;
  readonly harnessVersion?: string;
  readonly seed?: number;
  readonly interruptionPrecision?: number | null;
}): unknown {
  return {
    schemaVersion: parts.schemaVersion ?? BASELINE_SCHEMA_VERSION,
    harnessVersion: parts.harnessVersion ?? EFFECTIVENESS_HARNESS_VERSION,
    seed: parts.seed ?? EFFECTIVENESS_HARNESS_SEED,
    commitSha: parts.commitSha,
    legCount: parts.legCount ?? EFFECTIVENESS_LEG_COUNT,
    rows: parts.rows,
    interruptionPrecision: parts.interruptionPrecision ?? null,
    proxyCeiling: parts.proxyCeiling,
  };
}
