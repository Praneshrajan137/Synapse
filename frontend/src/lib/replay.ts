// FE-INV-028 / FE-INV-009: deterministic decision replay.
//
// Given a ConsensusDecision and a phase index, returns the UI slice that
// represents the system's state at that phase boundary. Pure — no
// Date.now(), no Math.random(), no I/O — so loading the same decision
// twice produces byte-identical renders (FE-INV-009). Every helper in this
// module is a total, referentially-transparent function so the replay
// surfaces (Decision Theater detail + Council Theater choreography) share a
// single, property-testable source of truth and can never drift.

import type { ConsensusDecision, Proposal } from "@domain/consensus-decision";
import type { Tier } from "@domain/primitives";

// ── Phase model ──────────────────────────────────────────────────────────

export const MIN_PHASE = 1;
export const MAX_PHASE = 5;
export type PhaseIndex = 1 | 2 | 3 | 4 | 5;

const PHASE_NAMES = ["proposal", "debate", "arbitration", "execution", "learning"] as const;
export type PhaseName = (typeof PHASE_NAMES)[number];

export function phaseName(index: PhaseIndex): PhaseName {
  // `index - 1` is bounded to [0, 4] by the literal-type parameter, so the
  // lookup is always defined. The intermediate `as` avoids a Biome-flagged
  // non-null assertion while preserving the precise PhaseName return type.
  return PHASE_NAMES[index - 1] as PhaseName;
}

/**
 * Clamp any real number to a valid phase index in [1, 5]. Non-finite inputs
 * (NaN, ±∞) collapse to the lower bound so the result is always a concrete
 * PhaseIndex — the total function the replay slicer and phase-param parser
 * both build on.
 */
export function clampPhase(n: number): PhaseIndex {
  if (!Number.isFinite(n)) return MIN_PHASE;
  const floored = Math.floor(n);
  return Math.max(MIN_PHASE, Math.min(MAX_PHASE, floored)) as PhaseIndex;
}

/**
 * FE-INV-028 — resolve the active replay phase from a `?phase=` URL search
 * parameter. A numeric value is clamped into [1, 5] (validate/clamp); an
 * absent, empty, or non-numeric value falls back to the decision's terminal
 * phase (itself clamped defensively). Pure and total, so a shared link parks
 * on a deterministic frame.
 */
export function parseReplayPhase(
  param: string | null | undefined,
  terminalPhase: number,
): PhaseIndex {
  const fallback = clampPhase(terminalPhase);
  if (param == null) return fallback;
  const trimmed = param.trim();
  if (trimmed === "") return fallback;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return fallback;
  return clampPhase(parsed);
}

/**
 * Presence-aware variant of {@link parseReplayPhase}. Returns a clamped
 * PhaseIndex when the parameter is a usable number, or `undefined` when it is
 * absent/invalid. The Council Theater uses `undefined` to mean "no shared
 * frame — auto-narrate from phase 1" while a valid value parks playback.
 */
export function parseSharedPhase(param: string | null | undefined): PhaseIndex | undefined {
  if (param == null) return undefined;
  const trimmed = param.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return undefined;
  return clampPhase(parsed);
}

// ── Tier-aware tool visibility (FE-INV-018 / ADR-022) ──────────────────────

/** Prefix marking a reinforcement-learning tool, the only kind low tiers show. */
export const RL_TOOL_PREFIX = "rl_";

/** Tier ordinal at/above which the full toolset becomes visible. */
export const FULL_TOOLSET_MIN_TIER = 3;

/**
 * Ordinal [1..4] for a decision tier. Accepts the `tier_N` enum form or a bare
 * number; anything unrecognised clamps into [1, 4] so the function is total.
 */
export function tierOrdinal(tier: Tier | number): 1 | 2 | 3 | 4 {
  const raw = typeof tier === "number" ? tier : Number.parseInt(tier.replace("tier_", ""), 10);
  const n = Number.isFinite(raw) ? Math.floor(raw) : 1;
  return Math.max(1, Math.min(4, n)) as 1 | 2 | 3 | 4;
}

/**
 * FE-INV-018 — tier-aware tool visibility. Tiers 1–2 expose only `rl_*` tools
 * (the RL fast path never invokes the LLM toolset); tier ≥ 3 exposes the full
 * recorded toolset. Pure, order-preserving, and never fabricates a tool that
 * was not in the input list.
 */
