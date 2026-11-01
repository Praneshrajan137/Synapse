// Interruption_Precision -- the North-Star effectiveness metric, computed from a run.
//
// WHY THIS MODULE WAS REBUILT (purpose-achievement-audit R8.5, task 11.5)
// ----------------------------------------------------------------------
// Of the decisions for which the Atlas_Console demanded human judgment
// (escalated / interrupted the operator), Interruption_Precision is the fraction
// whose review was WARRANTED -- the review changed the outcome, or it confirmed a
// genuinely uncertain, irreversible, or high-blast-radius decision:
//
//     Interruption_Precision = warranted / total
//
// The previous version of this file computed that ratio over a hand-authored
// array of four objects committed in this source file. The audit's finding was
// exact: the value was 0.75 BY CONSTRUCTION, the same array was duplicated in
// the spec, the committed baseline recorded the identical number, and the ratchet
// therefore compared a constant against itself. The formula was right and the
// measurement had never happened.
//
// So the committed list is gone. There is nothing left in this module to compute
// a precision FROM except a run's own collected interruptions. R8.5:
//
//   * the value SHALL be computed from interruptions raised during an executed run;
//   * it SHALL differ by at least `min_seed_divergence` between two seeds that
//     raise different interruption sets;
//   * IF it is reproducible from a committed list of warranted and unwarranted
//     interruptions without executing a run, the effectiveness job SHALL FAIL.
//
// THE FOUR MECHANISMS (not conventions)
// -------------------------------------
// A comment saying "do not hardcode this" is a convention. These are mechanisms:
// each one rejects an authored constant on the shape of its DERIVATION, so a
// hardcoded number that happens to equal the computed one is still rejected.
//
//  1. THE INPUT IS A SEALED RUN LEDGER, NOT AN ARRAY. `computeInterruptionPrecision`
//     accepts only a {@link SealedInterruptionLedger}. That type carries a brand
//     keyed by a module-private symbol, so no caller outside this file can write
//     one as an object literal -- the only two producers are
//     {@link openInterruptionLedger} (append-only, clock-stamped, one record per
//     observed interruption) and {@link deserializeSealedLedger} (which re-derives
//     the witness before it re-brands). Every record is bound to its run id and
//     seed, carries a contiguous observation index, a monotonic clock reading
//     inside the ledger's open/seal window, and a non-empty `evidence` string;
//     the whole body is covered by a recomputed {@link SealedInterruptionLedger.witness}.
//     Any of those checks failing yields `indeterminate` -- never a number.
//
//  2. SEED RESPONSIVENESS IS DIFFERENTIAL. {@link auditSeedResponsiveness} takes
//     two sealed ledgers from two seeds and fails unless the computed values
//     differ by at least the committed threshold. This is the mechanism that no
//     literal can satisfy and the reason a value-equal constant is still caught:
//     a constant returns the same number for both seeds, so its divergence is 0.
//     The threshold is not a literal here either -- it is read from
//     {@link INTERRUPTION_PRECISION_POLICY_RELPATH} through
//     {@link parseInterruptionPrecisionPolicy}, and the resulting policy is
//     branded the same way, so an in-code threshold cannot be passed instead.
//
//  3. A COMMITTED LIST IS DETECTABLE IN SOURCE. {@link findCommittedInterruptionLiterals}
//     is a pure scanner over source TEXT: it reports an authored warrant flag, a
//     committed interruption list, and a numeric literal assigned to the metric.
//     It judges the derivation, not the value, so a committed ratio is a finding
//     whether or not it also happens to be what the run measured.
//     {@link PRECISION_SCAN_SCOPE} declares the files that must scan clean, in
//     committed code rather than in a CI script's private argument list.
//
//  4. THE SCORECARD'S MEASURED INGRESS TAKES NO NUMBER. The value reaches the
//     Effectiveness_Scorecard only through
//     `@lib/effectiveness-scorecard::buildMeasuredScorecard`, which accepts a
//     {@link ComputedInterruptionPrecision} -- branded by a second module-private
//     symbol, so it too cannot be authored as a literal elsewhere, and its `run`
//     is the run that recorded the ledger, which is where that emitter reads the
//     scorecard's `seed` and `harnessVersion` from. Passing a number there is a
//     type error, and an `indeterminate` outcome cannot be narrowed to it at all:
//     {@link requireComputedOutcome} throws instead.
//
// WARRANT IS DERIVED, NOT ASSERTED
// --------------------------------
// A collector never states `warranted`. It records what it OBSERVED -- whether
// the review changed the decision's outcome, and which stakes the review
// confirmed -- and this module derives the warrant ({@link warrantOf}) and the
// boolean from it. R13.1's definition is encoded once, here, so a collector
// cannot quietly redefine "worth it".
//
// HONEST STATES (I-7)
// -------------------
// `total === 0` is `indeterminate/no-interruptions-collected`, not 0.0. A broken
// witness or provenance is `indeterminate`, not a best-effort number. An
// unreadable policy is `unavailable`, not a default. {@link requireComputedOutcome}
// throws rather than let a caller record a null into the scorecard where the
// ratchet would skip it -- that skip-as-pass is the hole the audit found.
//
// HONEST CEILING (Req 13.5 / 20.5)
// --------------------------------
// Even fully wired, this is measured over a Scripted_Proxy: seeded scenarios, not
// real operators. It shows an operator path exists and is efficient; it cannot
// model the false alarms and missed stakes a real operator experiences.
// {@link INTERRUPTION_PRECISION_PROXY_CEILING} extends the verbatim shared
// ceiling and travels with every computed outcome.
//
// WHAT THIS MODULE DOES NOT DO, AND WHO OWES IT
// ---------------------------------------------
// It does not observe interruptions and it does not run itself. Nothing here
// touches `window.__atlasHarness` (AD-12); every function is pure and total apart
// from the ledger's append and the clock it is handed. Two obligations therefore
// sit outside this file, and until they land the metric is honestly absent:
//
//   * COLLECTION -- `frontend/spec/effectiveness/harness.ts` (task 11.1) must
//     open a ledger per run and `record()` one observation per interruption the
//     Console raises. As committed it does not: no caller of
//     {@link openInterruptionLedger} exists anywhere yet.
//   * THE TWO CI STEPS -- the effectiveness job in
//     `.github/workflows/frontend.yml` (task 11.2) owes (a) a scan of
//     {@link PRECISION_SCAN_SCOPE} through {@link findCommittedInterruptionLiterals},
//     failing on any finding, and (b) two runs at two seeds, sealed and compared
//     through {@link auditSeedResponsiveness} against the committed policy, where
//     only `responsive` passes. Mechanisms 1 and 4 bind at compile time and at
//     compute time and need no job; mechanisms 2 and 3 are the falsifiers, and a
//     falsifier nobody runs proves nothing (I-7).

