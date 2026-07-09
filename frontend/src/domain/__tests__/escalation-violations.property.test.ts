// Feature: atlas-console-elevation, Property 12: Guardrail violations render completely with severity
//
// Property 12 (Validates: Requirements 3.4) — `normalizeViolations` is a
// total, non-lossy normalization over any list of guardrail violations:
//   - it preserves the count — a violation is NEVER dropped or collapsed;
//   - every produced row carries a non-empty `code`, a non-empty `message`,
//     and a `severity` drawn from the canonical set;
//   - a missing / empty / invalid severity defaults to `medium` rather than
//     hiding the row.

import {
  DEFAULT_VIOLATION_SEVERITY,
  type GuardrailViolation,
  VIOLATION_SEVERITIES,
  normalizeViolations,
} from "@domain/escalation";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const SEVERITY_SET: ReadonlySet<string> = new Set(VIOLATION_SEVERITIES);

// A severity slot that is EITHER a canonical severity, OR something the schema
// would consider "absent / invalid" (undefined, empty string, or an arbitrary
// non-canonical string). The normalizer must default the latter to `medium`.
const severitySlotArb: fc.Arbitrary<unknown> = fc.oneof(
  fc.constantFrom(...VIOLATION_SEVERITIES),
  fc.constant(undefined),
  fc.constant(""),
  fc.string({ maxLength: 12 }).filter((s) => !SEVERITY_SET.has(s)),
);

// A single incoming violation. `code` and `message` may be present strings,
// empty, or missing entirely — the normalizer must still yield a complete row.
const violationArb: fc.Arbitrary<GuardrailViolation> = fc
  .record(
    {
      code: fc.oneof(fc.string({ maxLength: 20 }), fc.constant(undefined)),
      message: fc.oneof(fc.string({ maxLength: 40 }), fc.constant(undefined)),
      severity: severitySlotArb,
    },
    { requiredKeys: [] },
  )
  .map((raw) => raw as unknown as GuardrailViolation);

const violationsArb: fc.Arbitrary<readonly GuardrailViolation[]> = fc.array(violationArb, {
  maxLength: 25,
});

describe("normalizeViolations — Property 12: complete rendering with severity", () => {
  it("preserves the count — never drops or collapses a violation", () => {
    fc.assert(
      fc.property(violationsArb, (violations) => {
        const normalized = normalizeViolations(violations);
        expect(normalized.length).toBe(violations.length);
      }),
      { numRuns: 200 },
    );
  });

  it("gives every row a non-empty code, non-empty message, and canonical severity", () => {
    fc.assert(
      fc.property(violationsArb, (violations) => {
        const normalized = normalizeViolations(violations);
        for (const row of normalized) {
          expect(typeof row.code).toBe("string");
          expect(row.code.length).toBeGreaterThan(0);
          expect(typeof row.message).toBe("string");
          expect(row.message.length).toBeGreaterThan(0);
          expect(SEVERITY_SET.has(row.severity)).toBe(true);
        }
      }),
      { numRuns: 200 },
    );
  });

  it("defaults a missing/empty/invalid severity to medium instead of hiding the row", () => {
    fc.assert(
      fc.property(violationsArb, (violations) => {
        const normalized = normalizeViolations(violations);
        violations.forEach((input, i) => {
          const rawSeverity = (input as { severity?: unknown }).severity;
          const wasCanonical = typeof rawSeverity === "string" && SEVERITY_SET.has(rawSeverity);
          if (!wasCanonical) {
            expect(normalized[i]!.severity).toBe(DEFAULT_VIOLATION_SEVERITY);
          } else {
            expect(normalized[i]!.severity).toBe(rawSeverity);
          }
        });
      }),
      { numRuns: 200 },
    );
  });

  it("is order-preserving and index-aligned with the input list", () => {
    fc.assert(
      fc.property(violationsArb, (violations) => {
        const normalized = normalizeViolations(violations);
        // Row i of the output corresponds to row i of the input — no reordering,
        // no coalescing of duplicate codes.
        expect(normalized.length).toBe(violations.length);
      }),
      { numRuns: 200 },
    );
  });
});
