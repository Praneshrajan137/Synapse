/**
 * SYNAPSE Atlas Console — Mission Control domain model.
 *
 * The Zod schema below validates frames arriving on `/ws/escalation`
 * (WebSocket) before they leave the parser. Anything that fails parses
 * is logged and dropped — never rendered. This is the I-3 boundary on
 * the client.
 *
 * Tier strings match the backend Postgres CHECK constraint exactly
 * (tier_1 .. tier_4). Confidence is the post-debate value at the time
 * the orchestrator decided to escalate; the queue ranker uses it.
 */
import { z } from "zod";

export const TierSchema = z.enum(["tier_1", "tier_2", "tier_3", "tier_4"]);
export type Tier = z.infer<typeof TierSchema>;

/** A single agent's proposal as seen in the escalation envelope. */
export const ProposalSchema = z
  .object({
    agent: z.string().min(1),
    confidence: z.number().min(0).max(1),
    action: z.unknown(),
    justification: z.string().optional(),
  })
  .strict();
export type Proposal = z.infer<typeof ProposalSchema>;

export const ViolationSchema = z.object({
  code: z.string().min(1),
  severity: z.enum(["info", "warn", "alert", "critical"]).default("warn"),
  detail: z.string().optional(),
});
export type Violation = z.infer<typeof ViolationSchema>;

/** The wire format of an escalation broadcast. */
export const EscalationSchema = z
  .object({
    type: z.literal("escalation"),
    decision_id: z.string().uuid(),
    tier: TierSchema,
    confidence: z.number().min(0).max(1),
    /** ISO-8601 timestamp of when the orchestrator emitted the escalation. */
    issued_at: z.string().datetime({ offset: true }).optional(),
    /** Seconds remaining before the orchestrator times out and falls back. */
    timeout_seconds: z.number().int().nonnegative().optional(),
    proposals: z.array(ProposalSchema).default([]),
    recommended_action: z.unknown().optional(),
    violations: z
      .array(z.union([z.string(), ViolationSchema]))
      .default([])
      // Normalise legacy bare-string violations into the structured form.
      .transform((vs) =>
        vs.map((v) =>
          typeof v === "string" ? ({ code: v, severity: "warn" } as const) : v,
        ),
      ),
  })
  .strict();
export type Escalation = z.infer<typeof EscalationSchema>;

/** Server → client ACK for a HITL response. */
export const AckSchema = z
  .object({
    type: z.literal("ack"),
    decision_id: z.string().uuid().optional(),
    response: z.unknown().optional(),
    error: z.string().optional(),
    /** Echoed clientId from the offline queue, if present. */
    client_id: z.string().optional(),
  })
  .strict();
export type Ack = z.infer<typeof AckSchema>;

/** Discriminated union of everything the WebSocket may emit. */
export const WsFrameSchema = z.discriminatedUnion("type", [EscalationSchema, AckSchema]);
export type WsFrame = z.infer<typeof WsFrameSchema>;

/** Client → server payload sent when the operator decides. */
export const ResponsePayloadSchema = z
  .object({
    decision_id: z.string().uuid(),
    response: z.discriminatedUnion("action", [
      z.object({ action: z.literal("approved") }),
      z.object({ action: z.literal("rejected"), reason: z.string().max(500).optional() }),
      z.object({
        action: z.literal("modified"),
        modification: z.record(z.string(), z.unknown()),
      }),
    ]),
    /** Stable client-issued id so we can ACK-match across reconnects. */
    client_id: z.string().min(8).max(128),
  })
  .strict();
export type ResponsePayload = z.infer<typeof ResponsePayloadSchema>;