import { z } from "zod";

import { SCRIPTED_PROXY_CEILING } from "@lib/effectiveness-scorecard";
import { canonicalJson } from "@lib/json-canonical";

// ---------------------------------------------------------------------------
// The ratio kernel
// ---------------------------------------------------------------------------

/**
 * A single interruption the Atlas_Console raised -- a decision for which it
 * demanded human judgment -- reduced to the one bit the ratio needs.
 *
 * `warranted` is DERIVED by this module from observed evidence
 * ({@link warrantOf}); a collector supplies observations, never this flag. The
 * shape stays minimal so the ratio kernel below is total over any window,
 * including generated ones.
 */
export interface Interruption {
  readonly warranted: boolean;
}

/**
 * Interruption_Precision = warranted / total over a window (Req 13.1).
 *
 * The result always lies within `[0, 1]`. When the window is empty the ratio is
 * undefined, so this returns `null` rather than `0/0` or a fabricated 0. Pure
 * and total -- the single ratio implementation in the codebase; every other
 * function here routes through it so there is one definition to falsify.
 */
export function interruptionPrecision(interruptions: readonly Interruption[]): number | null {
  const total = interruptions.length;
  if (total === 0) return null;
  let warranted = 0;
  for (const interruption of interruptions) {
    if (interruption.warranted) warranted += 1;
  }
  return warranted / total;
}

const PRECISION_CEILING_TAIL =
  "Interruption_Precision inherits that ceiling: it is the warranted fraction of the " +
  "interruptions a SEEDED run raised, so it bounds the Console's behaviour on the scripted " +
  "paths and says nothing about the false alarms or missed stakes a real operator would meet.";

/**
 * The honest ceiling carried on every Interruption_Precision outcome (Req 13.5,
 * 20.5). Extends the shared verbatim {@link SCRIPTED_PROXY_CEILING} rather than
 * restating it, so the two statements cannot drift apart.
 */
export const INTERRUPTION_PRECISION_PROXY_CEILING = `${SCRIPTED_PROXY_CEILING} ${PRECISION_CEILING_TAIL}`;

// ---------------------------------------------------------------------------
// Observations -- what a collector records
// ---------------------------------------------------------------------------

/**
 * A stake the human review CONFIRMED as genuine (Req 13.1). Mirrors the
 * Expected_Review_Value escalation reasons (`irreversible`, `high-blast`,
 * low confidence -> `uncertain`) so the two models name the same stakes.
 */
export type ConfirmedStake = "uncertain" | "irreversible" | "high-blast";

/** Canonical stake ordering, so a record's stake list is byte-stable. */
const STAKE_ORDER: readonly ConfirmedStake[] = ["irreversible", "high-blast", "uncertain"];

/**
 * Why an interruption was (or was not) worth the operator's attention. Derived
 * from the observation by {@link warrantOf}; `unwarranted` is a false
 * interruption -- the Console demanded judgment and the review neither changed
 * the outcome nor confirmed a stake.
 */
export type WarrantKind =
  | "outcome-changed"
  | "confirmed-irreversible"
  | "confirmed-high-blast"
  | "confirmed-uncertain"
  | "unwarranted";

/** Every warrant kind, in reporting precedence order. */
export const WARRANT_KINDS: readonly WarrantKind[] = [
  "outcome-changed",
  "confirmed-irreversible",
  "confirmed-high-blast",
  "confirmed-uncertain",
  "unwarranted",
];

/**
 * What a collector observed about one interruption the Console raised. The
 * collector reports FACTS; the judgement is derived.
 *
 * `evidence` must be non-empty and must describe what was actually observed (the
 * announced text, the response that carried the changed outcome). An
 * interruption with no evidence is not an observation, so
 * {@link InterruptionLedger.record} refuses it rather than recording a phantom.
 */
export interface InterruptionObservation {
  /** Stable within the run; a repeat is refused rather than double-counted. */
  readonly interruptionId: string;
  /** The seeded scenario during which the Console raised it. */
  readonly scenarioId: string;
  /** True only when the review was OBSERVED to change the decision's outcome. */
  readonly outcomeChanged: boolean;
  /** Stakes the review confirmed, read from the decision under review. */
  readonly confirmedStakes: readonly ConfirmedStake[];
  /** What was observed, for diagnosis and audit. Must be non-empty. */
  readonly evidence: string;
}

/**
 * One interruption as recorded by a run: the observation plus the provenance the
 * ledger stamps on it. `warranted` and `warrant` are derived here, never
 * supplied.
 */
export interface CollectedInterruption extends Interruption {
  readonly interruptionId: string;
  /** The run that observed it; must equal the ledger's run id. */
  readonly runId: string;
  /** The run's seed, copied onto the record so a mixed-seed ledger is visible. */
  readonly seed: number;
  readonly scenarioId: string;
  /** Position in the run's append-only sequence, starting at 0. */
  readonly observationIndex: number;
  /** Monotonic clock reading inside the ledger's open/seal window. */
  readonly observedAtMs: number;
  readonly outcomeChanged: boolean;
  /** De-duplicated and ordered by {@link STAKE_ORDER}. */
  readonly confirmedStakes: readonly ConfirmedStake[];
  readonly warrant: WarrantKind;
  readonly evidence: string;
}

/**
 * Derive the warrant from observed facts (Req 13.1). Outcome-changing review is
 * the strongest evidence; otherwise the strongest confirmed stake is reported,
 * in the same precedence Expected_Review_Value uses (irreversible, then
 * high-blast, then uncertain). Pure and total.
 */
