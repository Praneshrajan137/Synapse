// ============================================================================
// Testing layer 1 — SDD. One test per INV-CLR invariant in color-system.spec.yml.
// scripts/check-spec-coverage.mjs blocks any invariant without a test here.
// ============================================================================
import { describe, it, expect } from "vitest";
import {
  TOKENS,
  THEMES,
  AGENTS,
  THRESHOLDS,
  INVARIANT_IDS,
  color,
  colorPaths,
  CONTRAST_PAIRS,
} from "./_load.mjs";
import { build } from "../build/build.mjs";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "./_load.mjs";
import { wcag, apca } from "../build/contrast.mjs";
import { deltaEOK, hueDistance, simulateCvd, CVD_TYPES } from "../build/cvd.mjs";
import { isInGamut, toRgb } from "../build/resolve.mjs";
import { converter } from "culori";
import { findHexLiterals } from "../scripts/lint-hex.mjs";
import { confidenceColor, confidenceZone, AGENTS as TS_AGENTS } from "../dist/tokens.ts";

const HEX_RE = /^#[0-9a-f]{6}$/;
const parseOklchStr = (s) => {
  const m = s.match(/oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)/);
  return { mode: "oklch", l: +m[1], c: +m[2], h: +m[3] };
};

describe("INV-CLR-001 — theme completeness", () => {
  it("INV-CLR-001 every semantic colour token resolves in both light and dark", () => {
    for (const p of colorPaths()) {
      for (const theme of THEMES) {
        expect(TOKENS[p][theme], `${p}.${theme}`).toBeDefined();
        expect(TOKENS[p][theme].hex, `${p}.${theme}`).toMatch(HEX_RE);
      }
    }
  });
});

describe("INV-CLR-002 — WCAG 2.1 AA contrast", () => {
  it("INV-CLR-002 every text-on-surface pair clears WCAG AA in both themes", () => {
    for (const theme of THEMES) {
      for (const { surface, text } of CONTRAST_PAIRS) {
        const ratio = wcag(color(text, theme), color(surface, theme));
        expect(ratio, `${text} on ${surface} (${theme})`).toBeGreaterThanOrEqual(
          THRESHOLDS.wcag_text_normal,
        );
      }
    }
  });
});

describe("INV-CLR-003 — APCA contrast (tiered by emphasis)", () => {
  it("INV-CLR-003 every text-on-surface pair clears its APCA Lc tier", () => {
    const target = {
      primary: THRESHOLDS.apca_primary_lc,
      secondary: THRESHOLDS.apca_secondary_lc,
      tertiary: THRESHOLDS.apca_tertiary_lc,
    };
    for (const theme of THEMES) {
      for (const { surface, text, tier } of CONTRAST_PAIRS) {
        const lc = Math.abs(apca(color(text, theme), color(surface, theme)));
        expect(lc, `${text} on ${surface} (${theme})`).toBeGreaterThanOrEqual(target[tier]);
      }
    }
  });
});

describe("INV-CLR-004 — agent perceptual distinctness (normal vision)", () => {
  it("INV-CLR-004 all 28 agent pairs are hue- and deltaEOK-separated, both themes", () => {
    for (const theme of THEMES) {
      const cols = AGENTS.map((a) => color(`color.agent.${a}`, theme));
      for (let i = 0; i < AGENTS.length; i++) {
        for (let j = i + 1; j < AGENTS.length; j++) {
          const label = `${AGENTS[i]}/${AGENTS[j]} (${theme})`;
          expect(hueDistance(cols[i].h, cols[j].h), label).toBeGreaterThanOrEqual(
            THRESHOLDS.agent_pair_min_hue_deg,
          );
          expect(deltaEOK(cols[i], cols[j]), label).toBeGreaterThanOrEqual(
            THRESHOLDS.agent_pair_min_deltaeok,
          );
        }
      }
    }
  });
});

