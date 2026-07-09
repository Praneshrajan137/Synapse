import { type ChromaticTheme, confidenceColor } from "@lib/chromatics";
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { formatConfidence } from "../logic";

// Feature: atlas-console-elevation
// Property 13: Decisions carry two-decimal confidence, a gate-anchored color, and numeric text
//
// `formatConfidence` always renders exactly two decimals matching ^[01]\.\d{2}$
// (the numeric-text honesty channel that renders alongside any confidence
// colour), and `confidenceColor` is a continuous piecewise-linear scale whose
// interpolation knots sit EXACTLY at the I-5 gates {0.00, 0.70, 0.80, 1.00}.
//
// **Validates: Requirements 4.1, 4.2**

const TWO_DECIMAL = /^[01]\.\d{2}$/;

/** The gate anchors the confidence scale is required to be knotted at. */
const ANCHORS = [0, 0.7, 0.8, 1] as const;
const SEGMENTS: ReadonlyArray<readonly [number, number]> = [
  [0, 0.7],
  [0.7, 0.8],
  [0.8, 1],
];

interface Oklch {
  readonly l: number;
  readonly c: number;
  readonly h: number;
}

function parseOklch(s: string): Oklch {
  const m = /^oklch\((-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\)$/.exec(s);
  if (!m) throw new Error(`not an oklch string: ${s}`);
  return { l: Number(m[1]), c: Number(m[2]), h: Number(m[3]) };
}

describe("Property 13: two-decimal confidence, gate-anchored color, numeric text", () => {
  it("formats every possible confidence (incl. out-of-range / non-finite) as ^[01]\\.\\d{2}$", () => {
    const arbAny = fc.oneof(
      fc.double({ min: -5, max: 5, noNaN: true }),
      fc.double({ min: 0, max: 1, noNaN: true }),
      fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY),
    );
    fc.assert(
      fc.property(arbAny, (x) => {
        const out = formatConfidence(x);
        expect(out).toMatch(TWO_DECIMAL);
        // The rendered value is the clamp of the input into [0,1].
        const clamped = !Number.isFinite(x) ? 0 : x < 0 ? 0 : x > 1 ? 1 : x;
        expect(out).toBe(clamped.toFixed(2));
      }),
      { numRuns: 300 },
    );
  });

  it("returns a valid oklch(...) string for every value in [0,1] and both themes", () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 1, noNaN: true }),
        fc.constantFrom<ChromaticTheme[]>("light", "dark", "hc"),
        (v, theme) => {
          const s = confidenceColor(v, { theme });
          expect(s).toMatch(/^oklch\(/);
          const { l, c, h } = parseOklch(s);
          expect(Number.isFinite(l) && Number.isFinite(c) && Number.isFinite(h)).toBe(true);
        },
      ),
      { numRuns: 200 },
    );
  });

  it("is piecewise-linear within each gate-anchored segment (no interior knots)", () => {
    // If a knot existed anywhere other than the gate anchors, linear
    // interpolation within one of these segments would break.
    const arbSeg = fc.constantFrom(...SEGMENTS.map((_, i) => i));
    fc.assert(
      fc.property(arbSeg, fc.double({ min: 0.001, max: 0.999, noNaN: true }), (segIdx, t) => {
        const seg = SEGMENTS[segIdx];
        if (!seg) throw new Error("bad segment index");
        const [a, b] = seg;
        const v = a + t * (b - a);
        const lo = parseOklch(confidenceColor(a));
        const hi = parseOklch(confidenceColor(b));
        const act = parseOklch(confidenceColor(v));
        const predL = lo.l + t * (hi.l - lo.l);
        const predC = lo.c + t * (hi.c - lo.c);
        const predH = lo.h + t * (hi.h - lo.h);
        expect(Math.abs(act.l - predL)).toBeLessThan(0.01);
        expect(Math.abs(act.c - predC)).toBeLessThan(0.01);
        expect(Math.abs(act.h - predH)).toBeLessThan(0.2);
      }),
      { numRuns: 300 },
    );
  });

  it("has genuine interpolation knots exactly at the gates 0.70 and 0.80", () => {
    // A knot exists where the hue slope changes. Distinct slopes across each
    // gate prove the scale is anchored at {0.00, 0.70, 0.80, 1.00} and nowhere
    // else (interior linearity, above, rules out other knots).
    const h = ANCHORS.map((v) => parseOklch(confidenceColor(v)).h);
    // h = [h@0, h@0.7, h@0.8, h@1]
    const slope01 = (h[1]! - h[0]!) / (0.7 - 0);
    const slope12 = (h[2]! - h[1]!) / (0.8 - 0.7);
    const slope23 = (h[3]! - h[2]!) / (1 - 0.8);
    expect(Math.abs(slope12 - slope01)).toBeGreaterThan(1);
    expect(Math.abs(slope23 - slope12)).toBeGreaterThan(1);
  });
});
