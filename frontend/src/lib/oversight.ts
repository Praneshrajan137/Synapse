// Oversight pure predicates (Req 3.2, 3.7, 3.8, 3.9, 12.5).
//
// These are the single source of truth for the three pure decisions that
// govern the operator-authority surface (`OversightControls`):
//
//   1. focus demotion   — which action holds default focus for a decision
//   2. steering clamp    — sanitizing a raw steering input into [0, 1]
//   3. capability gating — whether a capability is actionable for a role
//
// They are deliberately dependency-free and side-effect-free so the property
// tests (Property 9 / 10 / 11) and the rendering compound share exactly one
// implementation. The 0.80 threshold is the I-5 autonomy gate, mirrored from
// `CONFIDENCE_GATE.high` so there is a single threshold convention.

import { CONFIDENCE_GATE } from "@lib/chromatics";
import {
  type ErvInput,
  type ErvReason,
  type ErvStakesField,
  expectedReviewValue,
} from "@lib/expected-review-value";
import type { Role } from "@state/session.store";

/**
 * Operator role alias. The design speaks in terms of `OperatorRole`; the
 * session store models the concrete union as `Role`. Aliasing keeps the
 * design vocabulary while binding to the real type (no drift).
 */
export type OperatorRole = Role;

/** The action that holds default focus when an operator reviews a decision. */
export type FocusAction = "approve" | "reject" | "modify";

/** A single oversight capability the operator surface can expose. */
export interface OversightCapability {
  readonly id:
    | "interrupt"
    | "override"
    | "steer"
    | "delegate"
    | "recover"
    | "escalate-next"
    | "escalate-prev"
    | "dismiss";
  /** null → no backing backend endpoint exists (a backend gap, Req 3.8). */
  readonly backingEndpoint: string | null;
  /** Roles permitted to actuate this capability. */
  readonly requiredRoles: readonly OperatorRole[];
  /** Keyboard key that activates the capability (Req 3.3). */
  readonly keyboardKey: string;
}

/**
 * Focus demotion (Req 3.2, FE-INV-007, Property 9).
 *
 * Below the 0.80 autonomy gate the machine is not confident enough to be
 * approved by default, so default focus is demoted away from "approve" to a
 * corrective action ("reject" or "modify"). At or above the gate, "approve"
 * holds default focus. Pure and total over the reals.
 *
 * We return "modify" as the demoted default: it is the least-destructive
 * corrective action (the operator can still reject from there), which keeps a
 * sub-threshold decision from being one keystroke away from a blind approve.
 */
export function defaultFocusAction(confidence: number): FocusAction {
  // A non-finite / sub-threshold confidence can never satisfy the gate, so the
  // single `>=` comparison covers NaN (NaN >= x is false → demoted) as well.
  return confidence >= CONFIDENCE_GATE.high ? "approve" : "modify";
}

/**
 * The default-focus decision for a single decision under review, derived from
 * Expected_Review_Value (Req 12.2, 12.3, 12.6) — the model that SUPERSEDES the
 * confidence-only `defaultFocusAction`.
 *
 * `action`             which override action holds default keyboard focus.
 * `escalated`          whether ERV demanded human review at all.
 * `reason`             the strongest reason review was demanded (Req 12.6).
 * `degraded`           a stakes field was absent → confidence-only fallback.
 * `fieldsUnavailable`  the absent stakes fields (Req 12.5), for the surface's
 *                      explicit "unavailable" indication.
 */
export interface ReviewFocus {
  readonly action: FocusAction;
  readonly escalated: boolean;
  readonly reason: ErvReason;
  readonly degraded: boolean;
  readonly fieldsUnavailable: readonly ErvStakesField[];
}

/**
 * ERV-derived focus demotion (Req 12.2, 12.3, 12.6, FE-INV-007, Property 17).
 *
 * Supersedes the confidence-only {@link defaultFocusAction}: default keyboard
 * focus among the override actions is derived from Expected_Review_Value rather
 * than from confidence alone. A decision escalates — and therefore has focus
 * demoted away from "approve" to the least-destructive corrective action
 * ("modify") — whenever ERV demands review:
 *
 *   - it is irreversible, OR
 *   - it is high-blast-radius,
 *
 * even when confidence is at or above the 0.80 autonomy gate (Req 12.2); OR
 *
 *   - its confidence is below the gate,
 *
 * which preserves the existing low-confidence demotion behaviour (Req 3.2). A
 * decision that escalates on neither stakes nor confidence keeps "approve" on
 * default focus. When a stakes field is absent, ERV degrades honestly to a
 * confidence-only ranking and the absent fields are surfaced so the compound
 * can render an explicit "unavailable" indication (Req 12.5). Pure and total.
 */
export function defaultFocusActionByReview(input: ErvInput): ReviewFocus {
  const erv = expectedReviewValue(input);
  return {
    // Demote away from a blind Approve whenever review was demanded; "modify"
    // is the least-destructive corrective action (mirrors defaultFocusAction).
    action: erv.escalate ? "modify" : "approve",
    escalated: erv.escalate,
    reason: erv.reason,
    degraded: erv.degraded,
    fieldsUnavailable: erv.fieldsUnavailable,
  };
}

/**
 * Steering clamp + sanitize (Req 3.7, FE-INV-033, Property 11).
 *
 * A finite value is clamped into the closed interval [0, 1]; a non-finite
 * value (NaN, +∞, −∞) collapses to 0 so a corrupt input can never be applied
 * as a live steering weight. Total over the reals; the result is always in
 * [0, 1].
 */
export function clampSteering(x: number): number {
  if (!Number.isFinite(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

/**
 * Authorization + visibility predicate (Req 3.8, 3.9, 12.5, Property 10).
 *
 * A capability is actionable if and only if:
 *   - it has a backing backend endpoint (a null endpoint is a backend gap and
 *     is NEVER actionable, regardless of role), AND
 *   - the operator's role is within the capability's required-role set.
 *
 * This predicate only answers "may this role actuate it now?". Out-of-scope
 * actions are still VISIBLE (rendered present-but-disabled with a communicated
 * restriction) — visibility is a separate concern handled by the compound, and
 * `isCapabilityVisible` documents that a capability is always shown.
 */
export function isCapabilityActionable(
  role: OperatorRole,
  capability: OversightCapability,
): boolean {
  if (capability.backingEndpoint === null) return false;
  return capability.requiredRoles.includes(role);
}

/**
 * Visibility predicate (Req 3.9, 12.5, Property 10).
 *
 * Oversight capabilities are ALWAYS present — an out-of-scope or backend-gapped
 * capability is rendered disabled with a communicated restriction, never
 * hidden and never silently allowed. This is a total constant so the intent is
 * explicit at the call site and in the property test.
 */
export function isCapabilityVisible(
  _role: OperatorRole,
  _capability: OversightCapability,
): boolean {
  return true;
}

/**
 * A capability whose backing endpoint is null is a backend gap (Req 3.8): the
 * Console is entitled to the action but the backend does not yet expose it.
 */
export function isBackendGap(capability: OversightCapability): boolean {
  return capability.backingEndpoint === null;
}
