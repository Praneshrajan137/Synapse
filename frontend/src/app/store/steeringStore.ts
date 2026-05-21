import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Steering state (plan section 6.7) — the operator-tunable governance
 * knobs: multi-objective Pareto weights and per-tier confidence
 * thresholds. Persisted; in production these changes are themselves
 * audit-logged to the synapse.steering.config topic.
 */

export interface ParetoWeights {
  cost: number;
  time: number;
  sustainability: number;
  fairness: number;
}

export interface TierThresholds {
  tier_2: number;
  tier_3: number;
  tier_4: number;
}

const DEFAULT_WEIGHTS: ParetoWeights = {
  cost: 0.35,
  time: 0.35,
  sustainability: 0.2,
  fairness: 0.1,
};

const DEFAULT_THRESHOLDS: TierThresholds = {
  tier_2: 0.7,
  tier_3: 0.65,
  tier_4: 0.5,
};

export interface SteeringState {
  paretoWeights: ParetoWeights;
  setParetoWeight: (key: keyof ParetoWeights, value: number) => void;
  tierThresholds: TierThresholds;
  setTierThreshold: (tier: keyof TierThresholds, value: number) => void;
  reset: () => void;
}

export const useSteeringStore = create<SteeringState>()(
  persist(
    (set) => ({
      paretoWeights: DEFAULT_WEIGHTS,
      setParetoWeight: (key, value) =>
        set((s) => ({ paretoWeights: { ...s.paretoWeights, [key]: value } })),
      tierThresholds: DEFAULT_THRESHOLDS,
      setTierThreshold: (tier, value) =>
        set((s) => ({ tierThresholds: { ...s.tierThresholds, [tier]: value } })),
      reset: () =>
        set({ paretoWeights: DEFAULT_WEIGHTS, tierThresholds: DEFAULT_THRESHOLDS }),
    }),
    { name: "synapse.steering" },
  ),
);
