// ============================================================================
// Testing layer 7 — Mutation. Proves the invariant checks have teeth: a
// corrupted token must be caught. Each test runs a check on the real palette
// (passes) and on a mutated palette (fails).
// ============================================================================
import { describe, it, expect } from "vitest";
import { AGENTS, THRESHOLDS, color } from "./_load.mjs";
import { deltaEOK } from "../build/cvd.mjs";

const minPairwise = (cols) => {
  let m = Infinity;
  for (let i = 0; i < cols.length; i++) {
    for (let j = i + 1; j < cols.length; j++) m = Math.min(m, deltaEOK(cols[i], cols[j]));
  }
  return m;
};
const strictlyDecreasing = (xs) => xs.every((x, i) => i === 0 || xs[i - 1] > x);
const strictlyIncreasing = (xs) => xs.every((x, i) => i === 0 || xs[i - 1] < x);

describe("Mutation — agent distinctness check catches a collapsed pair", () => {
  const cols = AGENTS.map((a) => color(`color.agent.${a}`, "dark"));

  it("real palette passes INV-CLR-004 threshold", () => {
    expect(minPairwise(cols)).toBeGreaterThanOrEqual(THRESHOLDS.agent_pair_min_deltaeok);
  });

  it("mutant (two agents made identical) fails the threshold", () => {
    const mutant = cols.map((c) => ({ ...c }));
    mutant[3] = { ...mutant[5] }; // freshness := disruption
    expect(minPairwise(mutant)).toBeLessThan(THRESHOLDS.agent_pair_min_deltaeok);
  });

  it("mutant (one agent hue nudged onto a neighbour) fails the threshold", () => {
    const mutant = cols.map((c) => ({ ...c }));
    mutant[0] = { ...mutant[0], h: mutant[1].h, l: mutant[1].l, c: mutant[1].c };
    expect(minPairwise(mutant)).toBeLessThan(THRESHOLDS.agent_pair_min_deltaeok);
  });
});

describe("Mutation — tier monotonicity check catches a reordering", () => {
  const tierL = [1, 2, 3, 4].map((n) => color(`color.tier.${n}`, "dark").l);

  it("real tier ramp is strictly decreasing (INV-CLR-006)", () => {
    expect(strictlyDecreasing(tierL)).toBe(true);
  });

  it("mutant (tier 3 lifted above tier 2) breaks monotonicity", () => {
    const mutant = [...tierL];
    mutant[2] = mutant[1] + 0.05;
    expect(strictlyDecreasing(mutant)).toBe(false);
  });
});

describe("Mutation — confidence hue monotonicity check catches a swap", () => {
  const hues = ["low", "escalation", "autonomous", "peak"].map(
    (k) => color(`color.confidence.${k}`, "dark").h,
  );

  it("real confidence stops have strictly increasing hue (INV-CLR-007)", () => {
    expect(strictlyIncreasing(hues)).toBe(true);
  });

  it("mutant (escalation and autonomous hues swapped) breaks the traversal", () => {
    const mutant = [...hues];
    [mutant[1], mutant[2]] = [mutant[2], mutant[1]];
    expect(strictlyIncreasing(mutant)).toBe(false);
  });
});