describe("INV-CLR-005 — agent distinctness under colour-vision deficiency", () => {
  it("INV-CLR-005 agent pairs stay separated under deutan/protan/tritan simulation", () => {
    for (const theme of THEMES) {
      const cols = AGENTS.map((a) => color(`color.agent.${a}`, theme));
      for (const cvd of CVD_TYPES) {
        const sim = cols.map((c) => simulateCvd(c, cvd));
        for (let i = 0; i < sim.length; i++) {
          for (let j = i + 1; j < sim.length; j++) {
            expect(
              deltaEOK(sim[i], sim[j]),
              `${AGENTS[i]}/${AGENTS[j]} (${theme}, ${cvd})`,
            ).toBeGreaterThanOrEqual(THRESHOLDS.agent_pair_min_deltaeok_cvd);
          }
        }
      }
    }
  });
});

describe("INV-CLR-006 — decision-tier lightness monotonicity", () => {
  it("INV-CLR-006 tier lightness is strictly decreasing 1->4 (encodes I-8 order)", () => {
    for (const theme of THEMES) {
      const l = [1, 2, 3, 4].map((n) => color(`color.tier.${n}`, theme).l);
      for (let i = 0; i < 3; i++) {
        expect(l[i], `tier ${i + 1} vs ${i + 2} (${theme})`).toBeGreaterThan(l[i + 1]);
      }
    }
  });
});

describe("INV-CLR-007 — confidence scale continuity + gate anchoring", () => {
  it("INV-CLR-007 confidence hue rises monotonically and the map is continuous", () => {
    for (const theme of THEMES) {
      const stops = ["low", "escalation", "autonomous", "peak"].map(
        (k) => color(`color.confidence.${k}`, theme).h,
      );
      for (let i = 0; i < 3; i++) {
        expect(stops[i + 1], `confidence stop ${i} (${theme})`).toBeGreaterThan(stops[i]);
      }
      // Continuity: fine sampling has only small, bounded, monotone steps
      // (a discontinuity would show as a large jump between non-adjacent stops).
      let prev = parseOklchStr(confidenceColor(0, theme));
      for (let v = 0.005; v <= 1.0001; v += 0.005) {
        const cur = parseOklchStr(confidenceColor(Math.min(v, 1), theme));
        expect(Math.abs(cur.l - prev.l), `L jump at ${v} (${theme})`).toBeLessThan(0.03);
        expect(cur.h - prev.h, `H non-decreasing at ${v} (${theme})`).toBeGreaterThanOrEqual(-1e-6);
        expect(cur.h - prev.h, `H jump at ${v} (${theme})`).toBeLessThan(6);
        prev = cur;
      }
    }
  });
});

describe("INV-CLR-008 — sRGB gamut", () => {
  it("INV-CLR-008 every emitted colour is within sRGB gamut", () => {
    for (const p of colorPaths()) {
      for (const theme of THEMES) {
        expect(isInGamut(toRgb(color(p, theme))), `${p}.${theme}`).toBe(true);
        expect(TOKENS[p][theme].hex).toMatch(HEX_RE);
      }
    }
  });
});

describe("INV-CLR-009 — no raw colour literals", () => {
  it("INV-CLR-009 the hex detector flags raw literals and passes token usage", () => {
    expect(findHexLiterals('const a = "#ff0000";')).toHaveLength(1);
    expect(findHexLiterals("background: rgb(1,2,3)")).toHaveLength(1);
    expect(findHexLiterals("color: #abc;")).toHaveLength(1);
    expect(findHexLiterals('color: "var(--color-text-primary)"')).toHaveLength(0);
    expect(findHexLiterals("// brand #ff0000 chromatic-allow")).toHaveLength(0);
  });
});

describe("INV-CLR-010 — build determinism", () => {
  it("INV-CLR-010 rebuilding yields byte-identical artifacts", () => {
    const names = ["tokens.css", "tokens.ts", "tailwind-preset.cjs", "tokens.json"];
    const before = names.map((n) => readFileSync(join(ROOT, "dist", n), "utf8"));
    build();
    const after = names.map((n) => readFileSync(join(ROOT, "dist", n), "utf8"));
    names.forEach((n, i) => expect(after[i], n).toBe(before[i]));
  });
});

