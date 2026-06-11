// Confidence colour science — the gate-anchored diverging scale + the
// value-suppressing uncertainty model (VSUP).
//
// WHY THIS EXISTS
// ---------------
// The legacy `confidence.ts` ramp banded confidence into three sRGB stops
// (ok / warn / risk). The canonical SYNAPSE Chromatic System
// (`design-system/color/dist/tokens.ts::confidenceColor`) defines a *continuous*
// diverging scale in OKLCH whose stops are anchored EXACTLY at the I-5 gates
// (0.00 / 0.70 / 0.80 / 1.00) and whose hue sweeps red → amber → green → teal
// (INV-CLR-007). This module mirrors that scale for the frontend so confidence
// is rendered perceptually, not bucketed — and adds the VSUP layer that drains
// chroma as confidence falls below the gate, so a low-confidence value LOOKS
// uncertain (Correll/Moritz/Heer, "Value-Suppressing Uncertainty Palettes",
// CHI 2018).
//
// Every value returned is an `oklch(...)` string — a derived colour, never a
// raw hex/rgb/hsl literal (INV-CLR-009). Pure + deterministic: trivially
// testable, no allocation in the hot path beyond the result string.

export type ChromaticTheme = "light" | "dark" | "hc";

/** The I-5 confidence gates. Below `low` → escalate; above `high` → autonomous. */
export const CONFIDENCE_GATE = { low: 0.7, high: 0.8 } as const;

export type ConfidenceZone = "low" | "escalation" | "autonomous";

/**
 * Classify a confidence value against the I-5 gates.
 *   < 0.70           → "low"         (would escalate to a human)
 *   [0.70, 0.80)     → "escalation"  (borderline — the gate band)
 *   >= 0.80          → "autonomous"  (the system acts without asking)
 */
export function confidenceZone(value: number): ConfidenceZone {
  if (value < CONFIDENCE_GATE.low) return "low";
  if (value < CONFIDENCE_GATE.high) return "escalation";
  return "autonomous";
}

interface Stop {
  readonly pos: number;
  readonly l: number;
  readonly c: number;
  readonly h: number;
}

type StopQuad = readonly [Stop, Stop, Stop, Stop];

// Stops mirror design-system/color/dist/tokens.ts::CONFIDENCE_STOPS so the FE
// and the design-system speak the identical scale. Anchored at the I-5 gates.
const STOPS: Record<"light" | "dark", StopQuad> = {
  light: [
    { pos: 0, l: 0.53, c: 0.205, h: 27 }, // red    — no confidence
    { pos: 0.7, l: 0.68, c: 0.1428, h: 76 }, // amber  — low gate
    { pos: 0.8, l: 0.58, c: 0.1597, h: 150 }, // green  — high gate
    { pos: 1, l: 0.6, c: 0.1074, h: 182 }, // teal   — peak
  ],
  dark: [
    { pos: 0, l: 0.64, c: 0.19, h: 27 },
    { pos: 0.7, l: 0.82, c: 0.15, h: 80 },
    { pos: 0.8, l: 0.8, c: 0.165, h: 148 },
    { pos: 1, l: 0.84, c: 0.115, h: 184 },
  ],
};

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function round(value: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(value * f) / f;
}

/**
 * VSUP chroma multiplier in [0,1]. Full chroma above the high gate; chroma
 * drains as confidence falls, anchored at the I-5 gates so the colour visibly
 * desaturates exactly where the system would hand off to a human:
 *
 *   >= 0.80         → 1.00  (crisp, fully saturated — the machine is sure)
 *   [0.70, 0.80)    → 0.55 … 1.00  (the escalation band, partially drained)
 *   [0.50, 0.70)    → 0.15 … 0.55  (clearly uncertain)
 *   <  0.50         → 0.15  (near-monochrome — the colour has drained out)
 *
 * The 0.15 floor (not 0) keeps a hue *hint* so the diverging direction is still
 * legible; colour is never the sole signal anyway (INV-CLR-011).
 */
export function vsupChromaFactor(value: number): number {
  const v = clamp01(value);
  if (v >= CONFIDENCE_GATE.high) return 1;
  if (v >= CONFIDENCE_GATE.low) {
    // 0.70 → 0.55, 0.80 → 1.00
    return 0.55 + ((v - CONFIDENCE_GATE.low) / (CONFIDENCE_GATE.high - CONFIDENCE_GATE.low)) * 0.45;
  }
  if (v >= 0.5) {
    // 0.50 → 0.15, 0.70 → 0.55
    return 0.15 + ((v - 0.5) / (CONFIDENCE_GATE.low - 0.5)) * 0.4;
  }
  return 0.15;
}

export interface ConfidenceColorOptions {
  readonly theme?: ChromaticTheme;
  /** Apply VSUP chroma suppression so low confidence renders desaturated. */
  readonly vsup?: boolean;
}

