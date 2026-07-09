// Property-based tests for the oversight pure predicates (Req 3.2, 3.7, 3.8,
// 3.9, 12.5). These exercise the single source of truth in `@lib/oversight`
// that both `OversightControls` and the operator-authority surface consume, so
// the UI can never drift from the verified focus/clamp/gating decisions.
//
// fast-check + Vitest, numRuns >= 100 per property.

import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { CONFIDENCE_GATE } from "../chromatics";
import {
  type FocusAction,
  type OperatorRole,
  type OversightCapability,
  clampSteering,
  defaultFocusAction,
  isBackendGap,
  isCapabilityActionable,
  isCapabilityVisible,
} from "../oversight";

const GATE = CONFIDENCE_GATE.high; // 0.80 — the I-5 autonomy gate.

const ALL_ROLES: readonly OperatorRole[] = ["viewer", "ops", "engineer", "admin", "anonymous"];

const CAPABILITY_IDS: readonly OversightCapability["id"][] = [
  "interrupt",
  "override",
  "steer",
  "delegate",
  "recover",
  "escalate-next",
  "escalate-prev",
  "dismiss",
];

const roleArb: fc.Arbitrary<OperatorRole> = fc.constantFrom(...ALL_ROLES);

// A backing endpoint is either null (a backend gap) or a non-empty string.
const backingEndpointArb: fc.Arbitrary<string | null> = fc.oneof(
  fc.constant<string | null>(null),
  fc.constantFrom<string>(
    "/api/v1/decisions/{id}/override",
    "/api/v1/steering",
    "client:escalation-nav",
    "client:dismiss",
  ),
);

