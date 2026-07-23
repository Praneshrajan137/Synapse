import { z } from "zod";
import { ZConfidence, ZTier, ZUuid } from "./primitives";

/**
 * A live per-agent telemetry event on the firehose `metric` channel
 * (topic 17 `synapse.metrics.agent`). ADR-053 gave this channel its first real
 * producer (`orchestrator/consensus/firehose_signals.emit_agent_metrics`);
 * before, it was registered-but-dead. Mirrors
 * `proto/domain/agent_metric.schema.json`.
 *
 * This is genuine measured data at proposal-collection time — an agent's
 * confidence and whether its provenance ran an I-7 fallback — NOT a fabricated
 * rate. `.passthrough()` for additive fields.
 */
export const AgentMetricSchema = z
  .object({
    agent_name: z.string(),
    decision_id: ZUuid,
    city: z.string().nullable().optional(),
    tier: ZTier,
    confidence: ZConfidence,
    degraded: z.boolean(),
    confidence_basis: z.string().optional(),
    ts: z.string(),
  })
  .passthrough();

export type AgentMetric = z.infer<typeof AgentMetricSchema>;
