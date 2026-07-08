import { z } from "zod";
import { ZConfidence, ZTier, ZUuid } from "./primitives";

// Escalation envelope on /ws/escalation (orchestrator/inference/serve.py:174-192).
// Not in proto/domain because it's a transport envelope, not a domain output.
// Kept here so the FE has a single source of truth.

export const ZViolation = z
  .object({
    code: z.string(),
    message: z.string(),
    severity: z.enum(["low", "medium", "high", "critical"]).optional(),
  })
  .passthrough();

/** A guardrail violation as it arrives on the escalation envelope (severity optional). */
export type GuardrailViolation = z.infer<typeof ZViolation>;

export const VIOLATION_SEVERITIES = ["low", "medium", "high", "critical"] as const;
export type ViolationSeverity = (typeof VIOLATION_SEVERITIES)[number];

/** Default severity applied when a violation arrives without one (Req 3.4). */
export const DEFAULT_VIOLATION_SEVERITY: ViolationSeverity = "medium";

/**
 * A guardrail violation guaranteed to carry code, message, and severity so the
 * Override Cockpit can render every constraint the operator is overriding.
 */
export interface NormalizedViolation {
  readonly code: string;
  readonly message: string;
  readonly severity: ViolationSeverity;
}

/**
 * Pure normalization for guardrail violations (Req 3.4).
 *
 * Guarantees, for any input list:
 * - count is preserved — a violation is NEVER dropped or collapsed;
 * - every row carries a non-empty `code`, a non-empty `message`, and a `severity`;
 * - a missing (or empty) severity defaults to `medium` rather than hiding the row.
 *
 * The input is intentionally accepted loosely so a malformed payload that slipped
 * past the schema still yields a complete, renderable row instead of a blank one.
 */
export function normalizeViolations(
  violations: readonly GuardrailViolation[],
): readonly NormalizedViolation[] {
  return violations.map((violation) => {
    const code =
      typeof violation.code === "string" && violation.code.length > 0
        ? violation.code
        : "UNKNOWN";
    const message =
      typeof violation.message === "string" && violation.message.length > 0
        ? violation.message
        : "(no message provided)";
    const severity: ViolationSeverity = isViolationSeverity(violation.severity)
      ? violation.severity
      : DEFAULT_VIOLATION_SEVERITY;
    return { code, message, severity };
  });
}

function isViolationSeverity(value: unknown): value is ViolationSeverity {
  return (
    value === "low" || value === "medium" || value === "high" || value === "critical"
  );
}

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