/**
 * Continuous confidence colour for `value` in [0,1], interpolated piecewise in
 * OKLCH across the gate-anchored stops. Returns an `oklch(L C H)` string.
 *
 * `hc` (high-contrast) borrows the dark stops; the numeric readout carries the
 * value there, so the diverging hue is decorative-but-consistent, not load-
 * bearing.
 */
export function confidenceColor(value: number, options: ConfidenceColorOptions = {}): string {
  const { theme = "dark", vsup = false } = options;
  const stops = STOPS[theme === "light" ? "light" : "dark"];
  const v = clamp01(value);

  // `stops` is a fixed 4-tuple, so the literal endpoints are always defined.
  let a: Stop = stops[0];
  let b: Stop = stops[3];
  for (let i = 0; i < stops.length - 1; i++) {
    const lo = stops[i];
    const hi = stops[i + 1];
    if (lo && hi && v >= lo.pos && v <= hi.pos) {
      a = lo;
      b = hi;
      break;
    }
  }

  const span = b.pos - a.pos || 1;
  const t = (v - a.pos) / span;
  const lerp = (x: number, y: number): number => x + (y - x) * t;

  const l = lerp(a.l, b.l);
  const c = lerp(a.c, b.c) * (vsup ? vsupChromaFactor(v) : 1);
  const h = lerp(a.h, b.h);

  return `oklch(${round(l, 4)} ${round(c, 4)} ${round(h, 2)})`;
}

/**
 * A CSS `color-mix` expression that drains an agent's frozen identity colour
 * toward the quiet neutral base as a function of "activity" in [0,1].
 *
 * This is the chromatic substrate of the "quiet by default" principle: at rest
 * (`activity = 0`) the colour is heavily mixed toward `--syn-neutral-mix` (near
 * monochrome); on activity (`activity = 1`) the agent's full hue is present.
 * Colour is rationed, so it carries signal when it appears (ISA-101 HP-HMI;
 * PR-CLR-002 "every hue is earned").
 *
 * Returns a `color-mix(in oklab, …)` string — token-only, no raw literal.
 */
export function rationedAgentColor(agentVar: string, activity: number): string {
  const a = clamp01(activity);
  // 18 % hue at rest → 100 % at full activity.
  const pct = Math.round(18 + a * 82);
  return `color-mix(in oklab, ${agentVar} ${pct}%, var(--syn-neutral-mix))`;
}

// ---------------------------------------------------------------------------
// Chromatic v1.1.0 (ADR-044) — agent process-state grammar + honesty states.
// ---------------------------------------------------------------------------

/**
 * What an agent is DOING, as a chromatic state. Identity hue is FROZEN
 * (INV-CLR-012); process state is encoded as chroma rationing — a scalar
 * factor on the identity colour, strictly monotone with cognitive activity
 * (INV-CLR-017). `recovered` is deliberately absent: recovery is a motion
 * event (one arrive-flash, then settle), not a colour.
 */
export type AgentProcessState =
  | "interrupted"
  | "waiting"
  | "thinking"
  | "debating"
  | "acting"
  | "escalated";

/**
 * Mirror of `factor.agentstate.*` in design-system/color/dist/tokens.json —
 * pinned byte-for-byte by chromatics.test.ts so the FE and the token system
 * cannot drift. escalated holds FULL chroma: urgency composes with the
 * danger ring + the 1200ms urgent pulse, never a colour change (MR-CLR-004:
 * state must not masquerade as a different agent).
 */
export const AGENT_STATE_FACTOR: Record<AgentProcessState, number> = {
  interrupted: 0.25,
  waiting: 0.35,
  thinking: 0.55,
  debating: 0.8,
  acting: 1,
  escalated: 1,
};

/**
 * The identity colour of an agent in a given process state. The chroma
 * factor maps directly to the identity share of a `color-mix()` toward the
 * quiet neutral base — an interrupted agent is nearly achromatic but never
 * invisible (the factor floor is 0.25, INV-CLR-017), an acting agent burns
 * at full identity. Token-only output (INV-CLR-009).
 */
export function processStateColor(agentVar: string, state: AgentProcessState): string {
  const pct = Math.round(AGENT_STATE_FACTOR[state] * 100);
  return `color-mix(in oklab, ${agentVar} ${pct}%, var(--syn-neutral-mix))`;
}

/**
 * The degraded honesty state (ADR-040/ADR-044): any output produced on a
 * fallback path renders in this chroma-drained caution colour — running on
 * reduced information must LOOK like reduced information (INV-CLR-016).
 */
export function degradedStateColor(): string {
  return "var(--syn-state-degraded)";
}

/**
 * The synthetic honesty state: traffic-generator decisions (`is_synthetic`)
 * render in this violet — always paired with a dashed ring + glyph, never
 * colour alone (INV-CLR-011).
 */
export function syntheticStateColor(): string {
  return "var(--syn-state-synthetic)";
}
