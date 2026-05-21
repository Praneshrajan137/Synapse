/**
 * SYNAPSE Atlas Console — design-token AAA-contrast guard.
 *
 * Plan §12 / ADR-028: pricing-cap badges, freshness ≤ 6h pins, and
 * disruption tier-4 banner MUST clear WCAG AAA (7:1) on the surface
 * where they appear.
 *
 * The Storybook a11y test-runner enforces this on rendered stories
 * (the visual gate), but we duplicate the contract here as a unit
 * test so a token edit fails fast — without a Storybook + Playwright
 * boot — when the dev runs `pnpm test`. Two separate gates is
 * intentional: one blocks at design-token edit time, the other at
 * component render time.
 */
import { describe, expect, it } from "vitest";

/**
 * Compute relative luminance per WCAG 2.2 §1.4.3 / sRGB definition.
 * Inputs are integers 0-255 (the format we use in tokens.css).
 */
function luminance(r: number, g: number, b: number): number {
  const toLin = (c: number): number => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * toLin(r) + 0.7152 * toLin(g) + 0.0722 * toLin(b);
}

function contrastRatio(
  fg: readonly [number, number, number],
  bg: readonly [number, number, number],
): number {
  const lFg = luminance(fg[0], fg[1], fg[2]);
  const lBg = luminance(bg[0], bg[1], bg[2]);
  const [a, b] = lFg > lBg ? [lFg, lBg] : [lBg, lFg];
  return (a + 0.05) / (b + 0.05);
}

// Mirrors `tokens.css`. If you bump a token there, bump it here in
// the same PR — CODEOWNERS makes the audit explicit.
const LIGHT = {
  bg: [248, 250, 252] as const, // slate-50
  fg: [15, 23, 42] as const, // slate-900
  safetyCritical: [127, 29, 29] as const, // red-900
};
const DARK = {
  bg: [2, 6, 23] as const,
  fg: [248, 250, 252] as const,
  safetyCritical: [254, 202, 202] as const, // red-200
};

const AAA_NORMAL = 7;
const AA_NORMAL = 4.5;

describe("design tokens · WCAG contrast", () => {
  it("light theme: fg vs bg clears AAA", () => {
    expect(contrastRatio(LIGHT.fg, LIGHT.bg)).toBeGreaterThanOrEqual(AAA_NORMAL);
  });

  it("dark theme: fg vs bg clears AAA", () => {
    expect(contrastRatio(DARK.fg, DARK.bg)).toBeGreaterThanOrEqual(AAA_NORMAL);
  });

  it("light theme: safety-critical vs bg clears AAA (ADR-028)", () => {
    expect(contrastRatio(LIGHT.safetyCritical, LIGHT.bg)).toBeGreaterThanOrEqual(
      AAA_NORMAL,
    );
  });

  it("dark theme: safety-critical vs bg clears AAA (ADR-028)", () => {
    expect(contrastRatio(DARK.safetyCritical, DARK.bg)).toBeGreaterThanOrEqual(
      AAA_NORMAL,
    );
  });

  it("dark theme: safety-critical vs bg clears the AA bar even on a small surface", () => {
    expect(contrastRatio(DARK.safetyCritical, DARK.bg)).toBeGreaterThanOrEqual(
      AA_NORMAL,
    );
  });
});