export function warrantOf(observation: InterruptionObservation): WarrantKind {
  if (observation.outcomeChanged) return "outcome-changed";
  const stakes = new Set<ConfirmedStake>(observation.confirmedStakes);
  if (stakes.has("irreversible")) return "confirmed-irreversible";
  if (stakes.has("high-blast")) return "confirmed-high-blast";
  if (stakes.has("uncertain")) return "confirmed-uncertain";
  return "unwarranted";
}

/** A warrant other than `unwarranted` means the interruption was worth it. */
export function isWarranted(warrant: WarrantKind): boolean {
  return warrant !== "unwarranted";
}

function normalizeStakes(stakes: readonly ConfirmedStake[]): readonly ConfirmedStake[] {
  const present = new Set<ConfirmedStake>(stakes);
  return STAKE_ORDER.filter((stake) => present.has(stake));
}

// ---------------------------------------------------------------------------
// The run ledger
// ---------------------------------------------------------------------------

/** Identity of the executed run an Interruption_Precision value belongs to. */
export interface RunContext {
  /** Unique per execution. A reused id across seeds makes a ledger pair invalid. */
  readonly runId: string;
  /** The run's seed (Req 8.10 reproducibility; R8.5 seed responsiveness). */
  readonly seed: number;
  /** The harness version that drove the run. */
  readonly harnessVersion: string;
  /** ISO-8601 start time of the run. */
  readonly startedAt: string;
}

/** Raised when the ledger is asked to record something it cannot honestly record. */
export class InterruptionLedgerError extends Error {
  constructor(message: string) {
    super(`Interruption_Precision ledger: ${message}`);
    this.name = "InterruptionLedgerError";
  }
}

/** Raised by {@link requireComputedPrecision} when no value was computed. */
export class InterruptionPrecisionUnavailableError extends Error {
  readonly reason: IndeterminateReason;

  constructor(reason: IndeterminateReason, detail: string) {
    super(`Interruption_Precision is not computable (${reason}): ${detail}`);
    this.name = "InterruptionPrecisionUnavailableError";
    this.reason = reason;
  }
}

/**
 * The append-only collector a run writes its interruptions into. Records cannot
 * be removed or edited, ids cannot repeat, and once {@link seal} is called no
 * further record is accepted -- so the sealed artifact is the run's whole and
 * final interruption set, not a curated subset.
 */
export interface InterruptionLedger {
  readonly run: RunContext;
  /** Append one observed interruption; returns the stamped record. */
  record(observation: InterruptionObservation): CollectedInterruption;
  /** Everything recorded so far, oldest first. */
  collected(): readonly CollectedInterruption[];
  /** Close the ledger and derive its witness. Idempotent. */
  seal(): SealedInterruptionLedger;
}

// The brand is module-private ON PURPOSE: an interface member keyed by a symbol
// this module does not export cannot be written by any other file, so a
// `SealedInterruptionLedger` cannot be authored as a literal elsewhere. The only
// producers are `seal()` and `deserializeSealedLedger()`, and both derive the
// witness. Reaching around it needs a double cast through `unknown`, which is
// visible in review and still leaves the witness and provenance checks to pass.
const LEDGER_BRAND: unique symbol = Symbol("synapse.interruption-precision.sealed-ledger");

/** Bumped when the sealed-ledger shape changes; old witnesses stop verifying. */
export const SEALED_LEDGER_VERSION = 1;

/**
 * A run's closed interruption set: the records, the window they were observed
 * in, and a witness over the whole body. This is the ONLY input
 * {@link computeInterruptionPrecision} accepts.
 */
export interface SealedInterruptionLedger {
  readonly [LEDGER_BRAND]: true;
  readonly run: RunContext;
  readonly interruptions: readonly CollectedInterruption[];
  /** Clock reading when the ledger was opened. */
  readonly openedAtMs: number;
  /** Clock reading when it was sealed. */
  readonly sealedAtMs: number;
  /**
   * Digest over `{version, run, interruptions, openedAtMs, sealedAtMs}`.
   * Tamper-EVIDENT, not tamper-proof: it is a non-cryptographic digest computed
   * in-process (no dependency, I-1), so it catches an edited or reassembled
   * artifact, not a determined forger who recomputes it. The falsifier a forger
   * still cannot satisfy is seed responsiveness ({@link auditSeedResponsiveness}).
   */
  readonly witness: string;
}

interface LedgerBody {
  readonly run: RunContext;
  readonly interruptions: readonly CollectedInterruption[];
  readonly openedAtMs: number;
  readonly sealedAtMs: number;
}

/** FNV-1a-style 64-bit digest over UTF-16 code units. Deterministic, no deps. */
function digest(text: string): string {
  let low = 0x811c9dc5;
  let high = 0x01000193;
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    low = Math.imul(low ^ code, 0x01000193) >>> 0;
    high = Math.imul((((high << 5) | (high >>> 27)) >>> 0) ^ code, 0x85ebca6b) >>> 0;
  }
  const hex = (value: number): string => value.toString(16).padStart(8, "0");
  return `fnv1a64:${hex(low)}${hex(high)}`;
}

function witnessOf(body: LedgerBody): string {
  return digest(canonicalJson({ version: SEALED_LEDGER_VERSION, ...body }));
}

function monotonicNow(): number {
  return typeof performance === "undefined" ? Date.now() : performance.now();
}

/**
 * Open an append-only ledger for one executed run (R8.5 "raised during an
 * executed run"). `clock` is injectable so a driver can supply a monotonic
 * source; it defaults to `performance.now()` where available.
 *
 * The returned ledger stamps each record with the run binding, a contiguous
 * observation index, and a clock reading, and refuses an observation that is
 * unrecordable (blank id, blank scenario, blank evidence, repeated id) rather
 * than recording something it did not observe.
 */
