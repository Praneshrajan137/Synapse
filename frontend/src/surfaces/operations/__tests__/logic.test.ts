import type { CalibrationBin } from "@domain/operations";
import { describe, expect, it } from "vitest";
import { confidenceSamples, outcomeMix } from "../logic";

function bin(lo: number, n: number, observed: number | null): CalibrationBin {
  return { lo, hi: lo + 0.1, n, mean_confidence: lo + 0.05, observed_rate: observed };
}

describe("outcomeMix (FE-INV-041 tri-state)", () => {
  it("derives confirmed from bins and keeps unknown separate", () => {
    const mix = outcomeMix([bin(0.9, 4, 0.5)], 4, 3);
    expect(mix.confirmed).toBe(2);
    expect(mix.diverged).toBe(2);
    expect(mix.unknown).toBe(3); // NEVER folded into confirmed
    expect(mix.total).toBe(7);
  });

  it("never reports a positive outcome when nothing is scored", () => {
    const mix = outcomeMix([], 0, 5);
    expect(mix.confirmed).toBe(0);
    expect(mix.diverged).toBe(0);
    expect(mix.unknown).toBe(5);
  });

  it("clamps confirmed so rounding can't exceed the scored total", () => {
    const mix = outcomeMix([bin(0.9, 10, 1)], 8, 0);
    expect(mix.confirmed).toBe(8);
    expect(mix.diverged).toBe(0);
  });

  it("ignores bins with a null observed rate", () => {
    const mix = outcomeMix([bin(0.5, 3, null)], 3, 0);
    expect(mix.confirmed).toBe(0);
    expect(mix.diverged).toBe(3);
  });
});

describe("confidenceSamples (FE-INV-044 synthetic segmentation)", () => {
  const rows = [
    { confidence: 0.9, is_synthetic: false },
    { confidence: 0.5, is_synthetic: true },
    { confidence: 0.8 },
  ];

  it("excludes synthetic by default", () => {
    expect(confidenceSamples(rows, false)).toEqual([0.9, 0.8]);
  });

  it("includes synthetic only when asked", () => {
    expect(confidenceSamples(rows, true)).toEqual([0.9, 0.5, 0.8]);
  });
});
