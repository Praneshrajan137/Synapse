import { z } from "zod";
import { ZUuid } from "./primitives";

/**
 * The live Cognition Channel payload (ADR-048) — one FSM phase transition the
 * orchestrator emits to `synapse.orchestrator.phase` and the firehose relays as
 * the `cognition` channel. Lets the AUX show the council thinking/debating LIVE
 * from real events, not just the final verdict.
 *
 * Correlated to the eventual ConsensusDecision by `decision_id` (the same id the
 * recorded Council Theater reconstruction uses). `.passthrough()` so additive
 * backend keys never break the schema (the dead-channel lesson of ADR-044).
 */

export const CognitionPhaseSchema = z.enum([
  "collecting",
  "debating",
  "arbitrating",
  "executing",
  "learning",
]);
export type CognitionPhase = z.infer<typeof CognitionPhaseSchema>;

export const CognitionEventSchema = z
  .object({
    decision_id: ZUuid,
    phase: CognitionPhaseSchema,
    // Present on per-agent collect events (event = "proposed" | "failed").
    agent_name: z.string().optional(),
    event: z.string().optional(),
    round: z.number().int().optional(),
    city: z.string().optional(),
    ts: z.string().optional(),
  })
  .passthrough();

export type CognitionEvent = z.infer<typeof CognitionEventSchema>;
