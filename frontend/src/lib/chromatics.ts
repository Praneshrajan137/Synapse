// Confidence colour science — the gate-anchored diverging scale + the
// value-suppressing uncertainty model (VSUP).
//
// WHY THIS EXISTS
// ---------------
// The legacy `confidence.ts` ramp banded confidence into three sRGB stops
// (ok / warn / risk). The canonical SYNAPSE Chromatic System
// (`design-system/color/dist/tokens.ts::confidenceColor`) defines a *continuous*
// diverging scale in OKLCH whose stops are anchored EXACTLY at the I-5 gates
// (0.00 / 0.70 / 0.80 / 1.00) and whose hue sweeps red → orange → green → teal
// (INV-CLR-007). This module mirrors that scale for the frontend so confidence
// is rendered perceptually, not bucketed — and adds the VSUP layer that drains
// chroma as confidence falls below the gate, so a low-confidence value LOOKS
// uncertain (Correll/Moritz/Heer, "Value-Suppressing Uncertainty Palettes",
// CHI 2018).
//
// Every value returned is an `oklch(...)` string — a derived colour, never a
// raw hex/rgb/hsl literal (INV-CLR-009). Pure + deterministic: trivially
// testable, no allocation in the hot path beyond the result string.

import type { AgentName } from "@lib/agent-identity";

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
    { pos: 0.7, l: 0.68, c: 0.155, h: 55 }, // orange — low gate
    { pos: 0.8, l: 0.58, c: 0.1597, h: 150 }, // green  — high gate
    { pos: 1, l: 0.6, c: 0.1074, h: 182 }, // teal   — peak
  ],
  dark: [
    { pos: 0, l: 0.64, c: 0.19, h: 27 },
    { pos: 0.7, l: 0.82, c: 0.1174, h: 55 },
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
  const pct = rationedAgentShare(activity);
  return `color-mix(in oklab, ${agentVar} ${pct}%, var(--syn-neutral-mix))`;
}

/**
 * The agent's identity share, in percent, of a rationed fill: 18 % at rest
 * (`activity = 0`) up to 100 % at full activity. `rationedAgentColor` writes
 * this number into its `color-mix()` and `glyphInk` reads it, so a fill and the
 * ink drawn on it are computed from one mix.
 */
export function rationedAgentShare(activity: number): number {
  return Math.round(18 + clamp01(activity) * 82);
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
  const pct = processStateShare(state);
  return `color-mix(in oklab, ${agentVar} ${pct}%, var(--syn-neutral-mix))`;
}

/**
 * The identity share, in percent, of a process-state fill: the state's chroma
 * factor as a percentage. `processStateColor` writes it into its `color-mix()`
 * and `glyphInk` reads it, so the fill and its glyph ink cannot drift apart.
 */