export function visibleTools(tier: Tier | number, tools: readonly string[]): ReadonlyArray<string> {
  if (tierOrdinal(tier) >= FULL_TOOLSET_MIN_TIER) return tools.slice();
  return tools.filter((t) => t.startsWith(RL_TOOL_PREFIX));
}

// ── Replay slice ───────────────────────────────────────────────────────────

export interface ReplaySlice {
  readonly phase: PhaseIndex;
  readonly proposalsVisible: ReadonlyArray<Proposal>;
  readonly selectedAction: Record<string, unknown> | null;
  readonly confidenceAtPhase: number;
  readonly debateRoundsCompleted: number;
  readonly auditTraceSoFar: ReadonlyArray<string>;
  readonly humanOverride: Record<string, unknown> | null;
  readonly executionConfirmations: ReadonlyArray<string>;
}

export function replayDecision(decision: ConsensusDecision, phaseIndex: number): ReplaySlice {
  const clamped = clampPhase(phaseIndex);
  const proposals = decision.proposals;
  // Phase 1 surfaces only "proposed" + "rejected" entries (initial offerings).
  // Phase 2 reveals debate rounds (already encoded as proposal status updates).
  // Phase 3 marks selection; phase 4 binds executor confirmations; phase 5
  // is post-hoc learning context.
  const visible = proposals.filter((p) => {
    if (clamped >= 3) return true;
    return (p.status ?? "proposed") === "proposed";
  });
  const selectedAction = clamped >= 3 ? decision.selected_action : null;
  const confidenceAtPhase = clamped >= 3 ? decision.confidence : 0;
  const traceCutoff = Math.min(decision.audit_trace.length, clamped * 2);
  const trace = decision.audit_trace.slice(0, traceCutoff);
  const debateRounds = clamped >= 2 ? decision.debate_rounds : 0;
  const humanOverride =
    clamped >= 4 ? ((decision.human_override ?? null) as Record<string, unknown> | null) : null;
  const confirmations = clamped >= 4 ? decision.execution_confirmations : [];
  return {
    phase: clamped,
    proposalsVisible: visible,
    selectedAction,
    confidenceAtPhase,
    debateRoundsCompleted: debateRounds,
    auditTraceSoFar: trace,
    humanOverride,
    executionConfirmations: confirmations,
  };
}

// ── Council reconstruction fidelity (FE-INV-045) ────────────────────────────

/** Debate reconstruction: a recorded transcript or an explicit fast-path gap. */
export type DebateReconstruction =
  | { readonly kind: "recorded"; readonly rounds: number; readonly transcriptLength: number }
  | { readonly kind: "empty"; readonly reason: "no-debate-fast-path" };

/** Pareto-front reconstruction: a recorded front or an explicit null-front gap. */
export type ParetoFrontReconstruction =
  | { readonly kind: "recorded"; readonly size: number }
  | { readonly kind: "empty"; readonly reason: "null-front" };

export interface CouncilReconstruction {
  /** The terminal phase the row actually reached, clamped to [1, 5]. */
  readonly maxPhase: PhaseIndex;
  /** Exactly the phases the row recorded — [1..maxPhase], never beyond. */
  readonly recordedPhases: ReadonlyArray<PhaseIndex>;
  readonly debate: DebateReconstruction;
  readonly paretoFront: ParetoFrontReconstruction;
}

/**
 * FE-INV-045 — honest Council Theater reconstruction. Derives only the phases
 * the decision actually recorded (a subset of [1, 5] bounded by
 * `phase_reached`) and classifies debate/Pareto-front as recorded or an
 * explicit empty state — "no debate — fast path" for a zero-round decision and
 * a null-front marker when no Pareto front was recorded. Pure and total; it
 * never fabricates deliberation with no backing record.
 */
export function reconstructCouncil(decision: ConsensusDecision): CouncilReconstruction {
  const maxPhase = clampPhase(decision.phase_reached);
  const recordedPhases: PhaseIndex[] = [];
  for (let p = MIN_PHASE; p <= maxPhase; p++) recordedPhases.push(p as PhaseIndex);

  const rounds = decision.debate_rounds;
  const transcriptLength = decision.context_messages.length;
  const debate: DebateReconstruction =
    rounds > 0 && transcriptLength > 0
      ? { kind: "recorded", rounds, transcriptLength }
      : { kind: "empty", reason: "no-debate-fast-path" };

  const front = decision.pareto_front;
  const paretoFront: ParetoFrontReconstruction =
    front && front.length > 0
      ? { kind: "recorded", size: front.length }
      : { kind: "empty", reason: "null-front" };

  return { maxPhase, recordedPhases, debate, paretoFront };
}
