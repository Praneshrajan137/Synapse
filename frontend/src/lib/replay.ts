// FE-INV-028: deterministic decision replay.
//
// Given a ConsensusDecision and a phase index, returns the UI slice that
// represents the system's state at that phase boundary. Pure — no
// Date.now(), no Math.random(), no I/O — so loading the same decision
// twice produces byte-identical renders (FE-INV-009).

import type { ConsensusDecision, Proposal } from "@domain/consensus-decision";

export interface ReplaySlice {
  readonly phase: 1 | 2 | 3 | 4 | 5;
  readonly proposalsVisible: ReadonlyArray<Proposal>;
  readonly selectedAction: Record<string, unknown> | null;
  readonly confidenceAtPhase: number;
  readonly debateRoundsCompleted: number;
  readonly auditTraceSoFar: ReadonlyArray<string>;
  readonly humanOverride: Record<string, unknown> | null;
  readonly executionConfirmations: ReadonlyArray<string>;
}

const PHASE_NAMES = ["proposal", "debate", "arbitration", "execution", "learning"] as const;
export type PhaseName = (typeof PHASE_NAMES)[number];

export function phaseName(index: 1 | 2 | 3 | 4 | 5): PhaseName {
  return PHASE_NAMES[index - 1]!;
}

export function replayDecision(decision: ConsensusDecision, phaseIndex: number): ReplaySlice {
  const clamped = Math.max(1, Math.min(5, Math.floor(phaseIndex))) as 1 | 2 | 3 | 4 | 5;
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
