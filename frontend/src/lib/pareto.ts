// Pareto front domain helpers — the 8 objectives, their agent identity, and a
// faithful client-side re-implementation of the orchestrator's knee-point
// selection (orchestrator/consensus/pareto.py::run_pareto_arbitration).
//
// The orchestrator emits a multi-objective Pareto front (one row per
// non-dominated solution, each row a value per objective in [0,1], higher =
// better) plus the meta-RL objective weights. The "knee point" is the solution
// closest to the ideal under the weighted distance metric. Re-implementing it
// here lets the UI (a) bold the chosen solution even when the audit row didn't
// persist a knee index, and (b) PREVIEW how a different weighting would move
// the choice — the heart of the Steering surface (SENSORIUM "The Will").

import type { AgentName } from "@lib/agent-identity";

/** The 8 objectives, in the canonical order of pareto.py::OBJECTIVES. */
export const PARETO_OBJECTIVES = [
  "demand_accuracy",
  "route_efficiency",
  "inventory_fill_rate",
  "freshness_score",
  "pricing_revenue",
  "disruption_readiness",
  "supplier_reliability",
  "carbon_efficiency",
] as const;

export type ParetoObjective = (typeof PARETO_OBJECTIVES)[number];

/** Short axis label per objective (dense parallel-coordinate headers). */
export const OBJECTIVE_LABEL: Record<ParetoObjective, string> = {
  demand_accuracy: "Demand",
  route_efficiency: "Route",
  inventory_fill_rate: "Fill",
  freshness_score: "Fresh",
  pricing_revenue: "Revenue",
  disruption_readiness: "Disrupt",
  supplier_reliability: "Supplier",
  carbon_efficiency: "Carbon",
};

/**
 * Objective → owning agent (inverse of pareto.py::_AGENT_TO_OBJECTIVE). Each
 * objective axis is tinted with its agent's frozen identity hue (INV-CLR-012),
 * so the operator reads "which agent's interest is this axis" pre-attentively.
 */
export const OBJECTIVE_AGENT: Record<ParetoObjective, AgentName> = {
  demand_accuracy: "demand_prophet",
  route_efficiency: "routing_navigator",
  inventory_fill_rate: "inventory_sentinel",
  freshness_score: "freshness_guardian",
  pricing_revenue: "pricing_oracle",
  disruption_readiness: "disruption_shield",
  supplier_reliability: "supplier_trust",
  carbon_efficiency: "sustainability_agent",
};

export type ParetoFront = ReadonlyArray<Readonly<Record<string, number>>>;

/** Per-axis [min, max] across the front; used to normalise each objective. */
export function axisExtents(
  front: ParetoFront,
  objectives: readonly string[] = PARETO_OBJECTIVES,
): Record<string, { min: number; max: number }> {
  const out: Record<string, { min: number; max: number }> = {};
  for (const obj of objectives) {
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const row of front) {
      const v = row[obj];
      if (typeof v !== "number" || !Number.isFinite(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      out[obj] = { min: 0, max: 1 };
    } else {
      out[obj] = { min, max };
    }
  }
  return out;
}

/**
 * Index of the knee point — the solution minimising the weighted, normalised
 * distance to the ideal (per-objective max). Mirrors pareto.py's selection
 * (there it minimises distance to the ideal of the negated/minimised front;
 * here, with positive "higher-is-better" values, the ideal is the max and we
 * minimise the gap below it). Returns null for an empty front.
 */
export function kneePointIndex(
  front: ParetoFront,
  weights: Readonly<Record<string, number>>,
  objectives: readonly string[] = PARETO_OBJECTIVES,
): number | null {
  if (front.length === 0) return null;
  if (front.length === 1) return 0;

  const extents = axisExtents(front, objectives);

  let bestIdx = 0;
  let bestDist = Number.POSITIVE_INFINITY;
  front.forEach((row, idx) => {
    let sumSq = 0;
    for (const obj of objectives) {
      const ext = extents[obj];
      if (!ext) continue;
      const span = ext.max - ext.min;
      const v = typeof row[obj] === "number" ? (row[obj] as number) : ext.min;
      // gap = how far below the ideal (max), normalised to [0,1].
      const gap = span <= 0 ? 0 : (ext.max - v) / span;
      const w = weights[obj] ?? 1;
      sumSq += (w * gap) ** 2;
    }
    const dist = Math.sqrt(sumSq);
    if (dist < bestDist) {
      bestDist = dist;
      bestIdx = idx;
    }
  });
  return bestIdx;
}
