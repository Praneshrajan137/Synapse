// ============================================================================
// SYNAPSE Chromatic System — contrast (domain service: ContrastEvaluator)
//
// Two contrast models, validated together (INV-CLR-002 / INV-CLR-003):
//   - WCAG 2.1 contrast ratio  — the legal conformance baseline.
//   - APCA (Lc)                — the perceptual frontier (WCAG 3 draft).
//
// APCA is implemented in-repo from the published APCA-W3 0.1.9 G-series
// constants, so the system depends on no APCA package and stays within the
// I-1 license allow-list. Oracle test cross-checks against known reference
// values (#000-on-#fff -> Lc ~106, #fff-on-#000 -> Lc ~-108).
// ============================================================================
import { wcagContrast, converter } from "culori";

const toRgb = converter("rgb");

/** WCAG 2.1 contrast ratio in [1, 21]. */
export function wcag(a, b) {
  return wcagContrast(a, b);
}

// --- APCA-W3 0.1.9 (G-series / "4g") constants -----------------------------
const APCA = {
  mainTRC: 2.4,
  sRco: 0.2126729,
  sGco: 0.7151522,
  sBco: 0.072175,
  normBG: 0.56,
  normTXT: 0.57,
  revTXT: 0.62,
  revBG: 0.65,
  blkThrs: 0.022,
  blkClmp: 1.414,
  scaleBoW: 1.14,
  scaleWoB: 1.14,
  loBoWoffset: 0.027,
  loWoBoffset: 0.027,
  deltaYmin: 0.0005,
  loClip: 0.1,
};

const clamp01 = (v) => Math.max(0, Math.min(1, v));

/** Screen luminance (Y_s) of a color, with APCA black soft-clamp applied. */
export function apcaLuminance(color) {
  const c = toRgb(color);
  const r = clamp01(c.r) ** APCA.mainTRC;
  const g = clamp01(c.g) ** APCA.mainTRC;
  const b = clamp01(c.b) ** APCA.mainTRC;
  let y = APCA.sRco * r + APCA.sGco * g + APCA.sBco * b;
  if (y < APCA.blkThrs) y += (APCA.blkThrs - y) ** APCA.blkClmp;
  return y;
}

/**
 * APCA lightness contrast (Lc) of `text` against `background`.
 * Sign encodes polarity: positive = dark text on light bg, negative = light
 * text on dark bg. Magnitude is the readable contrast.
 */
export function apca(text, background) {
  const txtY = apcaLuminance(text);
  const bgY = apcaLuminance(background);
  if (Math.abs(bgY - txtY) < APCA.deltaYmin) return 0;

  let sapc;
  let output;
  if (bgY > txtY) {
    sapc = (bgY ** APCA.normBG - txtY ** APCA.normTXT) * APCA.scaleBoW;
    output = sapc < APCA.loClip ? 0 : sapc - APCA.loBoWoffset;
  } else {
    sapc = (bgY ** APCA.revBG - txtY ** APCA.revTXT) * APCA.scaleWoB;
    output = sapc > -APCA.loClip ? 0 : sapc + APCA.loWoBoffset;
  }
  return output * 100;
}

/** Convenience: absolute APCA Lc, polarity discarded. */
export function apcaLc(text, background) {
  return Math.abs(apca(text, background));
}
