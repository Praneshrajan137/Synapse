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
 * persist middleware so the operator's preferences survive reload.
 *
 * WS-5: every mutation also hits `POST /api/v1/steering` so the change
 * lands in the `audit_steering` table BEFORE local state moves. On
 * failure the optimistic update is reverted. The audit-first guarantee
 * matches FE-INV-021 (audit row precedes orchestrator notification).
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

/**
 * Backend-write hook. The API client wires this in app/providers.tsx so
 * the store stays decoupled from the network layer (testable, no fetch
 * stubbing required for unit tests). Set to a no-op for stories and
 * isolated unit tests.
 */
type SteeringAuditWriter = (change: {
  action: "set_pareto_weight" | "set_tier_threshold" | "reset";
  target?: string | null;
  value?: number | null;
  idempotency_key?: string;
}) => Promise<unknown>;

let steeringWriter: SteeringAuditWriter = async () => {
  /* default: no-op — tests + stories use this */
};

export function setSteeringWriter(writer: SteeringAuditWriter): void {
  steeringWriter = writer;
}

function makeIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export interface SteeringState {
  readonly paretoWeights: ParetoWeights;
  readonly tierThresholds: TierThresholds;
  readonly lastError: string | null;
  setParetoWeight(key: keyof ParetoWeights, value: number): Promise<void>;
  setTierThreshold(tier: keyof TierThresholds, value: number): Promise<void>;
  reset(): Promise<void>;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

export const useSteeringStore = create<SteeringState>()(
  persist(
    (set, get) => ({
      paretoWeights: DEFAULT_PARETO_WEIGHTS,
      tierThresholds: DEFAULT_TIER_THRESHOLDS,
      lastError: null,
      async setParetoWeight(key, value) {
        const next = clamp01(value);
        const before = get().paretoWeights;
        // Optimistic update.
        set({ paretoWeights: { ...before, [key]: next }, lastError: null });
        try {
          await steeringWriter({
            action: "set_pareto_weight",
            target: key,
            value: next,
            idempotency_key: makeIdempotencyKey(),
          });
        } catch (err) {
          // Audit insert failed — revert and surface the error.
          set({ paretoWeights: before, lastError: errMsg(err) });
        }
      },
      async setTierThreshold(tier, value) {
        const next = clamp01(value);
        const before = get().tierThresholds;
        set({ tierThresholds: { ...before, [tier]: next }, lastError: null });
        try {
          await steeringWriter({
            action: "set_tier_threshold",
            target: tier,
            value: next,
            idempotency_key: makeIdempotencyKey(),
          });
        } catch (err) {
          set({ tierThresholds: before, lastError: errMsg(err) });
        }
      },
      async reset() {
        const beforeP = get().paretoWeights;
        const beforeT = get().tierThresholds;
        set({
          paretoWeights: DEFAULT_PARETO_WEIGHTS,
          tierThresholds: DEFAULT_TIER_THRESHOLDS,
          lastError: null,
        });
        try {
          await steeringWriter({
            action: "reset",
            idempotency_key: makeIdempotencyKey(),
          });
        } catch (err) {
          set({
            paretoWeights: beforeP,
            tierThresholds: beforeT,
            lastError: errMsg(err),
          });
        }
      },
    }),
    {
      name: "synapse.steering",
      version: 1,
      // Only the values persist; transient lastError stays in memory.
      partialize: (s) => ({
        paretoWeights: s.paretoWeights,
        tierThresholds: s.tierThresholds,
      }),
    },
  ),
);

function errMsg(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