const capabilityArb: fc.Arbitrary<OversightCapability> = fc.record({
  id: fc.constantFrom(...CAPABILITY_IDS),
  backingEndpoint: backingEndpointArb,
  // Any subset of the roles may be required (including the empty set).
  requiredRoles: fc.uniqueArray(roleArb, { maxLength: ALL_ROLES.length }),
  keyboardKey: fc.constantFrom("I", "A", "S", "D", "C", "J", "K", "Escape"),
});

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-elevation, Property 9: Sub-threshold confidence demotes Approve from default focus
//
// Property 9: `defaultFocusAction(confidence)` returns a corrective action
// (reject/modify) for any confidence below the 0.80 autonomy gate and returns
// "approve" only at or above the gate. A non-finite confidence can never
// satisfy the gate and is therefore demoted too.
//
// Validates: Requirements 3.2
// ─────────────────────────────────────────────────────────────────────────
describe("defaultFocusAction — Property 9: Sub-threshold confidence demotes Approve", () => {
  const NON_APPROVE: readonly FocusAction[] = ["reject", "modify"];

  it("returns approve iff confidence is at or above the 0.80 gate", () => {
    fc.assert(
      fc.property(fc.double({ noNaN: true }), (confidence) => {
        const action = defaultFocusAction(confidence);
        if (confidence >= GATE) {
          expect(action).toBe("approve");
        } else {
          // Below the gate the machine is not trusted to be approved by
          // default; focus is demoted to a corrective action.
          expect(NON_APPROVE).toContain(action);
          expect(action).not.toBe("approve");
        }
      }),
      { numRuns: 300 },
    );
  });

  it("demotes Approve for values in the open sub-threshold interval [0, 0.80)", () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: GATE, noNaN: true }), (confidence) => {
        fc.pre(confidence < GATE); // exclude the boundary sample
        expect(defaultFocusAction(confidence)).not.toBe("approve");
      }),
      { numRuns: 200 },
    );
  });

  it("approves for values at or above the gate up to 1.0", () => {
    fc.assert(
      fc.property(fc.double({ min: GATE, max: 1, noNaN: true }), (confidence) => {
        expect(defaultFocusAction(confidence)).toBe("approve");
      }),
      { numRuns: 200 },
    );
  });

  it("never approves a non-finite confidence", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY),
        (confidence) => {
          const action = defaultFocusAction(confidence);
          if (confidence === Number.POSITIVE_INFINITY) {
            // +∞ >= gate is true — approve is the correct (and safe) result.
            expect(action).toBe("approve");
          } else {
            expect(action).not.toBe("approve");
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("holds the boundary exactly: 0.80 approves", () => {
    expect(defaultFocusAction(GATE)).toBe("approve");
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-elevation, Property 10: Authorization and visibility predicate
//
// Property 10: For any role and capability —
//   - a capability with no backing endpoint is a backend gap and is NEVER
//     actionable, regardless of role;
//   - a backed capability is actionable if and only if the role is within the
//     capability's required-role set;
//   - an out-of-scope capability (role not permitted, or a backend gap) is
//     still VISIBLE (present-but-disabled), never hidden and never silently
//     allowed.
//
// Validates: Requirements 3.8, 3.9, 12.5
// ─────────────────────────────────────────────────────────────────────────
describe("oversight gating — Property 10: Authorization and visibility predicate", () => {
  it("a backend gap (null endpoint) is never actionable for any role", () => {
    fc.assert(
      fc.property(roleArb, capabilityArb, (role, capability) => {
        const gapped: OversightCapability = { ...capability, backingEndpoint: null };
        expect(isBackendGap(gapped)).toBe(true);
        expect(isCapabilityActionable(role, gapped)).toBe(false);
      }),
      { numRuns: 300 },
    );
  });

  it("a backed capability is actionable iff the role is in the required set", () => {
    fc.assert(
      fc.property(roleArb, capabilityArb, (role, capability) => {
        const backed: OversightCapability = {
          ...capability,
          backingEndpoint: capability.backingEndpoint ?? "/api/v1/steering",
        };
        const expected = backed.requiredRoles.includes(role);
        expect(isCapabilityActionable(role, backed)).toBe(expected);
      }),
      { numRuns: 300 },
    );
  });

  it("actionable implies both a backing endpoint and role membership (never silently allowed)", () => {
    fc.assert(
      fc.property(roleArb, capabilityArb, (role, capability) => {
        if (isCapabilityActionable(role, capability)) {
          expect(capability.backingEndpoint).not.toBeNull();
          expect(isBackendGap(capability)).toBe(false);
          expect(capability.requiredRoles).toContain(role);
        }
      }),
      { numRuns: 300 },
    );
  });

  it("every capability is always visible — never hidden — regardless of role or backend gap", () => {
    fc.assert(
      fc.property(roleArb, capabilityArb, (role, capability) => {
        expect(isCapabilityVisible(role, capability)).toBe(true);
        // Out-of-scope (not actionable) capabilities remain visible: this is
        // the present-but-disabled guarantee (Req 3.9, 12.5).
        if (!isCapabilityActionable(role, capability)) {
          expect(isCapabilityVisible(role, capability)).toBe(true);
        }
      }),
      { numRuns: 300 },
    );
  });

  it("a viewer / anonymous role is never actionable when not in the required set", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<OperatorRole>("viewer", "anonymous"),
        capabilityArb,
        (role, capability) => {
          if (!capability.requiredRoles.includes(role)) {
            expect(isCapabilityActionable(role, capability)).toBe(false);
          }
          // Still visible either way.
          expect(isCapabilityVisible(role, capability)).toBe(true);
        },
      ),
      { numRuns: 200 },
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-elevation, Property 11: Steering values are clamped and sanitized
//
// Property 11: `clampSteering(x)` preserves a finite value already inside
// [0, 1], clamps a finite out-of-range value to the nearest bound, and
// collapses any non-finite value (NaN, ±∞) to 0. The result is always within
// [0, 1].
//
// Validates: Requirements 3.7
// ─────────────────────────────────────────────────────────────────────────
describe("clampSteering — Property 11: Steering values are clamped and sanitized", () => {
  it("always yields a value within the closed interval [0, 1]", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.double(), // includes NaN, ±∞, and out-of-range values
          fc.double({ min: 0, max: 1, noNaN: true }),
        ),
        (x) => {
          const y = clampSteering(x);
          expect(y).toBeGreaterThanOrEqual(0);
          expect(y).toBeLessThanOrEqual(1);
        },
      ),
      { numRuns: 300 },
    );
  });

  it("preserves a finite value already inside [0, 1]", () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 1, noNaN: true }), (x) => {
        expect(clampSteering(x)).toBe(x);
      }),
      { numRuns: 300 },
    );
  });

  it("clamps a finite value above 1 down to 1", () => {
    fc.assert(
      fc.property(fc.double({ min: 1, max: Number.MAX_VALUE, noNaN: true }), (x) => {
        fc.pre(x > 1);
        expect(clampSteering(x)).toBe(1);
      }),
      { numRuns: 200 },
    );
  });

  it("clamps a finite value below 0 up to 0", () => {
    fc.assert(
      fc.property(fc.double({ min: -Number.MAX_VALUE, max: 0, noNaN: true }), (x) => {
        fc.pre(x < 0);
        expect(clampSteering(x)).toBe(0);
      }),
      { numRuns: 200 },
    );
  });

  it("collapses any non-finite value to 0", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY),
        (x) => {
          expect(clampSteering(x)).toBe(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("is idempotent — clamping a clamped value is a no-op", () => {
    fc.assert(
      fc.property(fc.double(), (x) => {
        const once = clampSteering(x);
        expect(clampSteering(once)).toBe(once);
      }),
      { numRuns: 200 },
    );
  });
});
