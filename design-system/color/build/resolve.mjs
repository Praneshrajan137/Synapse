// ============================================================================
// SYNAPSE Chromatic System — token resolution (domain service: TokenResolver)
//
// Loads DTCG token files, flattens the tree, resolves {references}, and
// gamut-maps every color into sRGB. Pure + deterministic: same input JSON
// always produces the same output (INV-CLR-010).
// ============================================================================
import { readFileSync } from "node:fs";
import { oklch, clampChroma, formatHex, inGamut, converter } from "culori";

const toRgb = converter("rgb");
const isInGamut = inGamut("rgb");

/** Round deterministically — fixed precision, trailing zeros dropped. */
export function num(x, digits = 4) {
  return Number(x.toFixed(digits));
}

/** Parse an OKLCH literal string into a culori color object. */
export function parseOklch(str) {
  const c = oklch(str);
  if (!c) throw new Error(`DbC: parseOklch could not parse "${str}"`);
  return { mode: "oklch", l: c.l, c: c.c, h: c.h ?? 0 };
}

/**
 * Map an OKLCH color into the sRGB gamut by reducing chroma at *exact*
 * constant L and H (CSS Color 4 chroma-reduction). Lightness and hue are
 * never altered — only saturation gives way. The result is quantized to the
 * emit precision and re-verified, so the stored value is itself in-gamut
 * (rounding never re-inflates chroma past the boundary).
 * Postcondition: isInGamut('rgb', toRgb(result)). (DbC — testing layer 5)
 */
export function gamutMap(o) {
  const l = num(o.l, 4);
  const h = num(o.h ?? 0, 2);
  const clamped = clampChroma({ mode: "oklch", l, c: o.c, h }, "oklch", "rgb");
  // Round chroma DOWN to emit precision so quantization can only shrink it.
  let c = Math.floor((clamped.c ?? 0) * 1e4) / 1e4;
  let result = { mode: "oklch", l, c, h };
  let guard = 0;
  while (!isInGamut(toRgb(result)) && c > 0 && guard < 400) {
    c = Math.max(0, num(c - 0.0001, 4));
    result = { mode: "oklch", l, c, h };
    guard += 1;
  }
  return result;
}

/** Format an OKLCH object as a CSS oklch() string, deterministically. */
export function oklchToCss(o) {
  return `oklch(${num(o.l, 4)} ${num(o.c, 4)} ${num(o.h, 2)})`;
}

/** Convert an OKLCH object to a #rrggbb hex fallback (sRGB). */
export function oklchToHex(o) {
  return formatHex(o);
}

/** Convert an OKLCH object to an [r,g,b] 0-255 integer array (deck.gl/three). */
export function oklchToRgb255(o) {
  const c = toRgb(o);
  const clamp = (v) => Math.max(0, Math.min(255, Math.round(v * 255)));
  return [clamp(c.r), clamp(c.g), clamp(c.b)];
}

export { isInGamut, toRgb };

/** Recursively flatten a DTCG token tree to a Map of dotted-path -> token. */
export function flatten(tree, prefix = "", inheritedType = null, out = new Map()) {
  for (const [key, node] of Object.entries(tree)) {
    if (key.startsWith("$")) continue;
    const path = prefix ? `${prefix}.${key}` : key;
    const type = node.$type ?? inheritedType;
    if (Object.prototype.hasOwnProperty.call(node, "$value")) {
      out.set(path, { type, value: node.$value, description: node.$description });
    } else {
      flatten(node, path, type, out);
    }
  }
  return out;
}

/** Load one or more DTCG JSON files and flatten them into a single Map. */
export function loadTokens(files) {
  const merged = new Map();
  for (const file of files) {
    const tree = JSON.parse(readFileSync(file, "utf8"));
    for (const [path, token] of flatten(tree)) {
      if (merged.has(path)) {
        throw new Error(`DbC: duplicate token "${path}" while loading ${file}`);
      }
      merged.set(path, token);
    }
  }
  return merged;
}

const REF = /^\{([^}]+)\}$/;

/** Resolve one raw value (literal | reference) for a given theme. */
function resolveValue(raw, theme, flat, seen) {
  let value = raw;
  if (value && typeof value === "object") {
    if (!(theme in value)) {
      throw new Error(`DbC: themed value missing "${theme}" branch`);
    }
    value = value[theme];
  }
  if (typeof value === "string") {
    const m = value.match(REF);
    if (m) {
      const refPath = m[1];
      if (seen.has(refPath)) {
        throw new Error(`DbC: circular reference at "${refPath}"`);
      }
      const target = flat.get(refPath);
      if (!target) {
        throw new Error(`PRE-CLR-002: dangling reference "{${refPath}}"`);
      }
      return resolveValue(target.value, theme, flat, new Set([...seen, refPath]));
    }
  }
  return value;
}

/**
 * Resolve the whole token graph for both themes. Returns
 * { light: Map<path, resolved>, dark: Map<path, resolved> } where a resolved
 * color carries { type:'color', oklch, css, hex, rgb255 } and other token
 * types carry { type, value }.
 */
export function resolveAll(flat) {
  const out = { light: new Map(), dark: new Map() };
  for (const theme of ["light", "dark"]) {
    for (const [path, token] of flat) {
      const value = resolveValue(token.value, theme, flat, new Set());
      if (token.type === "color") {
        const mapped = gamutMap(parseOklch(value));
        out[theme].set(path, {
          type: "color",
          oklch: { l: num(mapped.l, 4), c: num(mapped.c, 4), h: num(mapped.h, 2) },
          css: oklchToCss(mapped),
          hex: oklchToHex(mapped),
          rgb255: oklchToRgb255(mapped),
        });
      } else {
        out[theme].set(path, { type: token.type, value });
      }
    }
  }
  return out;
}
