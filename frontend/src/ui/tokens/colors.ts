/**
 * Synaptic Calm — color tokens (JS mirror of styles/globals.css @theme).
 *
 * Canvas / charts / three.js / deck.gl cannot read CSS custom properties
 * cheaply, so they consume these raw values. The CSS file remains the
 * design source of truth; this file must be kept in lockstep with it.
 * (A future codegen step will derive one from the other — for now the
 * colors.test.ts unit test asserts they have not drifted.)
 */

/** Canvas — "the silence". */
export const canvas = {
  void: "#05070D",
  paper: "#0C111B",
  elevated: "#141B2A",
  membrane: "#1B2336",
} as const;

/** Ink — "the voice". */
export const ink = {
  primary: "#E6EDF8",
  secondary: "#9AA7BD",
  hint: "#5C6A82",
  disabled: "#364154",
} as const;

/** Hairlines. */
export const line = {
  faint: "rgba(154,167,189,0.08)",
  strong: "rgba(154,167,189,0.16)",
} as const;

/** Signals — "the meaning". Semantic only, never decorative. */
export const signal = {
  live: "#5BE2FF",
  think: "#B68CFF",
  warn: "#FFB454",
  stop: "#FF6B6B",
  ok: "#7BE9A7",
  trace: "#4ECDC4",
} as const;

/** The canonical eight agents, in protocol order. */
export const AGENT_NAMES = [
  "demand_prophet",
  "routing_navigator",
  "inventory_sentinel",
  "freshness_guardian",
  "pricing_oracle",
  "disruption_shield",
  "supplier_trust",
  "sustainability_agent",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];

/** Agent sigil hues — Okabe-Ito-derived, AAA on --color-void. */
export const agentColor: Record<AgentName, string> = {
  demand_prophet: "#6F8CFF",
  routing_navigator: "#5BE2FF",
  inventory_sentinel: "#7BE9A7",
  freshness_guardian: "#C2F26B",
  pricing_oracle: "#FFD466",
  disruption_shield: "#FF7A8A",
  supplier_trust: "#B68CFF",
  sustainability_agent: "#4ECDC4",
};

/** Decision-tier accent — escalates cool→warm as latency budget grows. */
export const tierColor = {
  tier_1: signal.ok,
  tier_2: signal.live,
  tier_3: signal.warn,
  tier_4: signal.stop,
} as const;

export type TierKey = keyof typeof tierColor;

/**
 * Map a confidence value to its semantic signal color.
 * Mirrors the HITL gating bands (plan tenet T-4): a single number is a
 * lie, but for compact glyphs (badges, dots) we still need one color.
 */
export function confidenceColor(value: number): string {
  if (value >= 0.9) return signal.ok;
  if (value >= 0.65) return signal.live;
  if (value >= 0.4) return signal.warn;
  return signal.stop;
}

export const palette = { canvas, ink, line, signal } as const;
