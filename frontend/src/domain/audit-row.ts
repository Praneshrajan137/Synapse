import { z } from "zod";
import { ZCity, ZConfidence, ZInitiator, ZIsoTimestamp, ZTier, ZUuid } from "./primitives";

// Shape of a row from GET /api/v1/decisions/recent (api/routers/decisions.py:32-62).
// Audit immutability per I-4 — read-only on the FE.

export const AuditRowSchema = z
  .object({
    audit_id: ZUuid,
    decision_id: ZUuid,
    tier: ZTier,
    phase_reached: z.number().int().min(1).max(5),
    confidence: ZConfidence,
    escalated: z.boolean(),
    city: ZCity.optional(),
    selected_action: z.record(z.unknown()).optional(),
    pareto_weights: z.record(z.number()).optional(),
    proposals: z.array(z.record(z.unknown())).optional(),
    human_override: z.record(z.unknown()).nullable().optional(),
    operator_token_ref: z.string().nullable().optional(),
    debate_rounds: z.number().int().min(0).optional(),
    context_messages: z.array(z.record(z.unknown())).optional(),
    execution_confirmations: z.array(z.string()).optional(),
    audit_trace: z.array(z.string()).optional(),
    created_at: ZIsoTimestamp,
    // ADR-044 honesty fields (additive — optional for pre-044 gateways).
    degraded: z.boolean().optional(),
    is_synthetic: z.boolean().optional(),
    // ADR-053: three-way origin. Optional for pre-053 gateways; the UI treats
    // a missing value as "operator" (the honest default).
    initiator: ZInitiator.optional(),
  })
  .passthrough();

export type AuditRow = z.infer<typeof AuditRowSchema>;

export const AuditListResponseSchema = z
  .object({
    decisions: z.array(AuditRowSchema),
    count: z.number().int().min(0),
  })
  .passthrough();

export type AuditListResponse = z.infer<typeof AuditListResponseSchema>;
