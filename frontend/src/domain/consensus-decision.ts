import { z } from "zod";
import { ZConfidence, ZIsoTimestamp, ZTier, ZUuid } from "./primitives";

// Mirror of proto/domain/consensus_decision.schema.json (Orchestrator output).
// `proposals`, `selected_action`, `pareto_weights`, `human_override`,
// `pareto_front[]`, `context_messages[]` are open shapes in the proto schema
// (`type: object`). We keep them passthrough here but expose typed helper
// schemas in derived view-models.

const ZProposal = z
  .object({
    agent_name: z.string().optional(),
    action: z.unknown().optional(),
    utility_score: z.number().optional(),
    confidence: ZConfidence.optional(),
    justification_trace: z.array(z.string()).optional(),
    status: z.enum(["proposed", "rejected", "selected", "modified"]).optional(),
    // ADR-044: structured provenance (synapse_common.models.Provenance) —
    // optional/nullable so pre-044 proposals keep validating.
    provenance: z
      .object({
        model_version: z.string().optional(),
        feature_source: z.string().optional(),
        degraded: z.boolean().optional(),
        confidence_basis: z.string().optional(),
      })
      .passthrough()
      .nullable()
      .optional(),
  })
  .passthrough();

const ZParetoWeights = z.record(z.number()).default({});

export const ConsensusDecisionSchema = z
  .object({
    decision_id: ZUuid,
    timestamp: ZIsoTimestamp,
    tier: ZTier,
    proposals: z.array(ZProposal),
    selected_action: z.record(z.unknown()),
    pareto_weights: ZParetoWeights,
    confidence: ZConfidence,
    escalated_to_human: z.boolean().optional(),
    human_override: z.record(z.unknown()).nullable().optional(),
    audit_trace: z.array(z.string()),
    phase_reached: z.number().int().min(1).max(5).default(1),
    debate_rounds: z.number().int().min(0).default(0),
    pareto_front: z.array(z.record(z.unknown())).nullable().optional(),
    context_messages: z.array(z.record(z.unknown())).default([]),
    execution_confirmations: z.array(z.string()).default([]),
    audit_id: ZUuid.nullable().optional(),
  })
  .strict();

export type ConsensusDecision = z.infer<typeof ConsensusDecisionSchema>;
export type Proposal = z.infer<typeof ZProposal>;