export function openInterruptionLedger(
  run: RunContext,
  clock: () => number = monotonicNow,
): InterruptionLedger {
  if (run.runId.trim().length === 0) {
    throw new InterruptionLedgerError("a run must carry a non-empty runId");
  }
  if (!Number.isFinite(run.seed)) {
    throw new InterruptionLedgerError(`run "${run.runId}" carries a non-finite seed`);
  }
  const openedAtMs = clock();
  const collected: CollectedInterruption[] = [];
  const seenIds = new Set<string>();
  let sealedLedger: SealedInterruptionLedger | null = null;

  return {
    run,

    record(observation: InterruptionObservation): CollectedInterruption {
      if (sealedLedger !== null) {
        throw new InterruptionLedgerError(
          `run "${run.runId}" is sealed; an interruption observed after the seal cannot be ` +
            "back-dated into the measured window",
        );
      }
      if (observation.interruptionId.trim().length === 0) {
        throw new InterruptionLedgerError("an interruption must carry a non-empty interruptionId");
      }
      if (seenIds.has(observation.interruptionId)) {
        throw new InterruptionLedgerError(
          `interruption "${observation.interruptionId}" was already recorded in run ` +
            `"${run.runId}"; a repeat would double-count one interruption`,
        );
      }
      if (observation.scenarioId.trim().length === 0) {
        throw new InterruptionLedgerError(
          `interruption "${observation.interruptionId}" names no scenario, so it cannot be ` +
            "attributed to anything the run drove",
        );
      }
      if (observation.evidence.trim().length === 0) {
        throw new InterruptionLedgerError(
          `interruption "${observation.interruptionId}" carries no evidence; an interruption ` +
            "with nothing observed behind it is not an observation (I-7)",
        );
      }
      const warrant = warrantOf(observation);
      const stamped: CollectedInterruption = {
        interruptionId: observation.interruptionId,
        runId: run.runId,
        seed: run.seed,
        scenarioId: observation.scenarioId,
        observationIndex: collected.length,
        observedAtMs: clock(),
        outcomeChanged: observation.outcomeChanged,
        confirmedStakes: normalizeStakes(observation.confirmedStakes),
        warrant,
        warranted: isWarranted(warrant),
        evidence: observation.evidence,
      };
      collected.push(stamped);
      seenIds.add(stamped.interruptionId);
      return stamped;
    },

    collected(): readonly CollectedInterruption[] {
      return [...collected];
    },

    seal(): SealedInterruptionLedger {
      const existing = sealedLedger;
      if (existing !== null) return existing;
      const body: LedgerBody = {
        run,
        interruptions: [...collected],
        openedAtMs,
        sealedAtMs: clock(),
      };
      const artifact: SealedInterruptionLedger = {
        [LEDGER_BRAND]: true,
        ...body,
        witness: witnessOf(body),
      };
      sealedLedger = artifact;
      return artifact;
    },
  };
}

// ---------------------------------------------------------------------------
// Crossing the browser -> runner boundary
// ---------------------------------------------------------------------------

const ConfirmedStakeSchema = z.enum(["uncertain", "irreversible", "high-blast"]);

const WarrantKindSchema = z.enum([
  "outcome-changed",
  "confirmed-irreversible",
  "confirmed-high-blast",
  "confirmed-uncertain",
  "unwarranted",
]);

const RunContextSchema = z
  .object({
    runId: z.string().min(1),
    seed: z.number().finite(),
    harnessVersion: z.string().min(1),
    startedAt: z.string().min(1),
  })
  .strict();

const CollectedInterruptionSchema = z
  .object({
    interruptionId: z.string().min(1),
    runId: z.string().min(1),
    seed: z.number().finite(),
    scenarioId: z.string().min(1),
    observationIndex: z.number().int().nonnegative(),
    observedAtMs: z.number().finite(),
    outcomeChanged: z.boolean(),
    confirmedStakes: z.array(ConfirmedStakeSchema),
    warrant: WarrantKindSchema,
    warranted: z.boolean(),
    evidence: z.string().min(1),
  })
  .strict();

const SealedLedgerArtifactSchema = z
  .object({
    version: z.literal(SEALED_LEDGER_VERSION),
    run: RunContextSchema,
    interruptions: z.array(CollectedInterruptionSchema),
    openedAtMs: z.number().finite(),
    sealedAtMs: z.number().finite(),
    witness: z.string().min(1),
  })
  .strict();

/**
 * Canonical serialization of a sealed ledger (sorted keys, no incidental
 * whitespace) so the artifact a browser run writes is byte-stable and the
 * witness is reproducible on the other side of the boundary.
 */
export function serializeSealedLedger(ledger: SealedInterruptionLedger): string {
  return canonicalJson({
    version: SEALED_LEDGER_VERSION,
    run: ledger.run,
    interruptions: ledger.interruptions,
    openedAtMs: ledger.openedAtMs,
    sealedAtMs: ledger.sealedAtMs,
    witness: ledger.witness,
  });
}

/** Outcome of loading a serialized ledger. `unavailable` is never a pass (I-7). */
export type SealedLedgerLoadOutcome =
  | { readonly status: "loaded"; readonly ledger: SealedInterruptionLedger }
  | { readonly status: "unavailable"; readonly detail: string };

/**
 * Parse, validate and re-witness a serialized ledger -- the only way a sealed
 * ledger produced in the browser becomes one the runner can compute over.
 *
 * The witness is recomputed here and again in
 * {@link computeInterruptionPrecision}: this function refuses an artifact whose
 * body does not match its witness, so a hand-edited or hand-assembled JSON file
 * cannot enter the pipeline just because it type-checks.
 */
export function deserializeSealedLedger(text: string): SealedLedgerLoadOutcome {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", detail: `ledger artifact is not JSON: ${detail}` };
  }
  const parsed = SealedLedgerArtifactSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      status: "unavailable",
      detail: `ledger artifact failed validation: ${parsed.error.message}`,
    };
  }
  const body: LedgerBody = {
    run: parsed.data.run,
    interruptions: parsed.data.interruptions,
    openedAtMs: parsed.data.openedAtMs,
    sealedAtMs: parsed.data.sealedAtMs,
  };
  const recomputed = witnessOf(body);
  if (recomputed !== parsed.data.witness) {
    return {
      status: "unavailable",
      detail:
        `ledger artifact witness does not cover its body: recorded ${parsed.data.witness}, ` +
        `derived ${recomputed}`,
    };
  }
  return { status: "loaded", ledger: { [LEDGER_BRAND]: true, ...body, witness: recomputed } };
}

// ---------------------------------------------------------------------------
// Computing the metric
// ---------------------------------------------------------------------------

