import { Button } from "@ds/primitives";
import type { GuardrailViolation } from "@domain/escalation";
import { normalizeViolations } from "@domain/escalation";
import { cn } from "@lib/cn";
import type { BlastRadius, ErvReason, ErvStakesField, Reversibility } from "@lib/expected-review-value";
import {
  type FocusAction,
  type OperatorRole,
  type OversightCapability,
  clampSteering,
  defaultFocusActionByReview,
  isBackendGap,
  isCapabilityActionable,
} from "@lib/oversight";
import { type ParetoWeights, useSteeringStore } from "@state/steering.store";
import { useCockpitShortcuts } from "@surfaces/override-cockpit/useCockpitShortcuts";
import { useOverrideMutation } from "@surfaces/override-cockpit/useOverrideMutation";
import { forwardRef, useEffect, useMemo, useRef } from "react";

/**
 * Oversight Controls — operator authority surface (Req 3).
 *
 * Renders the full operator authority set — interrupt, override
 * (approve/reject/modify), steer, delegate, recover, escalate-to-next/previous,
 * and dismiss — as a single keyboard-operable compound. It is the rendering
 * counterpart to the pure predicates in `@lib/oversight` (focus demotion,
 * steering clamp, capability gating), so the property tests and the UI share
 * exactly one source of truth.
 *
 * Guarantees:
 *   - **Audit-row-first commits** (Req 3.1, 3.6). Override goes through the
 *     existing `useOverrideMutation` (FE-INV-003/021): the audit row is
 *     committed before the escalation is marked acted, and the WebSocket
 *     `override_confirm` is treated as operational confirmation only, never as
 *     the commit. Steering goes through `useSteeringStore`, which writes the
 *     audit row before applying locally and reverts the value on failure.
 *   - **Expected-value focus demotion** (Req 3.2, 12.2, 12.3, 12.6,
 *     FE-INV-007). `defaultFocusActionByReview` derives which override action
 *     holds default keyboard focus from Expected_Review_Value — superseding the
 *     confidence-only model. Focus is demoted away from Approve when a decision
 *     is irreversible or high-blast-radius (even at/above the 0.80 gate) or
 *     when confidence is below the gate; an explicit non-color indication names
 *     why review was demanded. When the stakes fields are absent, ERV degrades
 *     honestly to confidence-only and the surface says so (Req 12.5).
 *   - **Full keyboard operability** (Req 3.3). Every action is reachable and
 *     activatable without a pointer, reusing `useCockpitShortcuts`
 *     (FE-INV-022) and `aria-keyshortcuts` on each control.
 *   - **Role gating & visibility** (Req 3.8, 3.9, 12.5). A `viewer` (or an
 *     unauthenticated role) sees every control present but disabled and
 *     visibly non-actionable — never hidden — with the restriction spelled
 *     out. Interrupt/recover are exposed to `ops`/`engineer`/`admin` only
 *     where a backing endpoint exists; a capability with no backing endpoint
 *     is a backend gap and is rendered present-but-disabled for everyone.
 */

/** A backend endpoint the audit-row-first override mutation commits to. */
const OVERRIDE_ENDPOINT = "/api/v1/decisions/{id}/override";
/** A backend endpoint the audit-row-first steering store commits to. */
const STEERING_ENDPOINT = "/api/v1/steering";

/**
 * Default capability catalog (Req 3.8, 3.9).
 *
 * `backingEndpoint === null` marks a backend gap: the Console is entitled to
 * the affordance but no backend endpoint exists yet, so it renders
 * present-but-disabled for every role (the Contract Fidelity Suite records it
 * as a gap). `interrupt`, `delegate`, and `recover` have no backend endpoint
 * today and are therefore gaps. Escalation navigation and dismiss are
 * client-side operations (no backend commit), marked with a `client:` sentinel
 * so they are actionable for authorized roles without being mistaken for a
 * backend gap.
 */
