// Property-based tests for the Expected_Review_Value stakes-aware attention
// model (Req 12). These exercise the single source of truth in
// `@lib/expected-review-value` that both the override-focus model and the
// rendering compound consume, so the UI can never drift from the verified
// escalation / degradation / focus decisions.
//
// fast-check + Vitest, numRuns >= 100 per property.
//
// This file is the shared home for Properties 15, 16, and 17. The reusable
// generators and imports below are intentionally self-contained so that later
// tasks can append their own `describe` blocks without restructuring.

import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { CONFIDENCE_GATE } from "../chromatics";
import {
  type BlastRadius,
  type ErvInput,
  type Reversibility,
  defaultFocusActionByErv,
  expectedReviewValue,
} from "../expected-review-value";

const GATE = CONFIDENCE_GATE.high; // 0.80 — the I-5 autonomy gate.

// ── Reusable generators ────────────────────────────────────────────────────

/** Any confidence, including non-finite and out-of-range values. */
const anyConfidenceArb: fc.Arbitrary<number> = fc.double();

/** A confidence strictly within the closed unit interval [0, 1]. */
const unitConfidenceArb: fc.Arbitrary<number> = fc.double({ min: 0, max: 1, noNaN: true });

/** A confidence at or above the 0.80 autonomy gate, up to 1.0. */
const atOrAboveGateArb: fc.Arbitrary<number> = fc.double({ min: GATE, max: 1, noNaN: true });

/** A present reversibility value (never null/undefined). */
const reversibilityArb: fc.Arbitrary<Reversibility> = fc.constantFrom("reversible", "irreversible");

/** A present blast-radius value (never null/undefined). */
const blastRadiusArb: fc.Arbitrary<BlastRadius> = fc.constantFrom("low", "medium", "high");

/**
 * A reversibility slot that may be present or absent. Absence is modelled as
 * `null`; `expectedReviewValue` treats `null` and `undefined` identically (both
 * mean the field is absent), so `null` alone fully exercises the absent-field
 * path while keeping the object literals well-typed under
 * `exactOptionalPropertyTypes` (no `undefined` assigned to an optional slot).
 */
const optionalReversibilityArb: fc.Arbitrary<Reversibility | null> = fc.oneof(
  reversibilityArb,
  fc.constant<Reversibility | null>(null),
);

/**
 * A blast-radius slot that may be present or absent. Absence is modelled as
 * `null` for the same reason as {@link optionalReversibilityArb}.
 */
