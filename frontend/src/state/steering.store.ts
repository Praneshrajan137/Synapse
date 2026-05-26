import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Steering — operator-tunable governance (FE-INV-033).
 *
 * Two knobs that shape every consensus decision the orchestrator emits:
 *
 *   1. **Pareto objective weights** — how the arbitrator trades off
 *      cost / time / sustainability / fairness when ranking proposals.
 *      Must sum to a positive number; absolute scale is irrelevant
 *      (the arbitrator normalises). UI presents them on [0, 1] for
 *      operator intuition.
 *
 *   2. **Tier confidence thresholds** — the minimum confidence below
 *      which a decision at that tier is escalated to a human operator
 *      (I-5). Lower threshold → more decisions auto-confirmed.
 *      Higher threshold → more escalations to the Override Cockpit.
 *
 * Both are persisted to `localStorage["synapse.steering"]` via Zustand's
 * persist middleware so the operator's preferences survive reload. In
 * production every change is also audit-logged to the
 * `synapse.steering.config` Kafka topic (out of scope for this PR; that
 * write goes through the existing audit pipeline — see FE-INV-021).
 */

/** Pareto objective dimensions. Aligned with orchestrator/consensus/pareto.py. */
export interface ParetoWeights {
  readonly cost: number;
  readonly time: number;
  readonly sustainability: number;
  readonly fairness: number;
}

/** Per-tier minimum confidence; below this we escalate to HITL. */
export interface TierThresholds {
  readonly tier_2: number;
  readonly tier_3: number;
  readonly tier_4: number;
}

/**
 * Defaults are tuned to match `orchestrator/consensus/pareto.py` baseline.
 * Sum is intentionally exactly 1.0 so the persisted JSON is byte-stable
 * for first-load operators (helps with FE-INV-009 reproducible renders).
 */
export const DEFAULT_PARETO_WEIGHTS: ParetoWeights = {
  cost: 0.35,
  time: 0.35,
  sustainability: 0.2,
  fairness: 0.1,
};

export const DEFAULT_TIER_THRESHOLDS: TierThresholds = {
  tier_2: 0.7,
  tier_3: 0.65,
  tier_4: 0.5,
};

export interface SteeringState {
  readonly paretoWeights: ParetoWeights;
  readonly tierThresholds: TierThresholds;
  setParetoWeight(key: keyof ParetoWeights, value: number): void;
  setTierThreshold(tier: keyof TierThresholds, value: number): void;
  reset(): void;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

export const useSteeringStore = create<SteeringState>()(
  persist(
    (set) => ({
      paretoWeights: DEFAULT_PARETO_WEIGHTS,
      tierThresholds: DEFAULT_TIER_THRESHOLDS,
      setParetoWeight(key, value) {
        set((s) => ({
          paretoWeights: { ...s.paretoWeights, [key]: clamp01(value) },
        }));
      },
      setTierThreshold(tier, value) {
        set((s) => ({
          tierThresholds: { ...s.tierThresholds, [tier]: clamp01(value) },
        }));
      },
      reset() {
        set({
          paretoWeights: DEFAULT_PARETO_WEIGHTS,
          tierThresholds: DEFAULT_TIER_THRESHOLDS,
        });
      },
    }),
    {
      name: "synapse.steering",
      version: 1,
    },
  ),
);
