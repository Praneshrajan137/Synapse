import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { provenanceStatus, type ProvenanceLike } from "@ds/compounds/ProvenanceChip";

// Feature: atlas-console-elevation
// Property 17: Degraded honesty marker is never suppressed
//
// Whenever `degraded === true`, `provenanceStatus` returns "degraded"
// regardless of how complete or incomplete the rest of the structured
// provenance is — running on a fallback path must ALWAYS look like reduced
// information (Req 4.8 wins over completeness).
//
// **Validates: Requirements 4.8**

const arbField = fc.option(fc.string({ minLength: 1, maxLength: 12 }), { nil: null });

// Provenance that is always flagged degraded, with arbitrary completeness of
// every other field (present-and-set, present-and-null, or absent).
const arbDegraded: fc.Arbitrary<ProvenanceLike> = fc.record(
  {
    model_version: arbField,
    feature_source: arbField,
    confidence_basis: arbField,
    degraded: fc.constant(true),
  },
  { requiredKeys: ["degraded"] },
);

describe("Property 17: degraded honesty marker is never suppressed", () => {
  it("always returns 'degraded' when degraded=true, regardless of completeness", () => {
    fc.assert(
      fc.property(arbDegraded, (p) => {
        expect(provenanceStatus(p)).toBe("degraded");
      }),
      { numRuns: 300 },
    );
  });

  it("returns 'degraded' even for otherwise-complete provenance (never 'present')", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 12 }),
        fc.string({ minLength: 1, maxLength: 12 }),
        fc.string({ minLength: 1, maxLength: 12 }),
        (model_version, feature_source, confidence_basis) => {
          const p: ProvenanceLike = {
            model_version,
            feature_source,
            confidence_basis,
            degraded: true,
          };
          const status = provenanceStatus(p);
          expect(status).toBe("degraded");
          expect(status).not.toBe("present");
          expect(status).not.toBe("unavailable");
        },
      ),
      { numRuns: 200 },
    );
  });
});
