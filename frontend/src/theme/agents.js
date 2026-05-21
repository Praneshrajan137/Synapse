// SYNAPSE agent registry — display metadata for the 8 agents.
//
// Each agent carries THREE distinguishing channels so colour is never the
// sole signal (INV-CLR-011): an identity colour, a unique glyph, and a label.
// `key` is the hyphenated chromatic-token key; `id` is the backend agent name.

export const AGENTS = [
  {
    id: "demand_prophet",
    key: "demand-prophet",
    label: "Demand Prophet",
    glyph: "✦",
    role: "Multi-horizon demand forecasting",
  },
  {
    id: "routing_navigator",
    key: "routing-navigator",
    label: "Routing Navigator",
    glyph: "➤",
    role: "Rider routing & dispatch",
  },
  {
    id: "inventory_sentinel",
    key: "inventory-sentinel",
    label: "Inventory Sentinel",
    glyph: "▣",
    role: "Stock levels & replenishment",
  },
  {
    id: "freshness_guardian",
    key: "freshness-guardian",
    label: "Freshness Guardian",
    glyph: "❀",
    role: "Perishable shelf-life control",
  },
  {
    id: "pricing_oracle",
    key: "pricing-oracle",
    label: "Pricing Oracle",
    glyph: "◈",
    role: "Dynamic pricing within the I-6 cap",
  },
  {
    id: "disruption_shield",
    key: "disruption-shield",
    label: "Disruption Shield",
    glyph: "⚠",
    role: "Risk sensing & mitigation",
  },
  {
    id: "supplier_trust",
    key: "supplier-trust",
    label: "Supplier Trust",
    glyph: "⬡",
    role: "Supplier reliability scoring",
  },
  {
    id: "sustainability_agent",
    key: "sustainability-agent",
    label: "Sustainability Agent",
    glyph: "♺",
    role: "Carbon & waste minimisation",
  },
];

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a]));

/** Resolve an agent record from either an underscore id or a hyphen key. */
export function agentOf(name) {
  if (!name) return null;
  return AGENT_BY_ID[name] || AGENT_BY_ID[String(name).replace(/-/g, "_")] || null;
}

/** CSS custom-property reference for an agent identity colour. */
export function agentColorVar(name) {
  const a = agentOf(name);
  return a ? `var(--color-agent-${a.key})` : "var(--color-state-neutral)";
}
