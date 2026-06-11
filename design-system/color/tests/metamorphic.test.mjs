// ============================================================================
// Testing layer 4 — Metamorphic. Theme inversion and CVD simulation are
// metamorphic transforms: a property must survive the transform.
// ============================================================================
import { describe, it, expect } from "vitest";
import { AGENTS, THRESHOLDS, TOKENS, color, CONTRAST_PAIRS } from "./_load.mjs";
import { wcag } from "../build/contrast.mjs";
import { deltaEOK, simulateCvd, CVD_TYPES } from "../build/cvd.mjs";
import { confidenceColor } from "../dist/tokens.ts";

describe("MR-CLR-001 — theme inversion preserves legibility", () => {
  it("MR-CLR-001 every contrast pair that passes in dark also passes in light", () => {
    for (const { surface, text } of CONTRAST_PAIRS) {
      const darkRatio = wcag(color(text, "dark"), color(surface, "dark"));
      const lightRatio = wcag(color(text, "light"), color(surface, "light"));
      expect(darkRatio, `${text}/${surface} dark`).toBeGreaterThanOrEqual(THRESHOLDS.wcag_text_normal);
      expect(lightRatio, `${text}/${surface} light`).toBeGreaterThanOrEqual(THRESHOLDS.wcag_text_normal);
    }
  });
});

describe("MR-CLR-002 — CVD simulation preserves agent distinctness", () => {
  it("MR-CLR-002 agent distinctness survives the deutan/protan/tritan transform", () => {
    for (const theme of ["light", "dark"]) {
      const cols = AGENTS.map((a) => color(`color.agent.${a}`, theme));
      for (const cvd of CVD_TYPES) {
        const sim = cols.map((c) => simulateCvd(c, cvd));
        let min = Infinity;
        for (let i = 0; i < sim.length; i++) {
          for (let j = i + 1; j < sim.length; j++) {
            min = Math.min(min, deltaEOK(sim[i], sim[j]));
          }
        }
        expect(min, `${theme}/${cvd}`).toBeGreaterThanOrEqual(THRESHOLDS.agent_pair_min_deltaeok_cvd);
      }
    }
  });
});

describe("MR-CLR-003 — rising confidence advances the red->teal axis", () => {
  it("MR-CLR-003 increasing confidence never decreases the mapped hue", () => {
    for (const theme of ["light", "dark"]) {
      let prevH = -Infinity;
      for (let v = 0; v <= 1.0001; v += 0.01) {
        const m = confidenceColor(Math.min(v, 1), theme).match(/oklch\([\d.]+ [\d.]+ ([\d.]+)\)/);
        const h = +m[1];
        expect(h, `hue at v=${v} (${theme})`).toBeGreaterThanOrEqual(prevH - 1e-6);
        prevH = h;
      }
    }
  });
});

describe("MR-CLR-004 — degradation (chroma rationing) preserves identity", () => {
  // The process-state grammar (ADR-044): state = chroma factor over the
  // FROZEN identity hue. The transform must never read as a different agent.
  const ration = (c, f) => ({ mode: "oklch", l: c.l, c: c.c * f, h: c.h });

  it("MR-CLR-004 every factor < 1 strictly reduces chroma and leaves L and H untouched", () => {
    const factors = ["interrupted", "waiting", "thinking", "debating"].map(
      (n) => TOKENS[`factor.agentstate.${n}`].value,
    );
    for (const theme of ["light", "dark"]) {
      for (const agent of AGENTS) {
        const identity = color(`color.agent.${agent}`, theme);
        for (const f of factors) {
          const rationed = ration(identity, f);
          expect(rationed.c, `${agent} ${theme} f=${f} chroma`).toBeLessThan(identity.c);
          expect(rationed.l, `${agent} ${theme} f=${f} lightness`).toBe(identity.l);
          expect(
            Math.abs(rationed.h - identity.h),
            `${agent} ${theme} f=${f} hue drift`,
          ).toBeLessThan(2);
        }
      }
    }
  });

  it("MR-CLR-004 rationing never collapses two agents into the same colour", () => {
    // Even at the deepest drain (interrupted), the 8 identities must remain
    // pairwise separable under normal vision — the CVD-grade threshold is the
    // floor because drained chroma approaches the CVD-compressed regime.
    const f = TOKENS["factor.agentstate.interrupted"].value;
    for (const theme of ["light", "dark"]) {
      const drained = AGENTS.map((a) => ration(color(`color.agent.${a}`, theme), f));
      for (let i = 0; i < drained.length; i++) {
        for (let j = i + 1; j < drained.length; j++) {
          expect(
            deltaEOK(drained[i], drained[j]),
            `${AGENTS[i]}/${AGENTS[j]} ${theme} drained`,
          ).toBeGreaterThanOrEqual(THRESHOLDS.agent_pair_min_deltaeok_cvd);
        }
      }
    }
  });
});
