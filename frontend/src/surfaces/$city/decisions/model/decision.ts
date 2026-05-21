/**
 * SYNAPSE Atlas Console — Decision Trace domain model.
 *
 * Mirrors the OpenAPI shapes for ``RecentDecisionRow``,
 * ``RecentDecisionsResponse``, and ``ConsensusDecision``. We hand-author
 * the Zod schemas here (rather than rely on Orval-generated types) so the
 * surface owns its parsing boundary even if the codegen pipeline drifts.
 *
 * The parsed types are the source of truth used by hooks + components
 * across the surface.
 */
import { z } from "zod";

export const TierSchema = z.enum(["tier_1", "tier_2", "tier_3", "tier_4"]);
export type Tier = z.infer<typeof TierSchema>;

export const RecentDecisionRowSchema = z
  .object({
    audit_id: z.string().uuid(),
    decision_id: z.string().uuid(),
    tier: TierSchema,
    created_at: z.string().datetime({ offset: true }),
  })
  .strict();
export type RecentDecisionRow = z.infer<typeof RecentDecisionRowSchema>;

export const RecentDecisionsResponseSchema = z
  .object({
    decisions: z.array(RecentDecisionRowSchema),
    count: z.number().int().nonnegative(),
    next_cursor: z.string().nullable(),
  })
  .strict();
export type RecentDecisionsResponse = z.infer<typeof RecentDecisionsResponseSchema>;

const ContextMessageSchema = z
  .object({
    phase: z.number().int().min(1).max(5).optional(),
    role: z.string().optional(),
    content: z.string().optional(),
  })
  .passthrough();
export type ContextMessage = z.infer<typeof ContextMessageSchema>;

const AuditTraceEntrySchema = z
  .object({
    hash: z.string().min(64).max(64),
    prev: z.string().nullable(),
    ts: z.string().optional(),
  })
  .passthrough();

export const ConsensusDecisionSchema = z
  .object({
    id: z.string().uuid(),
    decision_id: z.string().uuid(),
    timestamp: z.string().datetime({ offset: true }),
    tier: TierSchema,
    phase_reached: z.number().int().min(1).max(5),
    proposals: z.array(z.record(z.string(), z.unknown())),
    selected_action: z.record(z.string(), z.unknown()),
    pareto_weights: z.record(z.string(), z.unknown()),
    confidence: z.number().min(0).max(1),
    debate_rounds: z.number().int().nonnegative(),
    escalated: z.boolean(),
    human_override: z.record(z.string(), z.unknown()).nullable(),
    execution_confirmations: z.array(z.record(z.string(), z.unknown())),
    context_messages: z.array(ContextMessageSchema),
    audit_trace: z.array(AuditTraceEntrySchema),
    pareto_front: z.array(z.record(z.string(), z.unknown())).nullable(),
    outcome: z.record(z.string(), z.unknown()).nullable(),
    created_at: z.string().datetime({ offset: true }),
  })
  .strict();
export type ConsensusDecision = z.infer<typeof ConsensusDecisionSchema>;

/** TanStack Router search-param shape — keep aligned with the route. */
export const DecisionsSearchSchema = z.object({
  tier: TierSchema.optional(),
  agent: z.string().min(1).max(64).optional(),
  escalated: z.coerce.boolean().optional(),
  override: z.coerce.boolean().optional(),
  q: z.string().max(200).optional(),
  since: z.string().datetime({ offset: true }).optional(),
  until: z.string().datetime({ offset: true }).optional(),
  /** Decision id whose drawer is open. */
  open: z.string().uuid().optional(),
  /** Replay scrubber position (ms since epoch). */
  scrub: z.coerce.number().int().nonnegative().optional(),
});
export type DecisionsSearch = z.infer<typeof DecisionsSearchSchema>;
