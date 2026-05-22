import { z } from "zod";
import { ZConfidence, ZTier, ZUuid } from "./primitives";

// Escalation envelope on /ws/escalation (orchestrator/inference/serve.py:174-192).
// Not in proto/domain because it's a transport envelope, not a domain output.
// Kept here so the FE has a single source of truth.

const ZViolation = z
  .object({
    code: z.string(),
    message: z.string(),
    severity: z.enum(["low", "medium", "high", "critical"]).optional(),
  })
  .passthrough();

const ZRecommendedAction = z.record(z.unknown()).optional();

export const EscalationMessageSchema = z
  .object({
    type: z.literal("escalation"),
    decision_id: ZUuid,
    tier: ZTier.optional(),
    confidence: ZConfidence,
    proposals: z.array(z.record(z.unknown())).default([]),
    recommended_action: ZRecommendedAction,
    violations: z.array(ZViolation).default([]),
    reason: z.string().optional(),
    created_at: z.string().optional(),
  })
  .passthrough();

export type EscalationMessage = z.infer<typeof EscalationMessageSchema>;

// Outgoing operator response (matches OverrideConsole.jsx:13).
export const OverrideResponseSchema = z
  .object({
    decision_id: ZUuid,
    response: z.object({
      action: z.enum(["approved", "rejected", "modified"]),
      modified_action: z.record(z.unknown()).optional(),
      reason: z.string().min(1).optional(),
    }),
  })
  .strict();

export type OverrideResponse = z.infer<typeof OverrideResponseSchema>;
