// Deck.gl colour palette — the one place the map's WebGL layers get colour.
//
// deck.gl accessors must return numeric `[r,g,b,a]` tuples, so these cannot be
// CSS-token strings. They MIRROR the chromatic tokens (src/styles/tokens.css —
// --syn-ink-subtle, --syn-confidence-*, --syn-signal-*) and exist here so the
// map honours the same "quiet by default" rationing as the rest of SENSORIUM:
// at rest a dark store is a neutral slate; saturated signal colour appears ONLY
// when a store is congested, a route violates freshness, etc. (ISA-101 HP-HMI;
// PR-CLR-002 "every hue is earned").
//
// If/when the frontend consumes design-system/color/dist directly, swap these
// for `tierRgb()` / `confidenceColor()` rgb255 helpers — the call sites here are
// the only ones to change.

export type RGBA = [number, number, number, number];

/** Quiet base — a dark store / idle node at rest. Neutral slate, translucent. */
export const DECK_NEUTRAL: RGBA = [100, 116, 139, 150]; // ~ --syn-ink-subtle
/** Muted connector line at rest (routes with nothing wrong). */
export const DECK_MUTED_LINE: RGBA = [100, 116, 139, 120];

// Signal palette — reserved for abnormality. Mirrors --syn-confidence/-signal.
export const DECK_INFO: RGBA = [56, 189, 248, 170]; // sky-400
export const DECK_WARN: RGBA = [234, 179, 8, 220]; // amber  — saturation > 0.7
export const DECK_RISK: RGBA = [239, 68, 68, 230]; // red    — saturation > 0.9
export const DECK_RISK_SOFT: RGBA = [251, 113, 133, 210]; // rose — risk arc target

export const SATURATION_WARN = 0.7;
export const SATURATION_RISK = 0.9;

/**
 * Dark-store fill colour by congestion/saturation in [0,1]. Quiet by default:
 * a healthy store is neutral, NOT a cheerful green. Colour fires only when the
 * store needs attention.
 */
export function storeFillColor(saturation: number | undefined): RGBA {
  const sat = saturation ?? 0;
  if (sat > SATURATION_RISK) return DECK_RISK;
  if (sat > SATURATION_WARN) return DECK_WARN;
  return DECK_NEUTRAL;
}