/** Why no Interruption_Precision value exists. Each is a first-class state (I-7). */
export type IndeterminateReason =
  /** The run executed but raised no interruption: warranted / 0 is undefined. */
  | "no-interruptions-collected"
  /** The body does not match its witness -- the set was edited or assembled. */
  | "witness-mismatch"
  /** A record is not attributable to the run that claims to have observed it. */
  | "provenance-broken";

// Mechanism 4's brand, module-private for the same reason `LEDGER_BRAND` is: the
// scorecard's measured ingress accepts only this type, and no file outside this
// one can write a member keyed by a symbol this module does not export. So a
// hand-authored `{status: "computed", value: <a number>, ...}` is not assignable
// to it, and the only producer is `computeInterruptionPrecision` below -- which
// re-derives the witness and the provenance before it brands anything.
const COMPUTED_BRAND: unique symbol = Symbol("synapse.interruption-precision.computed");

/** A computed Interruption_Precision value with the provenance that produced it. */
export interface ComputedInterruptionPrecision {
  readonly [COMPUTED_BRAND]: true;
  readonly status: "computed";
  /** warranted / total, in `[0, 1]`. */
  readonly value: number;
  readonly warranted: number;
  readonly total: number;
  /** The run this value belongs to; a value never travels without it. */
  readonly run: RunContext;
  /** The witness of the ledger it was computed from. */
  readonly witness: string;
  /** How many interruptions fell into each warrant kind, for diagnosis. */
  readonly warrantCounts: Readonly<Record<WarrantKind, number>>;
  readonly proxyCeiling: string;
}

/** No value could be computed. Non-passing; never rendered as a number. */
export interface IndeterminateInterruptionPrecision {
  readonly status: "indeterminate";
  readonly reason: IndeterminateReason;
  readonly detail: string;
  readonly proxyCeiling: string;
}

export type InterruptionPrecisionOutcome =
  | ComputedInterruptionPrecision
  | IndeterminateInterruptionPrecision;

function indeterminate(
  reason: IndeterminateReason,
  detail: string,
): IndeterminateInterruptionPrecision {
  return {
    status: "indeterminate",
    reason,
    detail,
    proxyCeiling: INTERRUPTION_PRECISION_PROXY_CEILING,
  };
}

/**
 * The provenance every record must satisfy before it may contribute to the
 * ratio. Returns the first failure, naming the record, or `null` when the whole
 * set is attributable to the run.
 */
function provenanceFailure(ledger: SealedInterruptionLedger): string | null {
  const { run, interruptions, openedAtMs, sealedAtMs } = ledger;
  if (!(sealedAtMs >= openedAtMs)) {
    return `run "${run.runId}" sealed at ${sealedAtMs} before it opened at ${openedAtMs}`;
  }
  const seenIds = new Set<string>();
  let previousAtMs = openedAtMs;
  for (let index = 0; index < interruptions.length; index += 1) {
    const record = interruptions[index];
    if (record === undefined) {
      return `run "${run.runId}" has a hole at observation index ${index}`;
    }
    if (record.observationIndex !== index) {
      return (
        `interruption "${record.interruptionId}" claims observation index ` +
        `${record.observationIndex} at position ${index}; the sequence a run appends is contiguous`
      );
    }
    if (record.runId !== run.runId) {
      return (
        `interruption "${record.interruptionId}" is bound to run "${record.runId}", not to ` +
        `"${run.runId}" -- it was not observed by this run`
      );
    }
    if (record.seed !== run.seed) {
      return (
        `interruption "${record.interruptionId}" carries seed ${record.seed} in a run seeded ` +
        `${run.seed}`
      );
    }
    if (seenIds.has(record.interruptionId)) {
      return `interruption "${record.interruptionId}" appears twice in run "${run.runId}"`;
    }
    seenIds.add(record.interruptionId);
    if (record.evidence.trim().length === 0) {
      return `interruption "${record.interruptionId}" carries no observed evidence`;
    }
    if (record.observedAtMs < previousAtMs || record.observedAtMs > sealedAtMs) {
      return (
        `interruption "${record.interruptionId}" was stamped ${record.observedAtMs}, outside the ` +
        `run's monotonic window [${previousAtMs}, ${sealedAtMs}]`
      );
    }
    previousAtMs = record.observedAtMs;
    const derived = warrantOf(record);
    if (derived !== record.warrant) {
      return (
        `interruption "${record.interruptionId}" records warrant "${record.warrant}" but its ` +
        `observed facts derive "${derived}"`
      );
    }
    if (record.warranted !== isWarranted(record.warrant)) {
      return (
        `interruption "${record.interruptionId}" disagrees with its own warrant ` +
        `"${record.warrant}"`
      );
    }
  }
  return null;
}

function countWarrants(
  interruptions: readonly CollectedInterruption[],
): Readonly<Record<WarrantKind, number>> {
  const counts: Record<WarrantKind, number> = {
    "outcome-changed": 0,
    "confirmed-irreversible": 0,
    "confirmed-high-blast": 0,
    "confirmed-uncertain": 0,
    unwarranted: 0,
  };
  for (const record of interruptions) {
    counts[record.warrant] += 1;
  }
  return counts;
}

/**
 * Compute Interruption_Precision over ONE run's collected interruptions
 * (R8.5, Req 13.1, 13.2).
 *
 * The value is `warranted / total` through the shared {@link interruptionPrecision}
 * kernel, and it is returned only when the ledger is attributable to the run
 * that claims to have produced it: the witness must cover the body, every record
 * must be bound to the run id and seed, the observation sequence must be
 * contiguous and monotonic inside the open/seal window, evidence must be
 * present, and each recorded warrant must equal the warrant its own observed
 * facts derive. Otherwise the outcome is `indeterminate` -- a first-class
 * non-passing state, never a substituted number (I-7).
 */
