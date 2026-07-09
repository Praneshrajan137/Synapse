// ============================================================================
// Testing layer 1 — SDD. One test per INV-CLR invariant in color-system.spec.yml.
// scripts/check-spec-coverage.mjs blocks any invariant without a test here.
// ============================================================================
import { describe, it, expect } from "vitest";
import fc from "fast-check";
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
import { confidenceColor, confidenceZone, agentVar, AGENTS as TS_AGENTS } from "../dist/tokens.ts";

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
    expect(findHexLiterals("background: rgba(1,2,3,0.4)")).toHaveLength(1);
    expect(findHexLiterals("background: hsl(120 50% 50%)")).toHaveLength(1);
    expect(findHexLiterals("color: #abc;")).toHaveLength(1);
    expect(findHexLiterals('color: "var(--color-text-primary)"')).toHaveLength(0);
    expect(findHexLiterals('color: "rgb(var(--syn-border))"')).toHaveLength(0);
    expect(findHexLiterals('color: "rgba(var(--syn-border) / 0.4)"')).toHaveLength(0);
    expect(findHexLiterals('color: "hsl(var(--color-accent))"')).toHaveLength(0);
    expect(findHexLiterals('color: "hsla(var(--color-accent) / 0.5)"')).toHaveLength(0);
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

// ============================================================================
// atlas-console-elevation — Property 20 (Req 5.2, 5.3).
// Feature: atlas-console-elevation, Property 20: Every semantic token resolves
// in every theme.
//
// Theme_Mode is one of {light, dark, hc}. Unlike the OKLCH dist model (which
// carries only light/dark), the three rendered Theme_Modes are concretely
// defined as CSS custom properties in frontend/src/styles/tokens.css:
//   :root, [data-theme="dark"]  -> base/dark defaults
//   [data-theme="light"]        -> light overrides (fall back to base)
//   [data-theme="hc"]           -> high-contrast overrides (fall back to base)
// hc only overrides a subset; every other token inherits the :root value via
// the cascade. This block models that cascade and asserts every semantic
// colour token resolves to a concrete, non-empty value in each Theme_Mode.
// ============================================================================
const THEME_MODES = ["light", "dark", "hc"];

const TOKENS_CSS = (() => {
  const cssPath = join(ROOT, "..", "..", "frontend", "src", "styles", "tokens.css");
  let css = readFileSync(cssPath, "utf8").replace(/\/\*[\s\S]*?\*\//g, ""); // strip comments
  const mediaIdx = css.indexOf("@media"); // drop @media blocks (motion-only overrides)
  return mediaIdx === -1 ? css : css.slice(0, mediaIdx);
})();

const parseDecls = (body) => {
  const out = {};
  if (!body) return out;
  for (const chunk of body.split(";")) {
    const m = chunk.match(/^\s*(--[\w-]+)\s*:\s*([\s\S]+?)\s*$/);
    if (m) out[m[1]] = m[2].replace(/\s+/g, " ").trim();
  }
  return out;
};
const blockBody = (re) => (TOKENS_CSS.match(re) || [])[1] || null;

const CSS_BASE = parseDecls(blockBody(/:root,\s*\[data-theme="dark"\]\s*\{([^}]*)\}/));
const CSS_LIGHT = parseDecls(blockBody(/\[data-theme="light"\]\s*\{([^}]*)\}/));
const CSS_HC = parseDecls(blockBody(/\[data-theme="hc"\]\s*\{([^}]*)\}/));

// Resolved cascade per Theme_Mode: overrides layered over the :root/dark base.
const THEME_TABLE = {
  dark: { ...CSS_BASE },
  light: { ...CSS_BASE, ...CSS_LIGHT },
  hc: { ...CSS_BASE, ...CSS_HC },
};
const resolveThemeToken = (token, theme) => THEME_TABLE[theme][token];

// Semantic COLOUR roles only — exclude geometry/motion/shadow families.
const NON_COLOR = /^--syn-(motion|ease|radius|elev|surface-highlight|card-edge|focus-ring)/;
const isColorToken = (name) =>
  (name.startsWith("--syn-") || name.startsWith("--gradient-")) && !NON_COLOR.test(name);
const SEMANTIC_TOKENS = Object.keys(CSS_BASE).filter(isColorToken).sort();
const ALL_TOKEN_THEME_PAIRS = SEMANTIC_TOKENS.flatMap((t) => THEME_MODES.map((m) => [t, m]));

