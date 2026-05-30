// Canonical presentation identity for the eight SYNAPSE agents.
//
// One source of truth for an agent's human label, its two-letter monogram,
// and its chromatic-token CSS variable (INV-CLR-012 — the 8 agent→hue
// assignments are FROZEN; changing one needs a version bump + an ADR
// supersede note). Colour reaches a component ONLY through these
// `var(--syn-agent-*)` tokens — never a raw literal (INV-CLR-009).
//
// `ProposalConstellation` re-exports `AGENT_NAMES` / `AgentName` from here so
// there is exactly one frozen registry shared by every agent-aware surface
// (the constellation, the Council strip, the Pulse).

/** Frozen 8-agent registry — must match `agents/*` and CLAUDE.md, in order. */
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

/** Human-facing label. Locale-stable; not translated (proper noun). */
export const AGENT_LABEL: Record<AgentName, string> = {
  demand_prophet: "Demand Prophet",
  routing_navigator: "Routing Navigator",
  inventory_sentinel: "Inventory Sentinel",
  freshness_guardian: "Freshness Guardian",
  pricing_oracle: "Pricing Oracle",
  disruption_shield: "Disruption Shield",
  supplier_trust: "Supplier Trust",
  sustainability_agent: "Sustainability Agent",
};

/** Two-letter monogram — icon-free, locale-stable, fits a small node. */
export const AGENT_INITIALS: Record<AgentName, string> = {
  demand_prophet: "DP",
  routing_navigator: "RN",
  inventory_sentinel: "IS",
  freshness_guardian: "FG",
  pricing_oracle: "PO",
  disruption_shield: "DS",
  supplier_trust: "ST",
  sustainability_agent: "SA",
};

/**
 * Per-agent chromatic-token CSS variable, resolved at render time. The hue is
 * frozen (INV-CLR-012); the variable swaps light/dark/hc variants under
 * `[data-theme]`. Never inline a colour — always reference the token.
 */
export const AGENT_COLOR_VAR: Record<AgentName, string> = {
  demand_prophet: "var(--syn-agent-demand-prophet)",
  routing_navigator: "var(--syn-agent-routing-navigator)",
  inventory_sentinel: "var(--syn-agent-inventory-sentinel)",
  freshness_guardian: "var(--syn-agent-freshness-guardian)",
  pricing_oracle: "var(--syn-agent-pricing-oracle)",
  disruption_shield: "var(--syn-agent-disruption-shield)",
  supplier_trust: "var(--syn-agent-supplier-trust)",
  sustainability_agent: "var(--syn-agent-sustainability-agent)",
};

/** Convenience accessor — the chromatic token var for an agent. */
export function agentColorVar(agent: AgentName): string {
  return AGENT_COLOR_VAR[agent];
}
