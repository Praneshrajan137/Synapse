import type { City } from "@/domain/city";
import type { AgentName, TierKey } from "@/ui/tokens";

/**
 * Decision domain — the core aggregate the UI expresses.
 *
 * Mirrors the orchestrator's consensus output. All shapes are readonly:
 * the backend's models are frozen (Pydantic frozen=True) and the UI
 * honors that — especially the append-only context (invariant I-14).
 */

export type DecisionTier = TierKey;

/** The five phases of the consensus protocol, in order. */
export const CONSENSUS_PHASES = [
  "collecting",
  "debating",
  "arbitrating",
  "executing",
  "learning",
] as const;
export type ConsensusPhase = (typeof CONSENSUS_PHASES)[number];

export const PHASE_LABEL: Record<ConsensusPhase, string> = {
  collecting: "Collecting",
  debating: "Debating",
  arbitrating: "Arbitrating",
  executing: "Executing",
  learning: "Learning",
};

/** Status of a context message — drives its visual treatment. */
export type MessageStatus = "active" | "error" | "resolved" | "reasoning";

/**
 * A single immutable entry in the append-only consensus context.
 * Once created it is never mutated or reordered (I-14).
 */
export interface ContextMessage {
  readonly id: string;
  /** Agent name, "system", "orchestrator", "llm" or "pareto". */
  readonly source: string;
  readonly status: MessageStatus;
  readonly role: "system" | "assistant" | "user";
  readonly phase: ConsensusPhase;
  /** Monotonic sequence — the append-only ordering key. */
  readonly sequence: number;
  /** Deterministically serialized JSON or reasoning prose. */
  readonly content: string;
  readonly timestamp: number;
}

/** An agent's domain-specific action payload, tagged for generative UI. */
export interface ActionPayload {
  /** e.g. "pricing.update.v1" — drives the payload renderer registry. */
  readonly kind: string;
  readonly data: Readonly<Record<string, unknown>>;
}

/** One agent's proposal within a decision. */
export interface AgentProposal {
  readonly agentName: AgentName;
  readonly utilityScore: number;
  readonly confidence: number;
  readonly justificationTrace: readonly string[];
  readonly action: ActionPayload;
  readonly tier: DecisionTier;
}

/** A point on the multi-objective Pareto front. */
export interface ParetoPoint {
  readonly cost: number;
  readonly time: number;
  readonly sustainability: number;
  readonly fairness: number;
  readonly knee: boolean;
}

/** A human's override of an escalated decision. */
export interface HumanOverride {
  readonly action: "approved" | "rejected" | "modified";
  readonly reason: string;
  readonly operator: string;
  readonly at: number;
}

/** Post-decision KPI measurement, joined 24h later. */
export interface DecisionOutcome {
  readonly fillRateDelta: number;
  readonly wasteRateDelta: number;
  readonly marginDelta: number;
  readonly onTimeDelta: number;
  readonly measuredAt: number;
}

export type DecisionStatus = "in_progress" | "executed" | "escalated" | "deferred";

/** The full decision aggregate. */
export interface Decision {
  readonly id: string;
  readonly city: City;
  readonly tier: DecisionTier;
  readonly phase: ConsensusPhase;
  readonly status: DecisionStatus;
  readonly confidence: number;
  readonly proposals: readonly AgentProposal[];
  readonly contextMessages: readonly ContextMessage[];
  readonly selectedAction: ActionPayload;
  readonly paretoFront: readonly ParetoPoint[];
  readonly debateRounds: number;
  readonly escalated: boolean;
  readonly auditId: string | null;
  readonly humanOverride: HumanOverride | null;
  readonly outcome: DecisionOutcome | null;
  readonly latencyMs: number;
  readonly createdAt: number;
  /** One-line human summary of the selected action. */
  readonly summary: string;
}

/** A guardrail or threshold breach that triggered an escalation. */
export interface Violation {
  readonly code: string;
  readonly detail: string;
}

/** An escalated decision awaiting human action in the Council. */
export interface Escalation {
  readonly decision: Decision;
  /** Recommended (orchestrator-selected) action. */
  readonly recommendedAction: ActionPayload;
  readonly recommendedAgent: AgentName;
  readonly violations: readonly Violation[];
  /** Epoch ms when the HITL window closes (300s default). */
  readonly deadlineAt: number;
}

/** Compact decision row for the Bridge tape and Replay timeline. */
export interface DecisionSummary {
  readonly id: string;
  readonly city: City;
  readonly tier: DecisionTier;
  readonly confidence: number;
  readonly escalated: boolean;
  readonly status: DecisionStatus;
  readonly leadAgent: AgentName;
  readonly summary: string;
  readonly createdAt: number;
}