export function computeInterruptionPrecision(
  ledger: SealedInterruptionLedger,
): InterruptionPrecisionOutcome {
  const recomputed = witnessOf({
    run: ledger.run,
    interruptions: ledger.interruptions,
    openedAtMs: ledger.openedAtMs,
    sealedAtMs: ledger.sealedAtMs,
  });
  if (recomputed !== ledger.witness) {
    return indeterminate(
      "witness-mismatch",
      `run "${ledger.run.runId}" records witness ${ledger.witness} but its body derives ` +
        `${recomputed}; the interruption set was edited or assembled after the run`,
    );
  }
  const failure = provenanceFailure(ledger);
  if (failure !== null) return indeterminate("provenance-broken", failure);

  const value = interruptionPrecision(ledger.interruptions);
  if (value === null) {
    return indeterminate(
      "no-interruptions-collected",
      `run "${ledger.run.runId}" (seed ${ledger.run.seed}) raised no interruption, so ` +
        "warranted / total is undefined; there is no value to record",
    );
  }
  let warranted = 0;
  for (const record of ledger.interruptions) {
    if (record.warranted) warranted += 1;
  }
  // Annotated rather than returned inline so the brand is checked against the
  // one type that declares it, with no reliance on union contextual typing.
  const computed: ComputedInterruptionPrecision = {
    [COMPUTED_BRAND]: true,
    status: "computed",
    value,
    warranted,
    total: ledger.interruptions.length,
    run: ledger.run,
    witness: ledger.witness,
    warrantCounts: countWarrants(ledger.interruptions),
    proxyCeiling: INTERRUPTION_PRECISION_PROXY_CEILING,
  };
  return computed;
}

/**
 * The computed outcome, or a throw naming why there is none -- the narrowing the
 * scorecard's measured ingress requires (mechanism 4).
 *
 * The scorecard's `interruptionPrecision` field is nullable, and the ratchet
 * skips the comparison when either side is null -- which is exactly how "never
 * measured" became "gate passed". So there is deliberately no way to turn an
 * `indeterminate` outcome into a recordable value: an emitter either holds a
 * branded {@link ComputedInterruptionPrecision} or the effectiveness job fails
 * with the reason named (R8.5, R8.2, I-7).
 */
export function requireComputedOutcome(
  outcome: InterruptionPrecisionOutcome,
): ComputedInterruptionPrecision {
  if (outcome.status === "computed") return outcome;
  throw new InterruptionPrecisionUnavailableError(outcome.reason, outcome.detail);
}

/**
 * The value, or a throw naming why there is none. Delegates to
 * {@link requireComputedOutcome} so there is one throw path; use it where a bare
 * ratio is genuinely what a caller needs (a report line, a log field) rather than
 * the scorecard field, which takes the outcome itself.
 */
export function requireComputedPrecision(outcome: InterruptionPrecisionOutcome): number {
  return requireComputedOutcome(outcome).value;
}

// ---------------------------------------------------------------------------
// The committed threshold
// ---------------------------------------------------------------------------

/** Where the committed threshold lives, relative to the repository root. */
export const INTERRUPTION_PRECISION_POLICY_RELPATH =
  "infrastructure/quality/effectiveness-precision.json";

const POLICY_BRAND: unique symbol = Symbol("synapse.interruption-precision.policy");

/**
 * The committed policy {@link auditSeedResponsiveness} compares against. Branded
 * with a module-private symbol so the only way to obtain one is
 * {@link parseInterruptionPrecisionPolicy} over the committed file's bytes -- an
 * in-code threshold cannot be passed in its place.
 */
export interface InterruptionPrecisionPolicy {
  readonly [POLICY_BRAND]: true;
  /** Minimum absolute difference two seeds must produce (R8.5). */
  readonly minSeedDivergence: number;
  /** The file the value came from, carried so a report can name its source. */
  readonly source: string;
}

const PolicyFileSchema = z
  .object({
    $comment: z.array(z.string()).optional(),
    version: z.number().int().positive(),
    interruption_precision: z
      .object({
        min_seed_divergence: z.number().finite().gt(0).lte(1),
        unit: z.string().min(1).optional(),
        requirement: z.string().min(1).optional(),
        read_by: z.array(z.string()).optional(),
      })
      .strict(),
  })
  .strict();

/** Outcome of loading the committed policy. `unavailable` is never a pass (I-7). */
export type PolicyLoadOutcome =
  | { readonly status: "loaded"; readonly policy: InterruptionPrecisionPolicy }
  | { readonly status: "unavailable"; readonly detail: string };

/**
 * Validate the committed threshold file's text into a policy.
 *
 * Takes TEXT, not a path: this module stays browser-safe and I/O-free, and the
 * caller (a CI runner) supplies
 * `readFileSync(INTERRUPTION_PRECISION_POLICY_RELPATH, "utf-8")`. There is no
 * default: an absent or malformed policy is reported `unavailable` so the job
 * fails rather than proceeding against an invented threshold.
 */
export function parseInterruptionPrecisionPolicy(
  text: string,
  source: string = INTERRUPTION_PRECISION_POLICY_RELPATH,
): PolicyLoadOutcome {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", detail: `${source} is not JSON: ${detail}` };
  }
  const parsed = PolicyFileSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      status: "unavailable",
      detail: `${source} failed validation: ${parsed.error.message}`,
    };
  }
  return {
    status: "loaded",
    policy: {
      [POLICY_BRAND]: true,
      minSeedDivergence: parsed.data.interruption_precision.min_seed_divergence,
      source,
    },
  };
}

// ---------------------------------------------------------------------------
// Mechanism 2: seed responsiveness
// ---------------------------------------------------------------------------

/** One side of the seed-responsiveness probe. */
export interface SeedProbe {
  readonly runId: string;
  readonly seed: number;
  readonly value: number;
  readonly total: number;
  readonly witness: string;
}

/**
 * `responsive` is the only passing status. `unresponsive` is the literal's
 * signature: the value did not move when its inputs did. `inapplicable` means
 * the probe could not decide -- also non-passing, because R8.5 requires the
 * difference to be DEMONSTRATED, and an undecided probe demonstrates nothing.
 */
export type SeedResponsivenessStatus = "responsive" | "unresponsive" | "inapplicable";

export type SeedResponsivenessReason =
  | "value-responded"
  | "value-did-not-respond"
  | "precision-indeterminate"
  | "same-seed"
  | "same-run"
  | "identical-interruption-sets";

export interface SeedResponsivenessVerdict {
  readonly status: SeedResponsivenessStatus;
  readonly reason: SeedResponsivenessReason;
  readonly detail: string;
  /** `|left - right|`, or null when one side produced no value. */
  readonly divergence: number | null;
  readonly minSeedDivergence: number;
  readonly policySource: string;
  readonly left: SeedProbe | null;
  readonly right: SeedProbe | null;
}