describe("INV-CLR-011 — colour is never the sole channel", () => {
  it("INV-CLR-011 non-colour signal helpers exist (zone label, agent keys)", () => {
    expect(confidenceZone(0.5)).toBe("low");
    expect(confidenceZone(0.75)).toBe("escalation");
    expect(confidenceZone(0.9)).toBe("autonomous");
    expect(TS_AGENTS).toHaveLength(8);
  });
});

describe("INV-CLR-012 — agent registry is frozen", () => {
  it("INV-CLR-012 exactly the 8 SYNAPSE agents have identity colours", () => {
    const keys = Object.keys(TOKENS)
      .filter((p) => p.startsWith("color.agent."))
      .map((p) => p.replace("color.agent.", ""))
      .sort();
    expect(keys).toEqual([...AGENTS].sort());
  });
});

describe("INV-CLR-013 — preference + forced-colors fallbacks", () => {
  it("INV-CLR-013 tokens.css defines reduced-motion, contrast, forced-colors blocks", () => {
    const css = readFileSync(join(ROOT, "dist", "tokens.css"), "utf8");
    expect(css).toContain("prefers-reduced-motion: reduce");
    expect(css).toContain("prefers-contrast: more");
    expect(css).toContain("forced-colors: active");
  });
});

describe("INV-CLR-014 — semantic state palette distinctness", () => {
  it("INV-CLR-014 the 5 state colours are mutually distinct, normal + CVD", () => {
    const states = ["success", "warning", "danger", "info", "neutral"];
    for (const theme of THEMES) {
      const cols = states.map((s) => color(`color.state.${s}`, theme));
      for (let i = 0; i < states.length; i++) {
        for (let j = i + 1; j < states.length; j++) {
          expect(deltaEOK(cols[i], cols[j]), `${states[i]}/${states[j]} ${theme}`).toBeGreaterThanOrEqual(
            THRESHOLDS.semantic_min_deltaeok,
          );
          for (const cvd of CVD_TYPES) {
            expect(
              deltaEOK(simulateCvd(cols[i], cvd), simulateCvd(cols[j], cvd)),
              `${states[i]}/${states[j]} ${theme} ${cvd}`,
            ).toBeGreaterThanOrEqual(THRESHOLDS.semantic_min_deltaeok_cvd);
          }
        }
      }
    }
  });
});

// ============================================================================
// v1.1.0 (ADR-044) — honesty states, process-state grammar, interaction recipes
// ============================================================================

describe("INV-CLR-015 — 7-state distinctness (5 + degraded + synthetic)", () => {
  it("INV-CLR-015 all 7 semantic states are mutually distinct, normal + CVD", () => {
    const states = ["success", "warning", "danger", "info", "neutral", "degraded", "synthetic"];
    for (const theme of THEMES) {
      const cols = states.map((s) => color(`color.state.${s}`, theme));
      for (let i = 0; i < states.length; i++) {
        for (let j = i + 1; j < states.length; j++) {
          expect(
            deltaEOK(cols[i], cols[j]),
            `${states[i]}/${states[j]} ${theme}`,
          ).toBeGreaterThanOrEqual(THRESHOLDS.semantic_min_deltaeok);
          for (const cvd of CVD_TYPES) {
            expect(
              deltaEOK(simulateCvd(cols[i], cvd), simulateCvd(cols[j], cvd)),
              `${states[i]}/${states[j]} ${theme} ${cvd}`,
            ).toBeGreaterThanOrEqual(THRESHOLDS.semantic_min_deltaeok_cvd);
          }
        }
      }
    }
  });
});

describe("INV-CLR-016 — degraded is chroma-drained", () => {
  it("INV-CLR-016 degraded chroma sits at/below the drain ceiling in both themes", () => {
    for (const theme of THEMES) {
      const degraded = color("color.state.degraded", theme);
      expect(degraded.c, `degraded chroma ${theme}`).toBeLessThanOrEqual(
        THRESHOLDS.degraded_max_chroma,
      );
    }
  });

  it("INV-CLR-016 degraded is visibly less saturated than every full state", () => {
    const fullStates = ["success", "warning", "danger", "info"];
    for (const theme of THEMES) {
      const degraded = color("color.state.degraded", theme);
      const minFull = Math.min(...fullStates.map((s) => color(`color.state.${s}`, theme).c));
      expect(degraded.c, `drain gap ${theme}`).toBeLessThanOrEqual(
        minFull - THRESHOLDS.degraded_min_chroma_gap,
      );
    }
  });
});