describe("INV-CLR-019 — every semantic token resolves in every theme (light/dark/hc)", () => {
  it("INV-CLR-019 the token model is non-empty and the base cascade parsed", () => {
    // Guard: a parse regression must not silently pass the property below.
    expect(SEMANTIC_TOKENS.length, "semantic colour tokens parsed from tokens.css").toBeGreaterThan(0);
    expect(Object.keys(CSS_HC).length, "[data-theme=hc] override block parsed").toBeGreaterThan(0);
    expect(Object.keys(CSS_LIGHT).length, "[data-theme=light] override block parsed").toBeGreaterThan(0);
  });

  it("INV-CLR-019 every semantic colour token resolves to a concrete value in light, dark, and hc", () => {
    fc.assert(
      fc.property(fc.constantFrom(...SEMANTIC_TOKENS), fc.constantFrom(...THEME_MODES), (token, theme) => {
        const value = resolveThemeToken(token, theme);
        // A miss surfaces the token + Theme_Mode by name — never a raw literal.
        expect(value, `Unresolved semantic token "${token}" in Theme_Mode "${theme}"`).toBeDefined();
        expect(typeof value, `"${token}" in "${theme}" must be a string value`).toBe("string");
        const v = String(value).trim();
        expect(v.length, `"${token}" in "${theme}" resolves to a non-empty value`).toBeGreaterThan(0);
        expect(
          /^(initial|inherit|unset)$/i.test(v),
          `"${token}" in "${theme}" must be concrete, not initial/inherit/unset`,
        ).toBe(false);
      }),
      // Every (token, theme) pair runs as an explicit example (exhaustive
      // coverage of "every token in every theme"), plus >=100 random runs.
      { numRuns: Math.max(100, SEMANTIC_TOKENS.length * THEME_MODES.length), examples: ALL_TOKEN_THEME_PAIRS },
    );
  });
});

// ============================================================================
// atlas-console-elevation — Properties 21..26. Universally-quantified
// (fast-check, >=100 runs) restatements of the deterministic INV-CLR laws the
// suite already checks by example, registered as fresh INV-CLR ids.
// ============================================================================

describe("INV-CLR-020 — tier lightness + confidence hue are monotonic", () => {
  // Feature: atlas-console-elevation, Property 21: Tier lightness and confidence
  // hue are monotonic (L(tier1)>L(tier2)>L(tier3)>L(tier4); increasing
  // confidence -> non-decreasing OKLCH hue). Validates Req 5.4.
  it("INV-CLR-020 tier lightness strictly decreases 1->4 in every theme", () => {
    fc.assert(
      fc.property(fc.constantFrom(...THEMES), fc.integer({ min: 0, max: 2 }), (theme, i) => {
        const hi = color(`color.tier.${i + 1}`, theme).l;
        const lo = color(`color.tier.${i + 2}`, theme).l;
        expect(hi, `L(tier${i + 1}) > L(tier${i + 2}) (${theme})`).toBeGreaterThan(lo);
      }),
      { numRuns: 200 },
    );
  });

  it("INV-CLR-020 increasing confidence never decreases the OKLCH hue coordinate", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...THEMES),
        fc.double({ min: 0, max: 1, noNaN: true }),
        fc.double({ min: 0, max: 1, noNaN: true }),
        (theme, a, b) => {
          const lo = Math.min(a, b);
          const hi = Math.max(a, b);
          const hLo = parseOklchStr(confidenceColor(lo, theme)).h;
          const hHi = parseOklchStr(confidenceColor(hi, theme)).h;
          expect(hHi - hLo, `hue(${hi}) >= hue(${lo}) (${theme})`).toBeGreaterThanOrEqual(-1e-6);
        },
      ),
      { numRuns: 300 },
    );
  });
});

describe("INV-CLR-021 — WCAG 2.1 AA contrast holds for every pair in every theme", () => {
  // Feature: atlas-console-elevation, Property 22: WCAG AA contrast holds for
  // every text/component-on-surface pair in every theme (>=4.5 body, >=3.0
  // large/UI). Validates Req 5.6.
  const PAIR_THEME = CONTRAST_PAIRS.flatMap((p) => THEMES.map((t) => [p, t]));
  it("INV-CLR-021 every text-on-surface pair clears WCAG AA body contrast in each theme", () => {
    fc.assert(
      fc.property(fc.constantFrom(...CONTRAST_PAIRS), fc.constantFrom(...THEMES), ({ surface, text }, theme) => {
        const ratio = wcag(color(text, theme), color(surface, theme));
        expect(ratio, `${text} on ${surface} (${theme})`).toBeGreaterThanOrEqual(
          THRESHOLDS.wcag_text_normal,
        );
        // Body threshold subsumes large-text/UI (3.0); assert the floor too.
        expect(ratio, `${text} on ${surface} (${theme}) >= UI floor`).toBeGreaterThanOrEqual(
          THRESHOLDS.wcag_ui_component,
        );
      }),
      { numRuns: Math.max(100, PAIR_THEME.length), examples: PAIR_THEME },
    );
  });
});