export const DEFAULT_OVERSIGHT_CAPABILITIES: readonly OversightCapability[] = [
  {
    id: "interrupt",
    backingEndpoint: null,
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "I",
  },
  {
    id: "override",
    backingEndpoint: OVERRIDE_ENDPOINT,
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "A",
  },
  {
    id: "steer",
    backingEndpoint: STEERING_ENDPOINT,
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "S",
  },
  {
    id: "delegate",
    backingEndpoint: null,
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "D",
  },
  {
    id: "recover",
    backingEndpoint: null,
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "C",
  },
  {
    id: "escalate-next",
    backingEndpoint: "client:escalation-nav",
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "J",
  },
  {
    id: "escalate-prev",
    backingEndpoint: "client:escalation-nav",
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "K",
  },
  {
    id: "dismiss",
    backingEndpoint: "client:dismiss",
    requiredRoles: ["ops", "engineer", "admin"],
    keyboardKey: "Escape",
  },
] as const;

export interface OversightControlsProps {
  /** Authenticated operator role; `viewer`/`anonymous` see disabled controls (Req 3.9). */
  readonly role: OperatorRole;
  /** Confidence of the decision under review; feeds Expected_Review_Value (Req 3.2, 12.3). */
  readonly decisionConfidence: number;
  /**
   * Reversibility of the decision under review (a Cross_Boundary_Dependency).
   * When present and `irreversible`, focus is demoted for review even at/above
   * the 0.80 gate (Req 12.2); absent/null degrades ERV to confidence-only (Req 12.5).
   */
  readonly decisionReversibility?: Reversibility | null;
  /**
   * Blast radius of the decision under review (a Cross_Boundary_Dependency).
   * When present and `high`, focus is demoted for review even at/above the 0.80
   * gate (Req 12.2); absent/null degrades ERV to confidence-only (Req 12.5).
   */
  readonly decisionBlastRadius?: BlastRadius | null;
  /** The decision under review; override actuation requires it. */
  readonly decisionId?: string | null;
  /** Guardrail violations for the active escalation (rendered by EscalationCard; count shown here). */
  readonly violations?: readonly GuardrailViolation[];
  /** Capability catalog; defaults to {@link DEFAULT_OVERSIGHT_CAPABILITIES}. */
  readonly capabilities?: readonly OversightCapability[];
  /** Pareto objective the inline steering control tunes (audit-row-first). */
  readonly steeringTarget?: keyof ParetoWeights;
  /** Escalation navigation (client-side, Req 3.3). */
  readonly onEscalateNext?: (() => void) | undefined;
  readonly onEscalatePrev?: (() => void) | undefined;
  /** Dismiss the active dialog (client-side, Req 3.3). */
  readonly onDismiss?: (() => void) | undefined;
  /** Interrupt/recover/delegate handlers, wired once a backing endpoint exists. */
  readonly onInterrupt?: (() => void) | undefined;
  readonly onRecover?: (() => void) | undefined;
  readonly onDelegate?: (() => void) | undefined;
  readonly className?: string | undefined;
}

/** Roles permitted to actuate oversight capabilities at all. */
function isOversightCapableRole(role: OperatorRole): boolean {
  return role === "ops" || role === "engineer" || role === "admin";
}

/**
 * The non-color reason text for why the Console demanded review (Req 12.6).
 * When stakes fields are present it names each escalating stake (irreversible
 * and/or high blast-radius) so the "and/or" case is honestly reflected; a pure
 * confidence escalation keeps the existing sub-gate wording (Req 3.2).
 */
function reviewDemandMessage(
  reversibility: Reversibility | null,
  blastRadius: BlastRadius | null,
  reason: ErvReason,
): string {
  const stakes: string[] = [];
  if (reversibility === "irreversible") stakes.push("irreversible");
  if (blastRadius === "high") stakes.push("high blast-radius");
  if (stakes.length > 0) {
    return `Review demanded — ${stakes.join(" and ")} decision escalated for human review; default focus demoted from Approve.`;
  }
  if (reason === "low-confidence") {
    return "Confidence below the 0.80 autonomy gate — default focus demoted from Approve.";
  }
  // Defensive fallback; should be unreachable while escalated with no stakes.
  return "Review demanded — default focus demoted from Approve.";
}

/** Human-readable "unavailable" indication for absent stakes fields (Req 12.5). */
function unavailableStakesMessage(fields: readonly ErvStakesField[]): string {
  const LABEL: Record<ErvStakesField, string> = {
    reversibility: "reversibility",
    blastRadius: "blast-radius",
  };
  const names = fields.map((f) => LABEL[f]).join(" and ");
  return `Stakes ${names} unavailable from the backend — ranking by confidence only.`;
}

