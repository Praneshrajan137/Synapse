import { type AgentName, agentColor } from "@/ui/tokens";
import type { ReactNode } from "react";

/**
 * AgentSigil — the custom geometric monogram for each of the eight
 * agents (plan section 3.6). Sigils are geometric, not illustrative;
 * operators learn to recognize agents by sigil and motion alone.
 *
 * Drawn in a 24x24 grid, stroke-based, inheriting `currentColor`.
 */

const AGENT_LABEL: Record<AgentName, string> = {
  demand_prophet: "Demand Prophet",
  routing_navigator: "Routing Navigator",
  inventory_sentinel: "Inventory Sentinel",
  freshness_guardian: "Freshness Guardian",
  pricing_oracle: "Pricing Oracle",
  disruption_shield: "Disruption Shield",
  supplier_trust: "Supplier Trust",
  sustainability_agent: "Sustainability Agent",
};

/** Sigil geometry per agent. Stroke inherits currentColor. */
const SIGIL: Record<AgentName, ReactNode> = {
  // Forking forecast line splitting into five horizons.
  demand_prophet: (
    <>
      <path d="M3 12h7" />
      <path d="M10 12 21 4M10 12 21 8.5M10 12h11M10 12 21 15.5M10 12 21 20" />
      <circle cx="10" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </>
  ),
  // Directed arrow weaving through three waypoints.
  routing_navigator: (
    <>
      <path d="M3 19 9 6l6 12 6-13" />
      <path d="m17 7 4-2 .6 4.3" />
      <circle cx="9" cy="6" r="1.7" fill="currentColor" stroke="none" />
      <circle cx="15" cy="18" r="1.7" fill="currentColor" stroke="none" />
    </>
  ),
  // Stacked-rectangle tower with a fill level.
  inventory_sentinel: (
    <>
      <rect
        x="6.5"
        y="14.5"
        width="11"
        height="6"
        rx="1"
        fill="currentColor"
        stroke="none"
      />
      <rect x="6.5" y="8.5" width="11" height="6" rx="1" />
      <rect x="6.5" y="2.8" width="11" height="6" rx="1" />
      <path d="M9.5 11.5h5" />
    </>
  ),
  // Clock face with a freshness leaf.
  freshness_guardian: (
    <>
      <circle cx="11" cy="13" r="8" />
      <path d="M11 13V8.5M11 13l3.4 2.2" />
      <path d="M16.5 4.5c2.6-1.4 4.7-1 4.7-1s.4 2.1-1 4.7c-1 1.8-3.7 1.3-3.7 1.3s-.5-2.7 0-5" />
    </>
  ),
  // Tilted balance scale.
  pricing_oracle: (
    <>
      <path d="M12 3v17M7 20h10" />
      <path d="M4 8.5 20 6" />
      <path d="M4 8.5 1.6 14a3 3 0 0 0 4.8 0z" />
      <path d="M20 6l-2.4 5.5a3 3 0 0 0 4.8 0z" />
    </>
  ),
  // Hexagonal shield with a fracture.
  disruption_shield: (
    <>
      <path d="M12 2.5 20 7v6.5C20 18 16.4 21 12 22 7.6 21 4 18 4 13.5V7z" />
      <path d="M12 6.5 9.5 12l4 1.6L11 18" />
    </>
  ),
  // Two interlocking chain links.
  supplier_trust: (
    <>
      <rect x="2.8" y="8.5" width="11" height="7" rx="3.5" />
      <rect x="10.2" y="8.5" width="11" height="7" rx="3.5" />
    </>
  ),
  // Concentric carbon-footprint rings.
  sustainability_agent: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5.4" />
      <circle cx="12" cy="12" r="1.8" fill="currentColor" stroke="none" />
    </>
  ),
};

export interface AgentSigilProps {
  agent: AgentName;
  /** Pixel size of the square sigil. */
  size?: number;
  className?: string;
  /** Override the stroke color. Defaults to the agent's token hue. */
  color?: string;
  /**
   * When omitted the sigil is decorative (aria-hidden). Pass `title` to
   * make it a labelled standalone image.
   */
  title?: string;
}

export function AgentSigil({
  agent,
  size = 24,
  className,
  color,
  title,
}: AgentSigilProps) {
  const labelled = title !== undefined;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ color: color ?? agentColor[agent] }}
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-label={labelled ? title : undefined}
    >
      {labelled && <title>{title}</title>}
      {SIGIL[agent]}
    </svg>
  );
}

export { AGENT_LABEL };