describe("INV-CLR-022 — APCA Lc target per emphasis tier, every pair, every theme", () => {
  // Feature: atlas-console-elevation, Property 23: APCA Lc target per emphasis
  // tier (primary >=75, secondary >=60, tertiary >=45) every text pair every
  // theme. Validates Req 5.7.
  const TARGET = {
    primary: THRESHOLDS.apca_primary_lc,
    secondary: THRESHOLDS.apca_secondary_lc,
    tertiary: THRESHOLDS.apca_tertiary_lc,
  };
  const PAIR_THEME = CONTRAST_PAIRS.flatMap((p) => THEMES.map((t) => [p, t]));
  it("INV-CLR-022 every text-on-surface pair clears its APCA Lc tier in each theme", () => {
    fc.assert(
      fc.property(fc.constantFrom(...CONTRAST_PAIRS), fc.constantFrom(...THEMES), ({ surface, text, tier }, theme) => {
        const lc = Math.abs(apca(color(text, theme), color(surface, theme)));
        expect(lc, `${text} on ${surface} (${theme}, ${tier})`).toBeGreaterThanOrEqual(TARGET[tier]);
      }),
      { numRuns: Math.max(100, PAIR_THEME.length), examples: PAIR_THEME },
    );
  });
});

describe("INV-CLR-023 — agent pairs stay ΔE-OK-separated under CVD, every theme", () => {
  // Feature: atlas-console-elevation, Property 24: All 28 agent-color pairs
  // differ by >= min ΔE-OK under deuteranopia/protanopia/tritanopia in each
  // theme. Validates Req 5.8.
  const AGENT_PAIRS = [];
  for (let i = 0; i < AGENTS.length; i++) {
    for (let j = i + 1; j < AGENTS.length; j++) AGENT_PAIRS.push([i, j]);
  }
  const ALL = AGENT_PAIRS.flatMap((pair) => THEMES.flatMap((t) => CVD_TYPES.map((c) => [pair, t, c])));
  it("INV-CLR-023 all 28 agent pairs differ by >= min ΔE-OK under each CVD, both themes", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...AGENT_PAIRS),
        fc.constantFrom(...THEMES),
        fc.constantFrom(...CVD_TYPES),
        ([i, j], theme, cvd) => {
          const a = simulateCvd(color(`color.agent.${AGENTS[i]}`, theme), cvd);
          const b = simulateCvd(color(`color.agent.${AGENTS[j]}`, theme), cvd);
          expect(
            deltaEOK(a, b),
            `${AGENTS[i]}/${AGENTS[j]} (${theme}, ${cvd})`,
          ).toBeGreaterThanOrEqual(THRESHOLDS.agent_pair_min_deltaeok_cvd);
        },
      ),
      { numRuns: Math.max(100, ALL.length), examples: ALL },
    );
  });
});

describe("INV-CLR-024 — degraded chroma sits below every full-saturation state", () => {
  // Feature: atlas-console-elevation, Property 25: Degraded chroma <=
  // degraded_max_chroma AND >= degraded_min_chroma_gap below the min chroma of
  // every full-saturation state. Validates Req 5.9.
  const FULL_STATES = ["success", "warning", "danger", "info"];
  it("INV-CLR-024 degraded chroma is drained below the ceiling and every full state, both themes", () => {
    fc.assert(
      fc.property(fc.constantFrom(...THEMES), fc.constantFrom(...FULL_STATES), (theme, state) => {
        const degraded = color("color.state.degraded", theme).c;
        expect(degraded, `degraded chroma ceiling (${theme})`).toBeLessThanOrEqual(
          THRESHOLDS.degraded_max_chroma,
        );
        const full = color(`color.state.${state}`, theme).c;
        expect(degraded, `degraded gap below ${state} (${theme})`).toBeLessThanOrEqual(
          full - THRESHOLDS.degraded_min_chroma_gap,
        );
      }),
      { numRuns: Math.max(100, THEMES.length * FULL_STATES.length), examples: THEMES.flatMap((t) => FULL_STATES.map((s) => [t, s])) },
    );
  });
});

describe("INV-CLR-025 — colour is never the sole channel (non-colour signal always present)", () => {
  // Feature: atlas-console-elevation, Property 26: Color is never the sole
  // channel — every color-coded affordance also carries text/icon/shape.
  // Structural, consistent with INV-CLR-011. Validates Req 5.10.
  const ZONES = new Set(["low", "escalation", "autonomous"]);
  it("INV-CLR-025 every confidence value carries a textual zone label, not just colour", () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 1, noNaN: true }), (v) => {
        const zone = confidenceZone(v);
        expect(ZONES.has(zone), `confidence ${v} -> non-colour zone label`).toBe(true);
      }),
      { numRuns: 200 },
    );
  });

  it("INV-CLR-025 every agent affordance carries a stable textual key + token reference", () => {
    fc.assert(
      fc.property(fc.constantFrom(...TS_AGENTS), (agent) => {
        // The agent key itself is a non-colour (text) signal; agentVar routes
        // colour through a token, never a raw literal.
        expect(typeof agent, `agent key is text`).toBe("string");
        expect(agent.length, `agent key non-empty`).toBeGreaterThan(0);
        expect(agentVar(agent), `agentVar(${agent})`).toMatch(/^var\(--color-agent-[a-z-]+\)$/);
      }),
      { numRuns: Math.max(100, TS_AGENTS.length), examples: TS_AGENTS.map((a) => [a]) },
    );
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
