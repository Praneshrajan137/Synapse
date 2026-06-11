import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  AGENT_STATE_FACTOR,
  type AgentProcessState,
  CONFIDENCE_GATE,
  type ChromaticTheme,
  confidenceColor,
  confidenceZone,
  degradedStateColor,
  processStateColor,
  rationedAgentColor,
  syntheticStateColor,
  vsupChromaFactor,
} from "../chromatics";

// The canonical token build — the FE mirrors below are pinned against it so
// the two systems cannot drift (frontend/src/lib/__tests__ → repo root).
const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const DIST_TOKENS = JSON.parse(
  readFileSync(join(REPO_ROOT, "design-system", "color", "dist", "tokens.json"), "utf8"),
).tokens as Record<string, { type: string; value?: unknown; [theme: string]: unknown }>;

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

describe("AGENT_STATE_FACTOR — process-state grammar (Chromatic v1.1.0)", () => {
  it("mirrors design-system factor.agentstate.* exactly (no drift)", () => {
    for (const [state, factor] of Object.entries(AGENT_STATE_FACTOR)) {
      const token = DIST_TOKENS[`factor.agentstate.${state}`];
      expect(token, `factor.agentstate.${state} exists in dist`).toBeDefined();
      expect(token?.value, `factor.agentstate.${state}`).toBe(factor);
    }
  });

  it("is strictly monotone with cognitive activity (INV-CLR-017)", () => {
    const seq: AgentProcessState[] = ["interrupted", "waiting", "thinking", "debating", "acting"];
    for (let i = 1; i < seq.length; i++) {
      const cur = seq[i];
      const prev = seq[i - 1];
      if (cur === undefined || prev === undefined) continue;
      expect(AGENT_STATE_FACTOR[cur]).toBeGreaterThan(AGENT_STATE_FACTOR[prev]);
    }
    expect(AGENT_STATE_FACTOR.acting).toBe(1);
    expect(AGENT_STATE_FACTOR.escalated).toBe(1);
  });
});

describe("processStateColor — identity rationed by state", () => {
  it("maps the factor directly to the identity share of the mix", () => {
    const v = "var(--syn-agent-demand-prophet)";
    expect(processStateColor(v, "interrupted")).toContain("25%");
    expect(processStateColor(v, "thinking")).toContain("55%");
    expect(processStateColor(v, "acting")).toContain("100%");
    expect(processStateColor(v, "interrupted")).toContain("color-mix(in oklab");
    expect(processStateColor(v, "interrupted")).toContain("var(--syn-neutral-mix)");
  });

  it("escalated keeps full identity chroma (urgency is the ring + pulse, not a drain)", () => {
    const v = "var(--syn-agent-disruption-shield)";
    expect(processStateColor(v, "escalated")).toBe(processStateColor(v, "acting"));
  });

  it("never emits a raw colour literal (INV-CLR-009)", () => {
    const s = processStateColor("var(--syn-agent-pricing-oracle)", "debating");
    expect(s).not.toMatch(/#[0-9a-f]{3,8}/i);
    expect(s).not.toMatch(/\b(rgba?|hsla?)\s*\(/);
  });
});

describe("honesty-state colours mirror the canonical tokens", () => {
  const parse = (s: string): { l: number; c: number; h: number } => {
    const m = /oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)/.exec(s);
    if (!m) throw new Error(`not oklch: ${s}`);
    return { l: Number(m[1]), c: Number(m[2]), h: Number(m[3]) };
  };

  it("returns token references only (INV-CLR-009)", () => {
    expect(degradedStateColor()).toBe("var(--syn-state-degraded)");
    expect(syntheticStateColor()).toBe("var(--syn-state-synthetic)");
  });

  it("tokens.css --syn-state-* values match design-system dist exactly", () => {
    const css = readFileSync(join(REPO_ROOT, "frontend", "src", "styles", "tokens.css"), "utf8");
    const varValues = (name: string): string[] =>
      [...css.matchAll(new RegExp(`${name}:\\s*(oklch\\([^)]+\\))`, "g"))].map((m) => m[1] ?? "");

    for (const [state, varName] of [
      ["degraded", "--syn-state-degraded"],
      ["synthetic", "--syn-state-synthetic"],
    ] as const) {
      const token = DIST_TOKENS[`color.state.${state}`] as unknown as {
        light: { oklch: { l: number; c: number; h: number } };
        dark: { oklch: { l: number; c: number; h: number } };
      };
      const values = varValues(varName).map(parse);
      expect(values.length, `${varName} declared for dark + light`).toBeGreaterThanOrEqual(2);
      // tokens.css declares dark first (:root) then the light override.
      const [dark, light] = values;
      for (const [mirror, canon] of [
        [dark, token.dark.oklch],
        [light, token.light.oklch],
      ] as const) {
        expect(mirror?.l).toBeCloseTo(canon.l, 4);
        expect(mirror?.c).toBeCloseTo(canon.c, 4);
        expect(mirror?.h).toBeCloseTo(canon.h, 2);
      }
    }
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