const optionalBlastRadiusArb: fc.Arbitrary<BlastRadius | null> = fc.oneof(
  blastRadiusArb,
  fc.constant<BlastRadius | null>(null),
);

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-effectiveness, Property 15: An irreversible or
// high-blast-radius decision is escalated for review even when confidence is at
// or above the 0.80 gate
//
// Property 15: For any decision that is irreversible or high-blast-radius,
// `expectedReviewValue` escalates it for human review even when its confidence
// is at or above the 0.80 autonomy gate.
//
// Validates: Requirements 12.1, 12.2
// ─────────────────────────────────────────────────────────────────────────
describe("expectedReviewValue — Property 15: Stakes escalate review above the confidence gate", () => {
  it("escalates any irreversible-or-high-blast decision at or above the gate", () => {
    fc.assert(
      fc.property(
        atOrAboveGateArb,
        // Force at least one stakes flag by pairing a "must escalate" driver
        // with a free-ranging companion field.
        fc.record({
          reversibility: optionalReversibilityArb,
          blastRadius: optionalBlastRadiusArb,
        }),
        fc.constantFrom<"irreversible" | "high-blast">("irreversible", "high-blast"),
        (confidence, companion, driver) => {
          const input: ErvInput =
            driver === "irreversible"
              ? { confidence, reversibility: "irreversible", blastRadius: companion.blastRadius }
              : { confidence, reversibility: companion.reversibility, blastRadius: "high" };

          const result = expectedReviewValue(input);

          // Confident machine, high stakes → still escalates (Req 12.2).
          expect(result.escalate).toBe(true);
          expect(result.reason).not.toBe("none");
          expect(["irreversible", "high-blast"]).toContain(result.reason);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("escalates an irreversible-or-high-blast decision for ANY confidence (incl. non-finite)", () => {
    fc.assert(
      fc.property(
        anyConfidenceArb,
        optionalReversibilityArb,
        optionalBlastRadiusArb,
        fc.constantFrom<"irreversible" | "high-blast">("irreversible", "high-blast"),
        (confidence, reversibility, blastRadius, driver) => {
          const input: ErvInput =
            driver === "irreversible"
              ? { confidence, reversibility: "irreversible", blastRadius }
              : { confidence, reversibility, blastRadius: "high" };

          expect(expectedReviewValue(input).escalate).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("ranks a stakes-escalated confident decision strictly above any confidence-only decision", () => {
    fc.assert(
      fc.property(
        atOrAboveGateArb,
        fc.constantFrom<"irreversible" | "high-blast">("irreversible", "high-blast"),
        unitConfidenceArb,
        (stakesConfidence, driver, otherConfidence) => {
          const stakesInput: ErvInput =
            driver === "irreversible"
              ? { confidence: stakesConfidence, reversibility: "irreversible" }
              : { confidence: stakesConfidence, blastRadius: "high" };

          // A decision that carries no escalating stakes field: its value is
          // driven by confidence alone (in [0, 1]).
          const confidenceOnly: ErvInput = {
            confidence: otherConfidence,
            reversibility: "reversible",
            blastRadius: "low",
          };

          const stakes = expectedReviewValue(stakesInput);
          const plain = expectedReviewValue(confidenceOnly);

          expect(stakes.escalate).toBe(true);
          expect(stakes.value).toBeGreaterThan(plain.value);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("holds the gate boundary exactly: irreversible at 0.80 confidence still escalates", () => {
    expect(expectedReviewValue({ confidence: GATE, reversibility: "irreversible" }).escalate).toBe(
      true,
    );
    expect(expectedReviewValue({ confidence: GATE, blastRadius: "high" }).escalate).toBe(true);
    // A perfectly confident machine does not buy out of stakes review.
    expect(expectedReviewValue({ confidence: 1, reversibility: "irreversible" }).escalate).toBe(
      true,
    );
    expect(expectedReviewValue({ confidence: 1, blastRadius: "high" }).escalate).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-effectiveness, Property 16: When reversibility/blast-radius
// are absent, Expected_Review_Value falls back to confidence-only ranking and
// flags the fields unavailable, never fabricating a value
//
// Property 16: When reversibility and/or blast-radius are absent (null or
// omitted/undefined), `expectedReviewValue` marks the result degraded, lists
// each absent field in `fieldsUnavailable`, falls back to a confidence-only
// ranking for the missing stakes, and never fabricates a stakes value or a
// stakes escalation reason for an absent field.
//
// Validates: Requirements 12.5
// ─────────────────────────────────────────────────────────────────────────
describe("expectedReviewValue — Property 16: Honest degradation when stakes fields are absent", () => {
  it("flags each absent stakes field and degrades iff any field is absent", () => {
    fc.assert(
      fc.property(
        unitConfidenceArb,
        optionalReversibilityArb,
        optionalBlastRadiusArb,
        (confidence, reversibility, blastRadius) => {
          const result = expectedReviewValue({ confidence, reversibility, blastRadius });

          const reversibilityAbsent = reversibility === null;
          const blastAbsent = blastRadius === null;

          // Each absent field — and only an absent field — is flagged unavailable.
          expect(result.fieldsUnavailable.includes("reversibility")).toBe(reversibilityAbsent);
          expect(result.fieldsUnavailable.includes("blastRadius")).toBe(blastAbsent);

          // Degraded exactly when at least one stakes field is absent.
          expect(result.degraded).toBe(reversibilityAbsent || blastAbsent);

          // An absent field NEVER fabricates its stakes escalation reason.
          if (reversibilityAbsent) expect(result.reason).not.toBe("irreversible");
          if (blastAbsent) expect(result.reason).not.toBe("high-blast");
        },
      ),
      { numRuns: 100 },
    );
  });

  it("falls back to a confidence-only ranking when BOTH stakes fields are absent (no fabricated stakes)", () => {
    fc.assert(
      fc.property(unitConfidenceArb, (confidence) => {
        const result = expectedReviewValue({ confidence, reversibility: null, blastRadius: null });

        // Fully degraded and both fields flagged unavailable.
        expect(result.degraded).toBe(true);
        expect([...result.fieldsUnavailable].sort()).toEqual(["blastRadius", "reversibility"]);

        // Ranking is confidence-only: value depends solely on confidence and no
        // stakes weight is fabricated. For confidence in [0, 1], the stakes-free
        // value is exactly (1 - confidence).
        expect(result.value).toBeCloseTo(1 - confidence, 10);

        // Escalation, if any, is driven by confidence alone — never a stakes reason.
        expect(result.escalate).toBe(confidence < GATE);
        expect(["low-confidence", "none"]).toContain(result.reason);
      }),
      { numRuns: 100 },
    );
  });

  it("uses a present stakes field while still flagging its absent companion", () => {
    fc.assert(
      fc.property(
        unitConfidenceArb,
        fc.constantFrom<"irreversible" | "high-blast">("irreversible", "high-blast"),
        (confidence, driver) => {
          // Exactly one stakes field present (the escalating driver); the other absent.
          const result =
            driver === "irreversible"
              ? expectedReviewValue({
                  confidence,
                  reversibility: "irreversible",
                  blastRadius: null,
                })
              : expectedReviewValue({ confidence, reversibility: null, blastRadius: "high" });

          // Present field still escalates on its genuine stakes…
          expect(result.escalate).toBe(true);
          expect(result.reason).toBe(driver === "irreversible" ? "irreversible" : "high-blast");

          // …while the absent companion is honestly flagged and marks degradation.
          expect(result.degraded).toBe(true);
          expect(result.fieldsUnavailable).toContain(
            driver === "irreversible" ? "blastRadius" : "reversibility",
          );
        },
      ),
      { numRuns: 100 },
    );
  });

  it("treats an omitted (undefined) stakes field identically to an explicit null", () => {
    fc.assert(
      fc.property(unitConfidenceArb, (confidence) => {
        // Omitting the optional fields yields `undefined` at runtime; this must
        // be indistinguishable from an explicit `null` (both mean absent).
        const omitted = expectedReviewValue({ confidence });
        const nulled = expectedReviewValue({ confidence, reversibility: null, blastRadius: null });
        expect(omitted).toEqual(nulled);
      }),
      { numRuns: 100 },
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-effectiveness, Property 17: Default override focus is
// derived from Expected_Review_Value, superseding the confidence-only focus model
//
// Property 17: For any set of decisions, the default override focus
// (`defaultFocusActionByErv`) is the index that MAXIMIZES Expected_Review_Value
// across the set — resolving ties to the lowest index and returning -1 for an
// empty set. Because ERV is stakes-aware, focus is ERV-derived rather than
// confidence-only: an irreversible / high-blast decision is focused over a
// higher-confidence reversible / low-blast one, superseding confidence-only focus.
//
// Validates: Requirements 12.3
// ─────────────────────────────────────────────────────────────────────────

/**
 * An arbitrary decision exercising every confidence value and each present /
 * absent stakes combination. `null` models an absent field (never `undefined`),
 * keeping the literal well-typed under `exactOptionalPropertyTypes`.
 */
const ervInputArb: fc.Arbitrary<ErvInput> = fc.record({
  confidence: unitConfidenceArb,
  reversibility: optionalReversibilityArb,
  blastRadius: optionalBlastRadiusArb,
});

describe("defaultFocusActionByErv — Property 17: Default focus is derived from Expected_Review_Value", () => {
  it("returns the index maximizing Expected_Review_Value (ties → lowest index)", () => {
    fc.assert(
      fc.property(fc.array(ervInputArb, { minLength: 1, maxLength: 12 }), (decisions) => {
        const focus = defaultFocusActionByErv(decisions);

        // A non-empty set always focuses a real, in-range index.
        expect(focus).toBeGreaterThanOrEqual(0);
        expect(focus).toBeLessThan(decisions.length);

        const values = decisions.map((d) => expectedReviewValue(d).value);
        const maxValue = Math.max(...values);

        // The focused decision attains the maximum Expected_Review_Value…
        expect(values[focus]).toBeCloseTo(maxValue, 12);

        // …and is the FIRST such maximizer (ties resolve to the lowest index).
        // `maxValue` is one of the array's own doubles, so `===` is exact here.
        const firstMax = values.findIndex((v) => v === maxValue);
        expect(focus).toBe(firstMax);
      }),
      { numRuns: 100 },
    );
  });

  it("returns -1 for an empty set (there is nothing to focus)", () => {
    expect(defaultFocusActionByErv([])).toBe(-1);
  });

  it("focuses a stakes decision over a higher-confidence reversible/low-blast one (ERV supersedes confidence-only)", () => {
    fc.assert(
      fc.property(
        // The stakes decision is itself confident (at or above the gate)…
        atOrAboveGateArb,
        // …and the "safe" decision may be even more confident.
        unitConfidenceArb,
        fc.constantFrom<"irreversible" | "high-blast">("irreversible", "high-blast"),
        (stakesConfidence, plainConfidence, driver) => {
          const stakes: ErvInput =
            driver === "irreversible"
              ? { confidence: stakesConfidence, reversibility: "irreversible", blastRadius: "low" }
              : { confidence: stakesConfidence, reversibility: "reversible", blastRadius: "high" };

          // A confidence-only "safe" decision: reversible + low blast radius.
          const plain: ErvInput = {
            confidence: plainConfidence,
            reversibility: "reversible",
            blastRadius: "low",
          };

          // Whatever the ordering, focus lands on the stakes decision — a
          // confidence-only focus model could have picked the plain one.
          expect(defaultFocusActionByErv([stakes, plain])).toBe(0);
          expect(defaultFocusActionByErv([plain, stakes])).toBe(1);
        },
      ),
      { numRuns: 100 },
    );
  });
});
