import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { provenanceStatus, type ProvenanceLike } from "@ds/compounds/ProvenanceChip";

// Feature: atlas-console-elevation
// Property 16: Provenance is rendered when present, marked unavailable otherwise
//
// For a non-degraded proposal, `provenanceStatus` returns "present" iff the
// structured provenance is complete (model version AND feature source AND
// confidence basis all present), and "unavailable" when the provenance is
// absent or incomplete — never silently omitted.
//
// **Validates: Requirements 4.7**

const arbField = fc.option(fc.string({ minLength: 1, maxLength: 12 }), { nil: null });

// Non-degraded provenance: `degraded` is never true (that path is Property 17).
const arbNonDegraded: fc.Arbitrary<ProvenanceLike> = fc.record(
  {
    model_version: arbField,
    feature_source: arbField,
    confidence_basis: arbField,
  },
  { requiredKeys: [] },
);

describe("Property 16: provenance rendered when present, marked unavailable otherwise", () => {
  it("returns 'unavailable' for absent provenance (null / undefined)", () => {
    expect(provenanceStatus(null)).toBe("unavailable");
    expect(provenanceStatus(undefined)).toBe("unavailable");
  });

  it("returns 'present' iff complete, 'unavailable' otherwise (non-degraded)", () => {
    fc.assert(
      fc.property(arbNonDegraded, (p) => {
        const complete = Boolean(p.model_version && p.feature_source && p.confidence_basis);
        const status = provenanceStatus(p);
        expect(status).toBe(complete ? "present" : "unavailable");
        // The classification is always one of the disclosed tri-states.
        expect(["present", "unavailable"]).toContain(status);
      }),
      { numRuns: 300 },
    );
  });

  it("never returns 'present' when any required field is missing", () => {
    fc.assert(
      fc.property(arbNonDegraded, (p) => {
        if (provenanceStatus(p) === "present") {
          expect(p.model_version).toBeTruthy();
          expect(p.feature_source).toBeTruthy();
          expect(p.confidence_basis).toBeTruthy();
        }
      }),
      { numRuns: 300 },
    );
  });
});

// Feature: atlas-console-elevation
// Property 17: Degraded honesty marker is never suppressed
//
// For ANY provenance with `degraded === true`, `provenanceStatus` returns
// "degraded" — never "unavailable" or "present" — regardless of how complete
// or incomplete the rest of the structured provenance is. This guarantees the
// explicit degraded (fallback-path) label always renders and is never
// swallowed by a missing model version / feature source / confidence basis.
//
// **Validates: Requirements 4.8**

// Degraded provenance: `degraded` is fixed true; every other field is free
// (present, absent, or incomplete) so we prove the marker survives any shape.
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
  it("returns 'degraded' for any degraded=true provenance, whatever the other fields", () => {
    fc.assert(
      fc.property(arbDegraded, (p) => {
        expect(provenanceStatus(p)).toBe("degraded");
      }),
      { numRuns: 300 },
    );
  });

  it("never collapses a degraded proposal to 'unavailable' or 'present'", () => {
    fc.assert(
      fc.property(arbDegraded, (p) => {
        const status = provenanceStatus(p);
        expect(status).not.toBe("unavailable");
        expect(status).not.toBe("present");
      }),
      { numRuns: 300 },
    );
  });

  it("surfaces degraded even when the provenance is otherwise completely empty", () => {
    expect(provenanceStatus({ degraded: true })).toBe("degraded");
    expect(
      provenanceStatus({
        degraded: true,
        model_version: null,
        feature_source: null,
        confidence_basis: null,
      }),
    ).toBe("degraded");
  });
});
