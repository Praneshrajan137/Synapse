// Expected_Review_Value — stakes-aware attention model (Req 12).
//
// WHY THIS EXISTS
// ---------------
// The confidence-only `defaultFocusAction` in `lib/oversight.ts` demotes focus
// away from "approve" below the 0.80 autonomy gate and trusts the machine at or
// above it. That model is blind to *stakes*: an irreversible or high-blast
// decision deserves human review even when the machine is confident. This
// module ranks a decision's need for human review by
//
//     f(confidence, reversibility, blast_radius)
//
// so that Expected_Review_Value — not confidence alone — governs which decision
// demands attention first (Req 12.1) and which decisions escalate despite a
// confident machine (Req 12.2). It is the single source of truth that task 14.2
// wires into the override-focus model, superseding confidence-only focus
// (Req 12.3, `defaultFocusActionByErv`).
//
// HONEST DEGRADATION (Req 12.5)
// -----------------------------
// Reversibility and Blast_Radius are a Cross_Boundary_Dependency: they are
// confirmed ABSENT from `DecisionEnvelopeSchema` / `AuditRowSchema` in the
// Backend_Contract today. When a stakes field is absent this module NEVER
// fabricates a value — it falls back to a confidence-only ranking, flags the
// absent field in `fieldsUnavailable` (so the surface can render an explicit
// "reversibility/blast-radius unavailable" indication, Req 12.6), and marks the
// result `degraded`. The missing fields are recorded as a backend gap for the
// drift report via `ERV_BACKEND_GAP` (consumed by `spec/contract-fidelity/*`).
//
// Every function here is pure, total, and side-effect-free so the property
// tests (Property 15 / 16 / 17) and the rendering compound share exactly one
// implementation. The 0.80 threshold is the I-5 autonomy gate, mirrored from
// `CONFIDENCE_GATE.high` so there is a single threshold convention.

import { CONFIDENCE_GATE } from "@lib/chromatics";

/** Reversibility of a decision's effect (a Cross_Boundary_Dependency). */
export type Reversibility = "reversible" | "irreversible";

/** Blast radius of a decision's effect (a Cross_Boundary_Dependency). */
export type BlastRadius = "low" | "medium" | "high";

/**
 * The stakes fields the Backend_Contract does not yet expose. Recorded as a
 * backend gap in the drift report (Req 12.5) rather than fabricated.
 */
export type ErvStakesField = "reversibility" | "blastRadius";

/**
 * Why a decision demanded human review. `"none"` when it was not escalated.
 * Stakes reasons take precedence over `"low-confidence"` so the non-color
 * indication (Req 12.6) names the *strongest* reason review was demanded.
 */
export type ErvReason = "irreversible" | "high-blast" | "low-confidence" | "none";

export interface ErvInput {
  /** Machine confidence in [0, 1]. Non-finite / out-of-range is clamped. */
  readonly confidence: number;
  /** Reversibility, or null/undefined when the contract omits it. */
  readonly reversibility?: Reversibility | null;
  /** Blast radius, or null/undefined when the contract omits it. */
  readonly blastRadius?: BlastRadius | null;
}

export interface ErvResult {
  /** Higher → more review-worthy. Used to rank decisions (Req 12.1). */
  readonly value: number;
  /** Whether this decision escalates for human review (Req 12.2). */
  readonly escalate: boolean;
  /** True when a stakes field was absent → confidence-only fallback (Req 12.5). */
  readonly degraded: boolean;
  /** The strongest reason review was demanded (Req 12.6). */
  readonly reason: ErvReason;
  /** Absent stakes fields — rendered as unavailable + a drift gap (Req 12.5). */
  readonly fieldsUnavailable: readonly ErvStakesField[];
}

/**
 * The backend gap ERV records when the contract omits the stakes fields
 * (Req 12.5). Consumed by the contract-fidelity drift report so the missing
 * capability is *tracked*, never fabricated and never silently hidden.
 */
