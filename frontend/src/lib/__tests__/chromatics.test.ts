import { describe, expect, it } from "vitest";
import {
  CONFIDENCE_GATE,
  type ChromaticTheme,
  confidenceColor,
  confidenceZone,
  rationedAgentColor,
  vsupChromaFactor,
} from "../chromatics";

// Parse an `oklch(L C H)` string back into numbers for assertions.
function parseOklch(value: string): { l: number; c: number; h: number } {
  const m = /^oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)$/.exec(value);
  if (!m) throw new Error(`not an oklch string: ${value}`);
  return { l: Number(m[1]), c: Number(m[2]), h: Number(m[3]) };
}

describe("confidenceZone — I-5 gates", () => {
  it("classifies against the 0.70 / 0.80 gates", () => {
    expect(confidenceZone(0.0)).toBe("low");
    expect(confidenceZone(0.699)).toBe("low");
    expect(confidenceZone(0.7)).toBe("escalation");
    expect(confidenceZone(0.799)).toBe("escalation");
    expect(confidenceZone(0.8)).toBe("autonomous");
    expect(confidenceZone(1)).toBe("autonomous");
  });

  it("exposes the gate constants the BE escalation logic uses", () => {
    expect(CONFIDENCE_GATE.low).toBe(0.7);
    expect(CONFIDENCE_GATE.high).toBe(0.8);
  });
});

describe("confidenceColor — gate-anchored diverging scale (INV-CLR-007)", () => {
  it("returns a well-formed oklch string", () => {
    expect(confidenceColor(0.5)).toMatch(/^oklch\([\d.]+ [\d.]+ [\d.]+\)$/);
  });

  it("hue sweeps red → amber → green → teal as confidence rises (monotone)", () => {
    const hues = [0, 0.35, 0.7, 0.8, 0.9, 1].map((v) => parseOklch(confidenceColor(v)).h);
    for (let i = 1; i < hues.length; i++) {
      const cur = hues[i];
      const prev = hues[i - 1];
      if (cur === undefined || prev === undefined) continue;
      expect(cur).toBeGreaterThanOrEqual(prev);
    }
    // Red-ish at the bottom, teal-ish at the top (dark stops: 27° → 184°).
    expect(hues.at(0)).toBeCloseTo(27, 0);
    expect(hues.at(-1)).toBeCloseTo(184, 0);
  });

  it("interpolates the hue exactly at the I-5 gate anchors", () => {
    expect(parseOklch(confidenceColor(0.7)).h).toBeCloseTo(80, 0); // low gate (dark)
    expect(parseOklch(confidenceColor(0.8)).h).toBeCloseTo(148, 0); // high gate (dark)
  });

  it("light + dark themes differ but both stay well-formed", () => {
    const dark = confidenceColor(0.75, { theme: "dark" });
    const light = confidenceColor(0.75, { theme: "light" });
    expect(dark).not.toBe(light);
    expect(light).toMatch(/^oklch\(/);
  });

  it("clamps out-of-range values into [0,1]", () => {
    expect(confidenceColor(-3)).toBe(confidenceColor(0));
    expect(confidenceColor(42)).toBe(confidenceColor(1));
  });

  it("is deterministic", () => {
    expect(confidenceColor(0.63)).toBe(confidenceColor(0.63));
  });

  it("hc theme borrows the dark scale (numeric readout carries the value)", () => {
    expect(confidenceColor(0.6, { theme: "hc" as ChromaticTheme })).toBe(
      confidenceColor(0.6, { theme: "dark" }),
    );
  });
});

describe("vsupChromaFactor — uncertainty drains chroma (VSUP)", () => {
  it("is full above the high gate and floored far below", () => {
    expect(vsupChromaFactor(0.8)).toBe(1);
    expect(vsupChromaFactor(0.95)).toBe(1);
    expect(vsupChromaFactor(0.2)).toBeCloseTo(0.15, 5);
    expect(vsupChromaFactor(0)).toBeCloseTo(0.15, 5);
  });

  it("is monotonic non-decreasing in confidence", () => {
    let prev = -1;
    for (let v = 0; v <= 1.0001; v += 0.05) {
      const f = vsupChromaFactor(v);
      expect(f).toBeGreaterThanOrEqual(prev);
      prev = f;
    }
  });

  it("partially drains the escalation band (0.70 → 0.55)", () => {
    expect(vsupChromaFactor(0.7)).toBeCloseTo(0.55, 5);
    // halfway through the band → halfway to full
    expect(vsupChromaFactor(0.75)).toBeCloseTo(0.775, 5);
  });
});

describe("confidenceColor with VSUP", () => {
  it("suppresses chroma below the gate but preserves L and H", () => {
    const plain = parseOklch(confidenceColor(0.55, { vsup: false }));
    const drained = parseOklch(confidenceColor(0.55, { vsup: true }));
    expect(drained.c).toBeLessThan(plain.c);
    expect(drained.l).toBeCloseTo(plain.l, 4); // lightness untouched
    expect(drained.h).toBeCloseTo(plain.h, 2); // hue untouched
  });

  it("leaves high-confidence colour untouched (factor 1 above the gate)", () => {
    expect(confidenceColor(0.9, { vsup: true })).toBe(confidenceColor(0.9, { vsup: false }));
  });
});

describe("rationedAgentColor — quiet-by-default", () => {
  it("mixes toward the neutral base at rest, full hue at activity", () => {
    const rest = rationedAgentColor("var(--syn-agent-pricing-oracle)", 0);
    const active = rationedAgentColor("var(--syn-agent-pricing-oracle)", 1);
    expect(rest).toContain("18%");
    expect(active).toContain("100%");
    expect(rest).toContain("color-mix(in oklab");
    expect(rest).toContain("var(--syn-neutral-mix)");
  });

  it("clamps activity into [0,1]", () => {
    expect(rationedAgentColor("var(--x)", -1)).toContain("18%");
    expect(rationedAgentColor("var(--x)", 5)).toContain("100%");
  });

  it("never emits a raw colour literal (INV-CLR-009)", () => {
    const s = rationedAgentColor("var(--syn-agent-demand-prophet)", 0.5);
    expect(s).not.toMatch(/#[0-9a-f]{3,8}/i);
    expect(s).not.toMatch(/\b(rgba?|hsla?)\s*\(/);
  });
});