describe("INV-CLR-017 — process-state factors strictly monotone with activity", () => {
  const factor = (name) => {
    const t = TOKENS[`factor.agentstate.${name}`];
    expect(t, `factor.agentstate.${name} emitted`).toBeDefined();
    return t.value;
  };

  it("INV-CLR-017 interrupted < waiting < thinking < debating < acting == 1.0", () => {
    const seq = ["interrupted", "waiting", "thinking", "debating", "acting"].map(factor);
    for (let i = 1; i < seq.length; i++) {
      expect(seq[i], `monotone at index ${i}`).toBeGreaterThan(seq[i - 1]);
    }
    expect(seq[seq.length - 1]).toBe(1);
  });

  it("INV-CLR-017 every factor is in (0, 1] — identity never fully vanishes", () => {
    for (const name of ["interrupted", "waiting", "thinking", "debating", "acting", "escalated"]) {
      const f = factor(name);
      expect(f, `${name} > 0`).toBeGreaterThan(0);
      expect(f, `${name} <= 1`).toBeLessThanOrEqual(1);
    }
  });

  it("INV-CLR-017 escalated holds full chroma (urgency composes with the danger ring, not a drain)", () => {
    expect(factor("escalated")).toBe(1);
  });
});

describe("INV-CLR-018 — interaction tints never sink text below contrast", () => {
  // The interaction recipes are color-mix() in component CSS; the spec pins
  // the mix constants so this test can verify the composite the user sees.
  // mix(in oklab, overlay a%, surface) == interpolate surface->overlay at a.
  const mixOklab = (surface, overlay, alpha) => {
    const lab = converter("oklab");
    const s = lab(surface);
    const o = lab(overlay);
    const lerp = (x, y) => x + (y - x) * alpha;
    return { mode: "oklab", l: lerp(s.l, o.l), a: lerp(s.a, o.a), b: lerp(s.b, o.b) };
  };

  it("INV-CLR-018 body text on hover-tinted surfaces clears WCAG AA + APCA primary", () => {
    for (const theme of THEMES) {
      const alpha = THRESHOLDS[`interaction_hover_alpha_${theme}`];
      const text = color("color.text.primary", theme);
      for (const s of ["canvas", "panel", "raised"]) {
        const hovered = mixOklab(color(`color.surface.${s}`, theme), text, alpha);
        expect(wcag(text, hovered), `hover ${s} ${theme} wcag`).toBeGreaterThanOrEqual(
          THRESHOLDS.wcag_text_normal,
        );
        expect(Math.abs(apca(text, hovered)), `hover ${s} ${theme} apca`).toBeGreaterThanOrEqual(
          THRESHOLDS.apca_primary_lc,
        );
      }
    }
  });

  it("INV-CLR-018 body text on selected (brand-tinted) surfaces clears WCAG AA + APCA primary", () => {
    for (const theme of THEMES) {
      const alpha = THRESHOLDS[`interaction_selected_alpha_${theme}`];
      const text = color("color.text.primary", theme);
      const brand = color("color.brand.base", theme);
      for (const s of ["canvas", "panel", "raised"]) {
        const selected = mixOklab(color(`color.surface.${s}`, theme), brand, alpha);
        expect(wcag(text, selected), `selected ${s} ${theme} wcag`).toBeGreaterThanOrEqual(
          THRESHOLDS.wcag_text_normal,
        );
        expect(Math.abs(apca(text, selected)), `selected ${s} ${theme} apca`).toBeGreaterThanOrEqual(
          THRESHOLDS.apca_primary_lc,
        );
      }
    }
  });
});

describe("SDD coverage self-check", () => {
  it("every INV-CLR id in the spec has a describe block in this file", () => {
    const self = readFileSync(new URL(import.meta.url), "utf8");
    for (const id of INVARIANT_IDS) {
      expect(self.includes(id), `${id} has a test`).toBe(true);
    }
  });
});
