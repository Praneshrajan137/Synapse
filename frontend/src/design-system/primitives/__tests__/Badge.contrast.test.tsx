/**
 * Every Badge tone's text clears 4.5:1 on what it is painted on (finding 134).
 *
 * Each tone's tint is painted over each page surface, in every theme, and its text token is
 * judged against the result. While each tinted tone drew its own colour as text, 36 of these
 * 81 pairings sat at or below 4.5:1, among them TierBadge Tier 3 (4.08:1) and Tier 4 (2.60:1)
 * on the dark canvas. Wrong if a tone draws its own colour as text again.
 */

import { BADGE_TONE_CLASSES } from "@ds/primitives/Badge";
import {
  PAGE_SURFACES,
  TOKEN_THEMES,
  WCAG_AA_NORMAL_TEXT,
  contrast,
  luminance,
  over,
  tokenIn,
  tokenRgb,
} from "@test/token-contrast";
import { describe, expect, it } from "vitest";

const TIER_TONES = ["tier1", "tier2", "tier3", "tier4"] as const;

describe("Badge tones", () => {
  for (const [tone, classes] of Object.entries(BADGE_TONE_CLASSES)) {
    it(`the ${tone} tone's text clears 4.5:1 on its tint over every surface and theme`, () => {
      const tint = tokenIn(classes, "bg");
      const text = tokenIn(classes, "text");
      if (tint === undefined || text === undefined) throw new Error(`${tone}: ${classes}`);
      for (const theme of TOKEN_THEMES) {
        for (const surface of PAGE_SURFACES) {
          const painted = over(tokenRgb(theme, tint.name), tint.alpha, tokenRgb(theme, surface));
          const ratio = contrast(tokenRgb(theme, text.name), painted);
          expect(ratio, `${tone} on ${surface} (${theme})`).toBeGreaterThan(WCAG_AA_NORMAL_TEXT);
        }
      }
    });
  }

  it("the tier tints keep the tier's order in lightness, so the tier stays encoded", () => {
    for (const theme of TOKEN_THEMES) {
      for (const surface of PAGE_SURFACES) {
        const lightness = TIER_TONES.map((tone) => {
          const tint = tokenIn(BADGE_TONE_CLASSES[tone], "bg");
          if (tint === undefined) throw new Error(`${tone} names no tint`);
          return luminance(over(tokenRgb(theme, tint.name), tint.alpha, tokenRgb(theme, surface)));
        });
        expect(lightness, `${surface} (${theme})`).toEqual([...lightness].sort((a, b) => b - a));
        expect(new Set(lightness).size).toBe(TIER_TONES.length);
      }
    }
  });
});