/**
 * The content of a run's interruption set that a judgement depends on: which
 * scenario raised each interruption and what warrant it earned. Per-run ids and
 * clock stamps are excluded on purpose -- they always differ between runs, and
 * including them would make every pair "different" and the check vacuous.
 */
function interruptionSetKey(interruptions: readonly CollectedInterruption[]): string {
  return canonicalJson(
    [...interruptions].map((record) => `${record.scenarioId}|${record.warrant}`).sort(),
  );
}

function probeOf(outcome: ComputedInterruptionPrecision): SeedProbe {
  return {
    runId: outcome.run.runId,
    seed: outcome.run.seed,
    value: outcome.value,
    total: outcome.total,
    witness: outcome.witness,
  };
}

/**
 * Two seeds, two runs, one question: did the value respond to its inputs?
 * (R8.5's second and third clauses.)
 *
 * This is the mechanism a literal cannot pass, and the reason a hardcoded number
 * that happens to equal a measured one is still rejected: a constant is seed-
 * invariant, so its divergence is 0 and the verdict is `unresponsive` naming both
 * seeds, both values, and the committed threshold.
 *
 * A pair that cannot decide the question is `inapplicable`, not a pass: the same
 * seed on both sides, the same run twice, an indeterminate side, or two runs that
 * happened to raise the same scenario/warrant content. `inapplicable` obliges the
 * caller to pick a probe pair that does raise different sets -- it never excuses
 * the check.
 */
export function auditSeedResponsiveness(
  left: SealedInterruptionLedger,
  right: SealedInterruptionLedger,
  policy: InterruptionPrecisionPolicy,
): SeedResponsivenessVerdict {
  const base = {
    minSeedDivergence: policy.minSeedDivergence,
    policySource: policy.source,
  } as const;

  const noValue = (
    side: "left" | "right",
    failing: IndeterminateInterruptionPrecision,
    other: ComputedInterruptionPrecision | null,
  ): SeedResponsivenessVerdict => {
    const probe = other === null ? null : probeOf(other);
    return {
      ...base,
      status: "inapplicable",
      reason: "precision-indeterminate",
      detail:
        `the ${side} run produced no value (${failing.reason}: ${failing.detail}), so no seed ` +
        "difference can be demonstrated",
      divergence: null,
      left: side === "left" ? null : probe,
      right: side === "right" ? null : probe,
    };
  };

  const leftOutcome = computeInterruptionPrecision(left);
  const rightOutcome = computeInterruptionPrecision(right);
  if (leftOutcome.status === "indeterminate") {
    return noValue("left", leftOutcome, rightOutcome.status === "computed" ? rightOutcome : null);
  }
  if (rightOutcome.status === "indeterminate") {
    return noValue("right", rightOutcome, leftOutcome);
  }

  const leftProbe = probeOf(leftOutcome);
  const rightProbe = probeOf(rightOutcome);
  const pair = { ...base, left: leftProbe, right: rightProbe };

  if (leftProbe.runId === rightProbe.runId) {
    return {
      ...pair,
      status: "inapplicable",
      reason: "same-run",
      detail: `both sides are run "${leftProbe.runId}"; two executed runs are required`,
      divergence: 0,
    };
  }
  if (leftProbe.seed === rightProbe.seed) {
    return {
      ...pair,
      status: "inapplicable",
      reason: "same-seed",
      detail: `both runs are seeded ${leftProbe.seed}; R8.5 compares two DIFFERENT seeds`,
      divergence: Math.abs(leftProbe.value - rightProbe.value),
    };
  }
  if (interruptionSetKey(left.interruptions) === interruptionSetKey(right.interruptions)) {
    return {
      ...pair,
      status: "inapplicable",
      reason: "identical-interruption-sets",
      detail:
        `seeds ${leftProbe.seed} and ${rightProbe.seed} raised the same scenario/warrant ` +
        "content, so this pair cannot show the value responding; probe with seeds that raise " +
        "different interruption sets",
      divergence: Math.abs(leftProbe.value - rightProbe.value),
    };
  }

  const divergence = Math.abs(leftProbe.value - rightProbe.value);
  if (divergence >= policy.minSeedDivergence) {
    return {
      ...pair,
      status: "responsive",
      reason: "value-responded",
      detail:
        `seed ${leftProbe.seed} measured ${leftProbe.value} over ${leftProbe.total} ` +
        `interruption(s) and seed ${rightProbe.seed} measured ${rightProbe.value} over ` +
        `${rightProbe.total}; divergence ${divergence} >= ${policy.minSeedDivergence}`,
      divergence,
    };
  }
  return {
    ...pair,
    status: "unresponsive",
    reason: "value-did-not-respond",
    detail:
      `seeds ${leftProbe.seed} and ${rightProbe.seed} raised different interruption sets but ` +
      `measured ${leftProbe.value} and ${rightProbe.value}; divergence ${divergence} < ` +
      `${policy.minSeedDivergence} (${policy.source}). Either the reported value is not derived ` +
      "from the collected interruptions, or this probe pair's warranted fractions coincide -- " +
      "both are failures of the probe, not results to accept",
    divergence,
  };
}

// ---------------------------------------------------------------------------
// Mechanism 3: a committed list is detectable in source
// ---------------------------------------------------------------------------

/**
 * The files that must contain no committed interruption data, declared in code
 * so the scan scope is reviewable rather than a CI script's private argument.
 * Paths are relative to the repository root.
 *
 * The four files are the whole derivation path: where the ratio is defined, where
 * the value lands, where interruptions are collected, and where the scorecard is
 * emitted. `frontend/tests/e2e/task-completion.jtbd.spec.ts` is the last of
 * those, and as committed it still carries the four-object mirror of the deleted
 * list the audit named ("the same array is duplicated in the spec"), so the scan
 * reports findings there on the day it first runs. That is R8.5's finding
 * becoming mechanical, not a defect in the scanner: it clears when task 11.2's
 * emitter records observations instead of mirroring a list. A finding is a failed
 * result, never a warning attached to a pass (I-7).
 *
 * Deliberately EXCLUDED: `frontend/spec/effectiveness/scorecard.baseline.json`
 * and `frontend/spec/effectiveness/run-ratchet.ts`. A committed baseline
 * legitimately records measured numbers, and the ratchet compares two artifacts
 * rather than deriving anything; whether a committed number is a measurement or
 * an authored ceiling is R8.10's question, answered by the baseline check (task
 * 11.7), not by a source scan.
 *
 * Named without "interruption" on purpose: the scanner below flags a non-empty
 * array literal bound to an interruption-named identifier or annotation, and this
 * file is in its own scope, so the declaration would flag itself. Being
 * constrained by its own detector is the point.
 */
