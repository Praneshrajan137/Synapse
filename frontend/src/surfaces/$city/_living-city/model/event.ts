/**
 * SYNAPSE Atlas Console — Living City event-tail domain.
 *
 * The right-rail event tail subscribes to the 9 user-visible Kafka
 * topics through the SSE bridge (`/api/v1/stream/{topic}`) and renders
 * them in arrival order. We don't try to enforce a tight schema on
 * every body — the orchestrator's wire formats live in
 * `proto/domain/*.schema.json` and Zod schemas land via
 * `pnpm schemas:zod` in S2. Until then the tail validates only the
 * envelope shape (topic, ts, body) and lets surfaces narrow further
 * if they need to.
 */
import { z } from "zod";

export const USER_VISIBLE_TOPICS = [
  "synapse.demand.forecast",
  "synapse.routing.plan",
  "synapse.inventory.reorder",
  "synapse.orchestrator.escalation",
  "synapse.disruption.alert",
  "synapse.pricing.update",
  "synapse.freshness.alert",
  "synapse.orchestrator.decision",
  "synapse.audit.log",
  "synapse.metrics.agent",
] as const;
export type UserVisibleTopic = (typeof USER_VISIBLE_TOPICS)[number];

export const TopicSeveritySchema = z.enum(["info", "warn", "alert", "critical"]);
export type TopicSeverity = z.infer<typeof TopicSeveritySchema>;

/** Mapping topic → severity tier for tail badges + filter chips. */
export const TOPIC_SEVERITY: Record<UserVisibleTopic, TopicSeverity> = {
  "synapse.demand.forecast": "info",
  "synapse.routing.plan": "info",
  "synapse.inventory.reorder": "warn",
  "synapse.orchestrator.escalation": "critical",
  "synapse.disruption.alert": "alert",
  "synapse.pricing.update": "info",
  "synapse.freshness.alert": "alert",
  "synapse.orchestrator.decision": "info",
  "synapse.audit.log": "info",
  "synapse.metrics.agent": "info",
};

export interface TailEvent {
  /** Stable id for React keys. */
  readonly id: string;
  readonly topic: UserVisibleTopic;
  readonly receivedAt: number;
  /** Parsed JSON body — passthrough; surfaces narrow per-topic. */
  readonly body: unknown;
}

/**
 * Loose envelope schema for a single SSE event payload. We accept
 * arbitrary record bodies and validate only the well-known fields
 * we actually render.
 */
export const TailEventBodySchema = z
  .object({
    /** Some topics include their own ts; we fall back to receive time. */
    ts: z.string().datetime({ offset: true }).optional(),
  })
  .passthrough();

export type TailEventBody = z.infer<typeof TailEventBodySchema>;
