import { z } from "zod";
import { ZConfidence, ZTier, ZUuid } from "./primitives";

/**
 * The LIVE decision envelope on the firehose `decision` channel — the lean
 * payload `orchestrator/audit/logger.py` enqueues to the outbox (ADR-044),
 * NOT the full `ConsensusDecision` audit row.
 *
 * History: the channel used to be validated against the strict
 * `ConsensusDecisionSchema`, whose required fields (timestamp, proposals,
 * audit_trace) the outbox payload never carried — every live decision was
 * silently rejected by `safeParse` and the "live" tail rendered nothing.
 * This schema matches what actually flows, and is `.passthrough()` so
 * future additive envelope keys (the ADR-044 contract) never break it.
 *
 * Honesty fields:
 *   degraded     — ANY input proposal ran a fallback path (ADR-040).
 *   is_synthetic — traffic-generator decision (order_id "synthetic-" rule,
 *                  owned by packages/synapse_common/synthetic.py).
 *   agents       — lean per-agent summary (name + confidence + degraded);
 *                  the full proposals stay in the audit row.
 */

export const DecisionAgentSummarySchema = z
  .object({
    agent_name: z.string(),
    confidence: ZConfidence.optional(),
    degraded: z.boolean().default(false),
  })
  .passthrough();

export type DecisionAgentSummary = z.infer<typeof DecisionAgentSummarySchema>;

export const DecisionEnvelopeSchema = z
  .object({
    decision_id: ZUuid,
    tier: ZTier,
    confidence: ZConfidence,
    phase_reached: z.number().int().min(1).max(5).default(1),
    escalated: z.boolean().default(false),
    selected_action: z.record(z.unknown()).default({}),
    // Pre-ADR-044 envelopes have no timestamp; use-firehose falls back to
    // the server envelope `ts` before appending to the store.
    timestamp: z.string().optional(),
    degraded: z.boolean().default(false),
    is_synthetic: z.boolean().default(false),
    agents: z.array(DecisionAgentSummarySchema).default([]),
  })
  .passthrough();

export type DecisionEnvelope = z.infer<typeof DecisionEnvelopeSchema>;

/**
 * A decision envelope as stored in the firehose ring buffer: `use-firehose`
 * guarantees a timestamp (payload timestamp, falling back to the server
 * envelope `ts`) before appending, so render code never branches on it.
 */
export type LiveDecision = DecisionEnvelope & { readonly timestamp: string };