export const PRECISION_SCAN_SCOPE: readonly string[] = [
  "frontend/src/lib/interruption-precision.ts",
  "frontend/src/lib/effectiveness-scorecard.ts",
  "frontend/spec/effectiveness/harness.ts",
  "frontend/tests/e2e/task-completion.jtbd.spec.ts",
];

/** What a scan found. Each kind is a way to state the metric without deriving it. */
export type CommittedLiteralKind =
  /** A judgement asserted as a boolean literal instead of observed. */
  | "authored-warrant-flag"
  /** A committed array of interruptions -- the shape this module used to ship. */
  | "committed-interruption-list"
  /** The metric assigned a numeric literal. */
  | "hardcoded-precision-value";

export interface CommittedLiteralFinding {
  readonly kind: CommittedLiteralKind;
  /** 1-based line number in the scanned text. */
  readonly line: number;
  /** The offending line, trimmed and capped, so a report can quote it. */
  readonly excerpt: string;
}

// Each pattern targets the SHAPE of a derivation, not a value, which is why a
// hardcoded number equal to the measured one is still a finding. None of these
// matches this module's own source (the patterns' own text is not a match: the
// escape sequences break every candidate, and an EMPTY array literal -- the
// ledger's own accumulator -- is excluded by the trailing non-`]` character), so
// this file scans clean, a self-check the property test for R8.5 can assert.
const AUTHORED_FLAG_PATTERNS: readonly RegExp[] = [
  /\bwarranted\s*:\s*(?:true|false)\b/g,
  /\boutcomeChanged\s*:\s*(?:true|false)\b/g,
];
// Two shapes, both case-INSENSITIVE and both requiring a non-empty literal. The
// case-insensitivity is not cosmetic: the mirror the audit found duplicated in
// `task-completion.jtbd.spec.ts` is bound to a SCREAMING_CASE name, which a
// `[Ii]nterruption` pattern reads straight past. The second shape catches the
// same data bound to a name that says nothing, with the type annotation naming
// it instead. `[^=;]` bounds both to a single statement, so neither can run past
// a `;` into an unrelated assignment further down the file.
const COMMITTED_LIST_PATTERNS: readonly RegExp[] = [
  /\b(?:const|let|var|readonly)\s+[\w$]*interruption[\w$]*\s*(?::[^=;]*)?=\s*\[\s*[^\s\]]/gi,
  /\b(?:const|let|var|readonly)\s+[\w$]+\s*:[^=;]*interruption[^=;]*=\s*\[\s*[^\s\]]/gi,
];
const HARDCODED_VALUE_PATTERN = /\binterruption[_-]?precision\b"?\s*[:=]\s*-?\d/gi;

function lineNumberOf(text: string, index: number): number {
  let line = 1;
  const limit = Math.min(index, text.length);
  for (let cursor = 0; cursor < limit; cursor += 1) {
    if (text.charCodeAt(cursor) === 10) line += 1;
  }
  return line;
}

function excerptAt(text: string, index: number): string {
  const start = text.lastIndexOf("\n", index) + 1;
  const end = text.indexOf("\n", index);
  const raw = text.slice(start, end === -1 ? text.length : end).trim();
  return raw.length > 120 ? `${raw.slice(0, 117)}...` : raw;
}

function collectMatches(
  text: string,
  pattern: RegExp,
  kind: CommittedLiteralKind,
  into: CommittedLiteralFinding[],
): void {
  // A fresh RegExp per scan: `lastIndex` on a shared global regex would make the
  // scanner order-dependent, and an order-dependent detector is not a mechanism.
  const scanner = new RegExp(pattern.source, pattern.flags);
  for (;;) {
    const match = scanner.exec(text);
    if (match === null) return;
    into.push({
      kind,
      line: lineNumberOf(text, match.index),
      excerpt: excerptAt(text, match.index),
    });
    if (scanner.lastIndex === match.index) scanner.lastIndex += 1;
  }
}

/**
 * Find committed interruption data in a module's source text (R8.5's third
 * clause).
 *
 * Pure: takes text, does no I/O, so it runs in the browser, in Vitest, and in a
 * CI runner that reads the files in {@link PRECISION_SCAN_SCOPE} with `utf-8`
 * (E-S13-07). A non-empty result means the metric is reproducible without
 * executing a run, which R8.5 makes a failed result for the effectiveness job.
 *
 * One finding per (kind, line): the two committed-list shapes overlap on the
 * commonest spelling, and reporting the same line twice would inflate a count a
 * report is entitled to read as "how many places".
 *
 * Known limits, stated rather than implied: it reads syntax, so it catches the
 * authored shapes the audit actually found and not an arbitrary encoding of the
 * same data (a base64 blob, a value computed from string lengths). Seed
 * responsiveness is the check that does not care how the constant is spelled.
 */
export function findCommittedInterruptionLiterals(
  source: string,
): readonly CommittedLiteralFinding[] {
  const findings: CommittedLiteralFinding[] = [];
  for (const pattern of AUTHORED_FLAG_PATTERNS) {
    collectMatches(source, pattern, "authored-warrant-flag", findings);
  }
  for (const pattern of COMMITTED_LIST_PATTERNS) {
    collectMatches(source, pattern, "committed-interruption-list", findings);
  }
  collectMatches(source, HARDCODED_VALUE_PATTERN, "hardcoded-precision-value", findings);
  const seen = new Set<string>();
  const unique = findings.filter((finding) => {
    const key = `${finding.kind}@${finding.line}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return unique.sort((a, b) =>
    a.line === b.line ? a.kind.localeCompare(b.kind) : a.line - b.line,
  );
}
