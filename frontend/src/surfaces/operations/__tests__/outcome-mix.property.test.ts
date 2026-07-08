import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { outcomeMix } from "../logic";
import type { CalibrationBin } from "@domain/operations";

// Feature: atlas-console-elevation
// Property 14: Decision outcomes partition into a tri-state
//
// `outcomeMix` yields exactly three non-overlapping buckets — confirmed,
// diverged, unknown. `confirmed` is clamped to the scored total (rounding can
// never imply more confirmations than there were scored decisions) and
// `unknown` is carried straight through — NEVER folded into `confirmed`.
//
// **Validates: Requirements 4.3**

const arbBin: fc.Arbitrary<CalibrationBin> = fc.record({
  lo: fc.double({ min: 0, max: 1, noNaN: true }),
  hi: fc.double({ min: 0, max: 1, noNaN: true }),
  n: fc.nat({ max: 1000 }),
  mean_confidence: fc.option(fc.double({ min: 0, max: 1, noNaN: true }), { nil: null }),
  observed_rate: fc.option(fc.double({ min: 0, max: 1, noNaN: true }), { nil: null }),
});

const arbBins = fc.array(arbBin, { maxLength: 12 });
const arbCount = fc.nat({ max: 5000 });

describe("Property 14: decision outcomes partition into a tri-state", () => {
  it("produces exactly the confirmed | diverged | unknown buckets (plus total)", () => {
    fc.assert(
      fc.property(arbBins, arbCount, arbCount, (bins, nScored, nUnknown) => {
        const mix = outcomeMix(bins, nScored, nUnknown);
        expect(Object.keys(mix).sort()).toEqual(
          ["confirmed", "diverged", "total", "unknown"].sort(),
        );
        expect(Number.isInteger(mix.confirmed)).toBe(true);
        expect(mix.confirmed).toBeGreaterThanOrEqual(0);
        expect(mix.diverged).toBeGreaterThanOrEqual(0);
        expect(mix.unknown).toBeGreaterThanOrEqual(0);
      }),
      { numRuns: 300 },
    );
  });

  it("clamps confirmed to the scored total and partitions scored into confirmed + diverged", () => {
    fc.assert(
      fc.property(arbBins, arbCount, arbCount, (bins, nScored, nUnknown) => {
        const mix = outcomeMix(bins, nScored, nUnknown);
        // confirmed can never exceed the scored total.
        expect(mix.confirmed).toBeLessThanOrEqual(nScored);
        // confirmed + diverged exactly reconstitute the scored population.
        expect(mix.confirmed + mix.diverged).toBe(nScored);
        // unknown is a distinct bucket, carried through verbatim.
        expect(mix.unknown).toBe(nUnknown);
        // total accounts for every record across the two populations.
        expect(mix.total).toBe(nScored + nUnknown);
      }),
      { numRuns: 400 },
    );
  });

  it("never folds unknown into confirmed — confirmed is independent of nUnknown", () => {
    fc.assert(
      fc.property(arbBins, arbCount, arbCount, (bins, nScored, extraUnknown) => {
        const withoutUnknown = outcomeMix(bins, nScored, 0);
        const withUnknown = outcomeMix(bins, nScored, extraUnknown);
        // Adding unknown records changes neither confirmed nor diverged.
        expect(withUnknown.confirmed).toBe(withoutUnknown.confirmed);
        expect(withUnknown.diverged).toBe(withoutUnknown.diverged);
        // The unknown records land only in the unknown bucket.
        expect(withUnknown.unknown).toBe(extraUnknown);
        expect(withoutUnknown.unknown).toBe(0);
      }),
      { numRuns: 300 },
    );
  });
});