function findCapability(
  capabilities: readonly OversightCapability[],
  id: OversightCapability["id"],
): OversightCapability | undefined {
  return capabilities.find((c) => c.id === id);
}

const STEERING_LABEL: Record<keyof ParetoWeights, string> = {
  cost: "Cost",
  time: "Time",
  sustainability: "Sustainability",
  fairness: "Fairness",
};

export function OversightControls({
  role,
  decisionConfidence,
  decisionReversibility = null,
  decisionBlastRadius = null,
  decisionId,
  violations = [],
  capabilities = DEFAULT_OVERSIGHT_CAPABILITIES,
  steeringTarget = "cost",
  onEscalateNext,
  onEscalatePrev,
  onDismiss,
  onInterrupt,
  onRecover,
  onDelegate,
  className,
}: OversightControlsProps) {
  const override = useOverrideMutation();
  const paretoWeights = useSteeringStore((s) => s.paretoWeights);
  const setParetoWeight = useSteeringStore((s) => s.setParetoWeight);
  const steeringError = useSteeringStore((s) => s.lastError);

  // Expected_Review_Value-derived focus (Req 12.2, 12.3, 12.6) — supersedes the
  // confidence-only model. `reason`/`degraded` drive the non-color indication.
  const reviewFocus = useMemo(
    () =>
      defaultFocusActionByReview({
        confidence: decisionConfidence,
        reversibility: decisionReversibility,
        blastRadius: decisionBlastRadius,
      }),
    [decisionConfidence, decisionReversibility, decisionBlastRadius],
  );
  const focusAction = reviewFocus.action;
  const roleActionable = isOversightCapableRole(role);
  const normalizedViolations = useMemo(() => normalizeViolations(violations), [violations]);

  const overrideCap = findCapability(capabilities, "override");
  const steerCap = findCapability(capabilities, "steer");

  const canOverride =
    overrideCap !== undefined &&
    isCapabilityActionable(role, overrideCap) &&
    typeof decisionId === "string" &&
    decisionId.length > 0;
  const canSteer = steerCap !== undefined && isCapabilityActionable(role, steerCap);

  // Refs to the three override actions so default focus can be placed on the
  // action `defaultFocusAction` selects (Req 3.2). Approve is demoted below
  // the 0.80 gate; the demoted-to action receives default keyboard focus.
  const approveRef = useRef<HTMLButtonElement>(null);
  const rejectRef = useRef<HTMLButtonElement>(null);
  const modifyRef = useRef<HTMLButtonElement>(null);

  const commitOverride = (action: "approved" | "rejected" | "modified") => {
    if (!canOverride || !decisionId) return;
    // Audit-row-first: the mutation POSTs the audit endpoint and only marks the
    // decision acted on 2xx; the WS ack is operational confirmation only.
    override.mutate({
      decision_id: decisionId,
      action,
      reason: `Operator ${action} via oversight controls`,
    });
  };

  const commitSteering = (raw: number) => {
    if (!canSteer) return;
    // Steering clamp + sanitize (Req 3.7) then audit-row-first commit: the
    // store writes the audit row before applying locally and reverts the value
    // on failure, surfacing `lastError`.
    void setParetoWeight(steeringTarget, clampSteering(raw));
  };

  // Place default keyboard focus on the action `defaultFocusAction` selects
  // whenever the decision (or its confidence) changes, but only when override
  // is actionable so we never steal focus in a read-only context.
  useEffect(() => {
    if (!canOverride) return;
    const target =
      focusAction === "approve"
        ? approveRef.current
        : focusAction === "reject"
          ? rejectRef.current
          : modifyRef.current;
    target?.focus();
  }, [canOverride, focusAction, decisionId]);

  // Keyboard operability (Req 3.3, FE-INV-022). Shortcuts are only armed for a
  // role that may actuate oversight; a viewer's controls are inert.
  const shortcutMap = useMemo(
    () => ({
      approve: () => commitOverride("approved"),
      reject: () => commitOverride("rejected"),
      modify: () => commitOverride("modified"),
      next: () => onEscalateNext?.(),
      prev: () => onEscalatePrev?.(),
      escape: () => onDismiss?.(),
    }),
    // commitOverride depends on canOverride/decisionId; the callbacks are stable-enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [canOverride, decisionId, onEscalateNext, onEscalatePrev, onDismiss],
  );
  useCockpitShortcuts(shortcutMap, roleActionable);

  const overrideDisabled = !canOverride || override.isPending;
  const steerDisabled = !canSteer;

  return (
    <section
      aria-label="Oversight controls"
      className={cn("syn-card flex flex-col gap-4 p-4", className)}
    >
      <header className="flex items-center justify-between gap-3">
        <h2 className="font-display text-sm font-semibold uppercase tracking-[0.14em] text-ink-subtle">
          Oversight
        </h2>
        <span className="font-mono text-2xs tabular-nums text-ink-muted">
          conf {decisionConfidence.toFixed(2)}
        </span>
      </header>

      {/* Role restriction notice — communicate rather than fail silently (Req 12.5, 3.9). */}
      {!roleActionable && (
        <p
          id="oversight-role-restriction"
          role="note"
          className="rounded-md border border-border bg-surface-raised px-3 py-2 text-xs text-ink-muted"
        >
          Your role (<span className="font-mono text-ink">{role}</span>) is read-only. Oversight
          actions are shown but disabled.
        </p>
      )}

      {/* Override (approve / reject / modify) — audit-row-first (Req 3.1). */}
      <fieldset
        className="flex flex-col gap-2"
        disabled={overrideDisabled}
        aria-describedby={roleActionable ? undefined : "oversight-role-restriction"}
      >
        <legend className="text-2xs uppercase tracking-wide text-ink-subtle">Override</legend>
        <div className="flex flex-wrap gap-2">
          <OverrideButton
            ref={approveRef}
            action="approve"
            label="Approve"
            variant="success"
            keyboardKey="A"
            isDefaultFocus={focusAction === "approve"}
            disabled={overrideDisabled}
            onActivate={() => commitOverride("approved")}
          />
          <OverrideButton
            ref={rejectRef}
            action="reject"
            label="Reject"
            variant="danger"
            keyboardKey="R"
            isDefaultFocus={focusAction === "reject"}
            disabled={overrideDisabled}
            onActivate={() => commitOverride("rejected")}
          />
          <OverrideButton
            ref={modifyRef}
            action="modify"
            label="Modify"
            variant="warning"
            keyboardKey="M"
            isDefaultFocus={focusAction === "modify"}
            disabled={overrideDisabled}
            onActivate={() => commitOverride("modified")}
          />
        </div>
        {/* Non-color indication of WHY review was demanded (Req 12.6): a text
            glyph + words, never color alone. Names the stakes (irreversible
            and/or high blast-radius) that escalated review even at/above the
            0.80 gate, else the sub-gate confidence that demoted focus (Req 3.2). */}
        {reviewFocus.escalated && (
          <p
            className="flex items-start gap-1 text-2xs text-ink-muted"
            data-review-reason={reviewFocus.reason}
          >
            <span aria-hidden="true" className="font-mono">
              ⚠
            </span>
            <span>{reviewDemandMessage(decisionReversibility, decisionBlastRadius, reviewFocus.reason)}</span>
          </p>
        )}
        {/* Honest degradation (Req 12.5): the stakes fields the Backend_Contract
            does not expose are named as unavailable — never fabricated. */}
        {reviewFocus.degraded && (
          <p
            className="text-2xs text-ink-subtle"
            data-review-degraded="true"
            data-fields-unavailable={reviewFocus.fieldsUnavailable.join(",")}
          >
            {unavailableStakesMessage(reviewFocus.fieldsUnavailable)}
          </p>
        )}
        {normalizedViolations.length > 0 && (
          <p className="text-2xs text-ink-muted">
            {normalizedViolations.length} guardrail violation
            {normalizedViolations.length === 1 ? "" : "s"} on this decision.
          </p>
        )}
      </fieldset>

      {/* Steer — audit-row-first + clamp/sanitize (Req 3.6, 3.7). */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="oversight-steer"
          className="text-2xs uppercase tracking-wide text-ink-subtle"
        >
          Steer · {STEERING_LABEL[steeringTarget]} weight
        </label>
        <div className="flex items-center gap-3">
          <input
            id="oversight-steer"
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={paretoWeights[steeringTarget]}
            disabled={steerDisabled}
            aria-keyshortcuts="S"
            aria-describedby={roleActionable ? undefined : "oversight-role-restriction"}
            onChange={(e) => commitSteering(Number(e.target.value))}
            className="h-1 flex-1 accent-accent disabled:cursor-not-allowed disabled:opacity-50"
          />
          <span className="w-10 text-right font-mono text-2xs tabular-nums text-ink">
            {paretoWeights[steeringTarget].toFixed(2)}
          </span>
        </div>
        {steeringError && (
          <p role="alert" className="text-2xs text-signal-danger">
            Steering change not applied — {steeringError}
          </p>
        )}
      </div>

      {/* Secondary authority actions — interrupt, delegate, recover, navigate, dismiss. */}
      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        <CapabilityButton
          capability={findCapability(capabilities, "interrupt")}
          role={role}
          label="Interrupt"
          variant="danger"
          onActivate={onInterrupt}
        />
        <CapabilityButton
          capability={findCapability(capabilities, "recover")}
          role={role}
          label="Recover"
          variant="secondary"
          onActivate={onRecover}
        />
        <CapabilityButton
          capability={findCapability(capabilities, "delegate")}
          role={role}
          label="Delegate"
          variant="secondary"
          onActivate={onDelegate}
        />
        <CapabilityButton
          capability={findCapability(capabilities, "escalate-prev")}
          role={role}
          label="Previous"
          variant="outline"
          onActivate={onEscalatePrev}
        />
        <CapabilityButton
          capability={findCapability(capabilities, "escalate-next")}
          role={role}
          label="Next"
          variant="outline"
          onActivate={onEscalateNext}
        />
        <CapabilityButton
          capability={findCapability(capabilities, "dismiss")}
          role={role}
          label="Dismiss"
          variant="ghost"
          onActivate={onDismiss}
        />
      </div>
    </section>
  );
}

interface OverrideButtonProps {
  readonly action: FocusAction;
  readonly label: string;
  readonly variant: "success" | "danger" | "warning";
  readonly keyboardKey: string;
  readonly isDefaultFocus: boolean;
  readonly disabled: boolean;
  readonly onActivate: () => void;
}

const OverrideButton = forwardRef<HTMLButtonElement, OverrideButtonProps>(
  ({ action, label, variant, keyboardKey, isDefaultFocus, disabled, onActivate }, ref) => (
    <Button
      ref={ref}
      variant={variant}
      size="sm"
      disabled={disabled}
      data-action={action}
      data-default-focus={isDefaultFocus ? "true" : undefined}
      aria-keyshortcuts={keyboardKey}
      onClick={onActivate}
    >
      {label}
      <kbd className="ml-1 font-mono text-2xs opacity-70">{keyboardKey}</kbd>
    </Button>
  ),
);
OverrideButton.displayName = "OverrideButton";

interface CapabilityButtonProps {
  readonly capability: OversightCapability | undefined;
  readonly role: OperatorRole;
  readonly label: string;
  readonly variant: "danger" | "secondary" | "outline" | "ghost";
  readonly onActivate?: (() => void) | undefined;
}

/**
 * A single secondary capability. Always rendered (never hidden, Req 3.9):
 *   - actionable  → enabled and wired to its handler;
 *   - backend gap → disabled, labelled as an unavailable backend affordance (Req 3.8);
 *   - out of role → disabled, restriction communicated (Req 12.5).
 */
function CapabilityButton({ capability, role, label, variant, onActivate }: CapabilityButtonProps) {
  if (!capability) return null;

  const gap = isBackendGap(capability);
  const roleActionable = isCapabilityActionable(role, capability);
  // A capability with no wired handler cannot actuate even if authorized.
  const actionable = roleActionable && typeof onActivate === "function";
  const disabled = !actionable;

  const restriction = gap
    ? "No backing backend endpoint yet — unavailable."
    : !isOversightCapableRole(role)
      ? "Not available to your role."
      : undefined;

  return (
    <Button
      variant={variant}
      size="sm"
      disabled={disabled}
      data-capability={capability.id}
      data-backend-gap={gap ? "true" : undefined}
      aria-keyshortcuts={capability.keyboardKey}
      title={restriction}
      aria-description={restriction}
      onClick={() => onActivate?.()}
    >
      {label}
      <kbd className="ml-1 font-mono text-2xs opacity-70">{capability.keyboardKey}</kbd>
    </Button>
  );
}
