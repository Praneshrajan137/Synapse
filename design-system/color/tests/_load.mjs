// Shared test fixtures — loads the built token model for the SYNAPSE
// Chromatic test suite. All 7 testing layers import from here.
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

export const dist = JSON.parse(readFileSync(join(ROOT, "dist", "tokens.json"), "utf8"));
export const TOKENS = dist.tokens;
export const THEMES = ["light", "dark"];

export const AGENTS = [
  "demand-prophet",
  "routing-navigator",
  "inventory-sentinel",
  "freshness-guardian",
  "pricing-oracle",
  "disruption-shield",
  "supplier-trust",
  "sustainability-agent",
];

/** A culori-shaped OKLCH color object for a token path + theme. */
export function color(path, theme) {
  const t = TOKENS[path];
  if (!t || t.type !== "color") throw new Error(`not a color token: ${path}`);
  return { mode: "oklch", ...t[theme].oklch };
}

export const colorPaths = () =>
  Object.keys(TOKENS).filter((p) => TOKENS[p].type === "color");

// --- spec.yml as the source of truth for thresholds + invariant IDs --------
const specText = readFileSync(join(ROOT, "color-system.spec.yml"), "utf8");

export const THRESHOLDS = (() => {
  const block = (specText.split(/^thresholds:[ \t]*$/m)[1] || "").split(/^\S/m)[0];
  const out = {};
  for (const line of block.split(/\r?\n/)) {
    const m = line.match(/^[ \t]+([a-z_]+):[ \t]*([0-9.]+)[ \t]*$/);
    if (m) out[m[1]] = Number(m[2]);
  }
  return out;
})();

export const INVARIANT_IDS = [...specText.matchAll(/id:[ \t]*"(INV-CLR-\d+)"/g)].map((m) => m[1]);
export const MR_IDS = [...specText.matchAll(/id:[ \t]*"(MR-CLR-\d+)"/g)].map((m) => m[1]);

/** Realistic text-on-surface pairs the UI actually renders. */
export const CONTRAST_PAIRS = (() => {
  const surfaces = ["canvas", "panel", "raised", "overlay"];
  const texts = ["primary", "secondary", "tertiary"];
  const out = [];
  for (const s of surfaces) {
    for (const t of texts) {
      out.push({ surface: `color.surface.${s}`, text: `color.text.${t}`, tier: t });
    }
  }
  // Button-label text — short, >=14px, medium weight — is the APCA secondary
  // tier (Lc 60), not body copy. See ADR-025.
  out.push({ surface: "color.brand.base", text: "color.brand.fg", tier: "secondary" });
  return out;
})();
