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

// v2.0.0 cool blue-graphite (ADR-048): every tuple below is a dist rgb255
// mirror, pinned against dist by lib/__tests__/chromatics.test.ts.

/** Quiet base — a dark store / idle node at rest. The state-neutral grey. */
export const DECK_NEUTRAL: RGBA = [143, 146, 150, 150]; // ← color.state.neutral dark
/** Muted connector line at rest (routes with nothing wrong). */
export const DECK_MUTED_LINE: RGBA = [143, 146, 150, 120];

// Signal palette — reserved for abnormality. Mirrors color.state/confidence.
export const DECK_INFO: RGBA = [102, 180, 252, 170]; // ← color.state.info dark
export const DECK_WARN: RGBA = [245, 116, 0, 220]; // ← color.state.warning dark (orange) — saturation > 0.7
export const DECK_RISK: RGBA = [235, 68, 65, 230]; // ← color.state.danger dark — saturation > 0.9
export const DECK_RISK_SOFT: RGBA = [233, 80, 72, 210]; // ← color.confidence.low dark — risk arc target

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