export function processStateShare(state: AgentProcessState): number {
  return Math.round(AGENT_STATE_FACTOR[state] * 100);
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

// ---------------------------------------------------------------------------
// Glyph ink (finding 131): which ink token an agent's monogram is drawn in on
// its own rationed fill. Everything below is measurement; a fill is rendered
// only through `processStateColor` / `rationedAgentColor`.
// ---------------------------------------------------------------------------

/** An OKLCH colour as tokens.css declares it: lightness in [0,1], chroma, hue in degrees. */
export interface Oklch {
  readonly l: number;
  readonly c: number;
  readonly h: number;
}

/** An 8-bit sRGB colour, the channel form tokens.css declares the inks in. */
export type Rgb255 = readonly [number, number, number];

/** The two text tokens a glyph can be drawn in: `--syn-ink` and `--syn-ink-inverse`. */
export type GlyphInk = "ink" | "ink-inverse";

/** The tokens one theme hands the glyph-ink rule. */
export interface GlyphInkTokens {
  /** `--syn-agent-*`, the frozen identity colours (INV-CLR-012). */
  readonly agents: Readonly<Record<AgentName, Oklch>>;
  /** `--syn-neutral-mix`, the base every rationed fill drains toward. */
  readonly neutralMix: Oklch;
  /** `--syn-ink`. */
  readonly ink: Rgb255;
  /** `--syn-ink-inverse`. */
  readonly inkInverse: Rgb255;
}

const DARK_GLYPH_INK_TOKENS: GlyphInkTokens = {
  agents: {
    demand_prophet: { l: 0.715, c: 0.17, h: 292 },
    routing_navigator: { l: 0.64, c: 0.16, h: 248 },
    inventory_sentinel: { l: 0.685, c: 0.18, h: 330 },
    freshness_guardian: { l: 0.79, c: 0.16, h: 145 },
    pricing_oracle: { l: 0.5, c: 0.19, h: 270 },
    disruption_shield: { l: 0.66, c: 0.175, h: 30 },
    supplier_trust: { l: 0.755, c: 0.135, h: 207 },
    sustainability_agent: { l: 0.7, c: 0.13, h: 168 },
  },
  neutralMix: { l: 0.55, c: 0.006, h: 250 },
  ink: [245, 246, 247],
  inkInverse: [2, 4, 7],
};

/**
 * Mirror of the tokens.css values the glyph-ink rule reads, per theme.
 * chromatics.test.ts pins every value against tokens.css, so the rule cannot
 * compute a fill the page does not paint. The hc block declares neither agent
 * colours nor `--syn-ink-inverse`, so hc inherits the dark ones from `:root`.
 */
export const GLYPH_INK_TOKENS: Readonly<Record<ChromaticTheme, GlyphInkTokens>> = {
  dark: DARK_GLYPH_INK_TOKENS,
  light: {
    agents: {
      demand_prophet: { l: 0.54, c: 0.185, h: 292 },
      routing_navigator: { l: 0.44, c: 0.16, h: 248 },
      inventory_sentinel: { l: 0.5, c: 0.205, h: 330 },
      freshness_guardian: { l: 0.56, c: 0.155, h: 145 },
      pricing_oracle: { l: 0.37, c: 0.2, h: 270 },
      disruption_shield: { l: 0.5, c: 0.19, h: 30 },
      supplier_trust: { l: 0.6, c: 0.115, h: 207 },
      sustainability_agent: { l: 0.46, c: 0.115, h: 168 },
    },
    neutralMix: { l: 0.62, c: 0.006, h: 250 },
    ink: [28, 32, 36],
    inkInverse: [252, 252, 253],
  },
  hc: {
    agents: DARK_GLYPH_INK_TOKENS.agents,
    neutralMix: { l: 0.6, c: 0, h: 0 },
    ink: [255, 255, 255],
    inkInverse: DARK_GLYPH_INK_TOKENS.inkInverse,
  },
};

interface Oklab {
  readonly l: number;
  readonly a: number;
  readonly b: number;
}

function oklabOf({ l, c, h }: Oklch): Oklab {
  const hue = (h * Math.PI) / 180;
  return { l, a: c * Math.cos(hue), b: c * Math.sin(hue) };
}

/**
 * CSS `color-mix(in oklab, first p%, second)` for two opaque colours: every
 * OKLab coordinate interpolated by the first colour's share `p` in [0,1].
 */
function mixOklab(first: Oklab, second: Oklab, firstShare: number): Oklab {
  const p = clamp01(firstShare);
  const q = 1 - p;
  return {
    l: first.l * p + second.l * q,
    a: first.a * p + second.a * q,
    b: first.b * p + second.b * q,
  };
}

/** The sRGB transfer function: a linear-light channel in [0,1] to its encoded value. */
function encodeSrgb(linear: number): number {
  return linear <= 0.0031308 ? linear * 12.92 : 1.055 * linear ** (1 / 2.4) - 0.055;
}

/**
 * Its inverse, as WCAG 2.1 relative luminance applies it. WCAG's 0.03928 and the
 * sRGB standard's 0.04045 thresholds agree on every 8-bit channel value.
 */
function decodeSrgb(encoded: number): number {
  return encoded <= 0.04045 ? encoded / 12.92 : ((encoded + 0.055) / 1.055) ** 2.4;
}

/**
 * An OKLab colour as the 8-bit sRGB a browser paints: OKLab to linear sRGB
 * (Ottosson's matrices), clipped into the gamut, encoded and rounded. Axe's
 * round-2 ratios for the Pricing Oracle match the rounded fills, not the
 * unrounded ones, so the rule measures what axe measures.
 */
function srgb8Of({ l, a, b }: Oklab): Rgb255 {
  const lCone = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const mCone = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const sCone = (l - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const channel = (linear: number): number => Math.round(encodeSrgb(clamp01(linear)) * 255);
  return [
    channel(4.0767416621 * lCone - 3.3077115913 * mCone + 0.2309699292 * sCone),
    channel(-1.2684380046 * lCone + 2.6097574011 * mCone - 0.3413193965 * sCone),
    channel(-0.0041960863 * lCone - 0.7034186147 * mCone + 1.707614701 * sCone),
  ];
}

/** WCAG 2.1 relative luminance of an 8-bit sRGB colour. */
function relativeLuminance([r, g, b]: Rgb255): number {
  return 0.2126 * decodeSrgb(r / 255) + 0.7152 * decodeSrgb(g / 255) + 0.0722 * decodeSrgb(b / 255);
}

/** WCAG 2.1 contrast ratio between two relative luminances. */
function contrastRatio(first: number, second: number): number {
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

/**
 * The fill under an agent's glyph as 8-bit sRGB: the agent's token mixed into
 * the theme's neutral at `sharePercent`, the mix `processStateColor` and
 * `rationedAgentColor` ask the browser for. For measurement only.
 */
export function agentFillRgb(
  agent: AgentName,
  sharePercent: number,
  theme: ChromaticTheme,
): Rgb255 {
  const tokens = GLYPH_INK_TOKENS[theme];
  return srgb8Of(
    mixOklab(oklabOf(tokens.agents[agent]), oklabOf(tokens.neutralMix), sharePercent / 100),
  );
}

/** WCAG 2.1 contrast of an ink token drawn on an agent's fill. */
export function glyphContrast(
  agent: AgentName,
  sharePercent: number,
  theme: ChromaticTheme,
  ink: GlyphInk,
): number {
  const tokens = GLYPH_INK_TOKENS[theme];
  return contrastRatio(
    relativeLuminance(agentFillRgb(agent, sharePercent, theme)),
    relativeLuminance(ink === "ink" ? tokens.ink : tokens.inkInverse),
  );
}

/**
 * The ink an agent's monogram is drawn in on its own fill (finding 131): the
 * ink token with the higher WCAG 2.1 contrast against that fill. The choice is
 * read from the fill's luminance, never from an agent's name.
 *
 * Equivalently, the lighter ink wins exactly when the fill's relative luminance
 * Y is below Y* = sqrt((Ylight + 0.05) * (Ydark + 0.05)) - 0.05, the luminance at
 * which both inks give the same ratio, sqrt((Ylight + 0.05) / (Ydark + 0.05)). In
 * the dark theme the Pricing Oracle (ADR-048 D4, L 0.50) is the one agent token
 * darker than the neutral mix (L 0.55), so at the shares a council cell renders
 * (25 % and up) its fills alone take the light ink.
 *
 * What no choice of ink can do: where that equal ratio is below 4.5, fills whose
 * Y lies in a band around Y* clear 4.5:1 with neither ink. The light theme has
 * such a band around its neutral mix; there this rule picks the better ink and
 * still falls short, which is a token decision, not a rule to tune.
 */
export function glyphInk(agent: AgentName, sharePercent: number, theme: ChromaticTheme): GlyphInk {
  const onInk = glyphContrast(agent, sharePercent, theme, "ink");
  const onInverse = glyphContrast(agent, sharePercent, theme, "ink-inverse");
  return onInk > onInverse ? "ink" : "ink-inverse";
}
