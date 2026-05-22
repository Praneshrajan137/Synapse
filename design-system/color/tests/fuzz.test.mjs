// ============================================================================
// Testing layer 2 — Fuzz. Random OKLCH inputs and random confidence values
// must never crash the resolver and must always yield in-gamut, valid output.
// Seeded RNG (mulberry32) so CI is deterministic — repo pattern E-S5-12.
// ============================================================================
import { describe, it, expect } from "vitest";
import { gamutMap, isInGamut, toRgb, num } from "../build/resolve.mjs";
import { confidenceColor } from "../dist/tokens.ts";

function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

describe("Fuzz — gamut mapping is total and gamut-correct", () => {
  it("500 random OKLCH inputs all map in-gamut, preserving L and H", () => {
    const rng = mulberry32(424242);
    for (let i = 0; i < 500; i++) {
      const input = { mode: "oklch", l: rng(), c: rng() * 0.45, h: rng() * 360 };
      const out = gamutMap(input);
      expect(isInGamut(toRgb(out)), `iter ${i} in-gamut`).toBe(true);
      expect(out.l, `iter ${i} L preserved`).toBe(num(input.l, 4));
      expect(out.h, `iter ${i} H preserved`).toBe(num(input.h, 2));
      expect(out.c, `iter ${i} chroma not increased`).toBeLessThanOrEqual(num(input.c, 4) + 1e-9);
    }
  });
});

describe("Fuzz — confidence map is total over [0,1]", () => {
  it("500 random confidence values yield valid in-range OKLCH", () => {
    const rng = mulberry32(1337);
    for (let i = 0; i < 500; i++) {
      const v = rng();
      for (const theme of ["light", "dark"]) {
        const m = confidenceColor(v, theme).match(/oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)/);
        expect(m, `iter ${i} parseable`).not.toBeNull();
        const [l, c, h] = [+m[1], +m[2], +m[3]];
        expect(l).toBeGreaterThanOrEqual(0);
        expect(l).toBeLessThanOrEqual(1);
        expect(c).toBeGreaterThanOrEqual(0);
        expect(h).toBeGreaterThanOrEqual(0);
        expect(h).toBeLessThanOrEqual(360);
      }
    }
  });

  it("out-of-range confidence is clamped, not crashed", () => {
    expect(() => confidenceColor(-5, "dark")).not.toThrow();
    expect(() => confidenceColor(99, "light")).not.toThrow();
    expect(confidenceColor(-5, "dark")).toBe(confidenceColor(0, "dark"));
    expect(confidenceColor(99, "dark")).toBe(confidenceColor(1, "dark"));
  });
});
