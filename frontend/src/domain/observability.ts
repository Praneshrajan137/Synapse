import type { DecisionSummary } from "@/domain/decision";
import type { AgentName } from "@/ui/tokens";

/**
 * Observability domain — per-agent x-ray (Inspector) and the Kafka
 * topic registry (Streams).
 */

export interface ConformalCoverage {
  readonly horizon: string;
  readonly target: number;
  readonly actual: number;
}

export interface AgentDetail {
  readonly name: AgentName;
  readonly rewardFunction: string;
  readonly p50LatencyMs: number;
  readonly p99LatencyMs: number;
  readonly decisionsPerMin: number;
  /** Reward over recent training episodes. */
  readonly rewardCurve: readonly number[];
  /** Confidence histogram, 10 buckets. */
  readonly confidenceHistogram: readonly number[];
  readonly recentDecisions: readonly DecisionSummary[];
  readonly topicsProduced: readonly string[];
  readonly topicsConsumed: readonly string[];
  /** Present only for probabilistic agents (e.g. Demand Prophet). */
  readonly conformal?: readonly ConformalCoverage[];
}

/** Protocol class of a Kafka topic — A2A vs telemetry (invariant I-9). */
export type TopicClass = "agent" | "orchestrator" | "telemetry" | "audit" | "hitl";

export interface KafkaTopic {
  readonly name: string;
  readonly partitions: number;
  readonly retentionHours: number;
  readonly messagesPerSec: number;
  readonly consumerLag: number;
  readonly topicClass: TopicClass;
}
