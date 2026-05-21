/**
 * Digital Twin domain — the supply-network topology and the Monte Carlo
 * what-if engine (plan section 5.5).
 */

export type TwinNodeKind = "store" | "warehouse" | "supplier" | "rider" | "zone";

export interface TwinNode {
  readonly id: string;
  readonly kind: TwinNodeKind;
  readonly label: string;
  /** Normalized layout coordinates in [0, 1]. */
  readonly x: number;
  readonly y: number;
  /** Stress level in [0, 1] — drives node glow. */
  readonly stress: number;
}

export interface TwinEdge {
  readonly from: string;
  readonly to: string;
}

export interface TwinTopology {
  readonly nodes: readonly TwinNode[];
  readonly edges: readonly TwinEdge[];
}

export const SHOCK_SCENARIOS = [
  "demand_spike",
  "supplier_failure",
  "route_disruption",
  "monsoon",
  "ipl_surge",
] as const;
export type ShockScenario = (typeof SHOCK_SCENARIOS)[number];

export const SCENARIO_LABEL: Record<ShockScenario, string> = {
  demand_spike: "Demand spike",
  supplier_failure: "Supplier failure",
  route_disruption: "Route disruption",
  monsoon: "Monsoon (Mumbai)",
  ipl_surge: "IPL surge (Bengaluru)",
};

/** The four ShockParams multipliers fed to the twin. */
export interface ShockParams {
  demand: number;
  leadTime: number;
  failureRate: number;
  spoilage: number;
}

/** A KPI's distribution across the Monte Carlo scenario set. */
export interface KpiDistribution {
  readonly id: string;
  readonly label: string;
  readonly unit: string;
  readonly p5: number;
  readonly p50: number;
  readonly p95: number;
  readonly baseline: number;
}

export interface MonteCarloResult {
  readonly scenarioCount: number;
  readonly distributions: readonly KpiDistribution[];
}