export const ERV_BACKEND_GAP = {
  kind: "erv-stakes" as const,
  fields: ["reversibility", "blastRadius"] as readonly ErvStakesField[],
  rationale:
    "DecisionEnvelopeSchema / AuditRowSchema expose no reversibility or " +
    "blast_radius field; Expected_Review_Value degrades to confidence-only.",
} as const;

// The stakes weight dominates the confidence component so any stakes-escalated
// decision ranks strictly above every decision escalated on confidence alone.
// The confidence component lies in [0, 1] (see below), so a weight of 2 keeps
// a single stakes flag above the confidence ceiling with headroom to spare.
const STAKES_WEIGHT = 2;
const MEDIUM_BLAST_WEIGHT = 0.5;

/** Clamp a possibly non-finite confidence into the closed interval [0, 1]. */
function clampConfidence(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

/**
 * Rank a decision's need for human review by f(confidence, reversibility,
 * blast_radius) (Req 12.1). An irreversible or high-blast-radius decision
 * escalates even when confidence is at or above the 0.80 gate (Req 12.2). When
 * a stakes field is absent, the value falls back to confidence-only, the field
 * is flagged unavailable, and the result is marked degraded — never fabricating
 * a value (Req 12.5). Pure and total over the reals.
 */
export function expectedReviewValue(i: ErvInput): ErvResult {
  const c = clampConfidence(i.confidence);

  // A stakes field counts as available only when it carries a real value; a
  // null/undefined field is a Cross_Boundary_Dependency we never fabricate.
  const reversibilityAvailable =
    i.reversibility === "reversible" || i.reversibility === "irreversible";
  const blastAvailable =
    i.blastRadius === "low" || i.blastRadius === "medium" || i.blastRadius === "high";

  const fieldsUnavailable: ErvStakesField[] = [];
  if (!reversibilityAvailable) fieldsUnavailable.push("reversibility");
  if (!blastAvailable) fieldsUnavailable.push("blastRadius");
  const degraded = fieldsUnavailable.length > 0;

  const isIrreversible = reversibilityAvailable && i.reversibility === "irreversible";
  const isHighBlast = blastAvailable && i.blastRadius === "high";
  const isMediumBlast = blastAvailable && i.blastRadius === "medium";
  const isLowConfidence = c < CONFIDENCE_GATE.high;

  // Confidence component: lower confidence → more review-worthy, in [0, 1].
  // Stakes components use only fields that are genuinely present (Req 12.5).
  let value = 1 - c;
  if (isIrreversible) value += STAKES_WEIGHT;
  if (isHighBlast) value += STAKES_WEIGHT;
  else if (isMediumBlast) value += MEDIUM_BLAST_WEIGHT;

  // A decision escalates on stakes even when confident (Req 12.2); otherwise it
  // escalates on sub-gate confidence, mirroring the confidence-only model. The
  // reason names the strongest driver so the non-color indication is honest.
  let reason: ErvReason = "none";
  if (isIrreversible) reason = "irreversible";
  else if (isHighBlast) reason = "high-blast";
  else if (isLowConfidence) reason = "low-confidence";

  return {
    value,
    escalate: reason !== "none",
    degraded,
    reason,
    fieldsUnavailable,
  };
}

/**
 * Default override focus derived from Expected_Review_Value, superseding the
 * confidence-only focus model (Req 12.3). Returns the index of the most
 * review-worthy decision (highest Expected_Review_Value); ties resolve to the
 * lowest index for a stable, deterministic focus. Returns -1 for an empty set
 * (there is nothing to focus). Pure and total.
 */
export function defaultFocusActionByErv(decisions: readonly ErvInput[]): number {
  let bestIndex = -1;
  let bestValue = Number.NEGATIVE_INFINITY;
  for (let idx = 0; idx < decisions.length; idx++) {
    const decision = decisions[idx];
    if (decision === undefined) continue;
    const { value } = expectedReviewValue(decision);
    if (value > bestValue) {
      bestValue = value;
      bestIndex = idx;
    }
  }
  return bestIndex;
}
