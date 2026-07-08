import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { confidenceSamples } from "../logic";

// Feature: atlas-console-elevation
// Property 18: Synthetic decisions are excluded from trust aggregates by default
//
// `confidenceSamples` excludes every `is_synthetic` record by default; the
// labelled include toggle (includeSynthetic=true) adds back exactly those
// synthetic records and nothing else.
//
// **Validates: Requirements 4.9**

interface Row {
  readonly confidence: number;
  readonly is_synthetic?: boolean | undefined;
}

const arbRow: fc.Arbitrary<Row> = fc.record(
  {
    confidence: fc.double({ min: 0, max: 1, noNaN: true }),
    is_synthetic: fc.boolean(),
  },
  { requiredKeys: ["confidence"] },
);

const arbRows = fc.array(arbRow, { maxLength: 30 });

const sorted = (xs: readonly number[]): number[] => [...xs].sort((a, b) => a - b);

describe("Property 18: synthetic decisions excluded from trust aggregates by default", () => {
  it("default aggregate contains exactly the non-synthetic confidences, in order", () => {
    fc.assert(
      fc.property(arbRows, (rows) => {
        const out = confidenceSamples(rows, false);
        const expected = rows.filter((r) => !r.is_synthetic).map((r) => r.confidence);
        expect(out).toEqual(expected);
        // No synthetic record leaks into the default aggregate.
        expect(out.length).toBe(expected.length);
      }),
      { numRuns: 300 },
    );
  });

  it("includeSynthetic=true yields every confidence (order preserved)", () => {
    fc.assert(
      fc.property(arbRows, (rows) => {
        const out = confidenceSamples(rows, true);
        expect(out).toEqual(rows.map((r) => r.confidence));
      }),
      { numRuns: 300 },
    );
  });

  it("the toggle adds back exactly the synthetic records and nothing else", () => {
    fc.assert(
      fc.property(arbRows, (rows) => {
        const withDefault = confidenceSamples(rows, false);
        const withSynthetic = confidenceSamples(rows, true);
        const syntheticConfidences = rows.filter((r) => r.is_synthetic).map((r) => r.confidence);

        // The multiset delta between include=true and include=false is exactly
        // the synthetic confidences.
        expect(withSynthetic.length - withDefault.length).toBe(syntheticConfidences.length);

        const removeFirst = (arr: number[], v: number): boolean => {
          const idx = arr.indexOf(v);
          if (idx === -1) return false;
          arr.splice(idx, 1);
          return true;
        };
        const remaining = [...withSynthetic];
        for (const v of withDefault) {
          expect(removeFirst(remaining, v)).toBe(true);
        }
        expect(sorted(remaining)).toEqual(sorted(syntheticConfidences));
      }),
      { numRuns: 300 },
    );
  });
});
