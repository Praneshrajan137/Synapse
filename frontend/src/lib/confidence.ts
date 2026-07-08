// Confidence ramp + tier helpers. Centralized so every visual decision uses
// the same thresholds (I-5 gating; tier_router.py SLAs).

export type Tier = "tier_1" | "tier_2" | "tier_3" | "tier_4";
export type ConfidenceBand = "ok" | "warn" | "risk";

export const TIER_SLA_MS: Record<Tier, number> = {
  tier_1: 100,
  tier_2: 500,
  tier_3: 15_000,
  tier_4: 120_000,
};

export const TIER_LABEL: Record<Tier, string> = {
  tier_1: "Tier 1",
  tier_2: "Tier 2",
  tier_3: "Tier 3",
  tier_4: "Tier 4",
};

export const TIER_DESCRIPTION: Record<Tier, string> = {
  tier_1: "RL-only, single agent (<100ms)",
  tier_2: "Lightweight LLM, 2–3 agents (<500ms)",
  tier_3: "Multi-agent debate, up to 3 rounds (2–15s)",
  tier_4: "System-wide, Monte Carlo + 70B LLM (15–120s)",
};

export function confidenceBand(value: number): ConfidenceBand {
  if (value >= 0.9) return "ok";
  if (value >= 0.7) return "warn";
  return "risk";
}

/**
 * Format a confidence value as a fixed two-decimal string in the range
 * "0.00".."1.00" (Req 4.1). The value is clamped defensively into [0,1] and
 * non-finite input collapses to "0.00", so the output ALWAYS matches
 * `^[01]\.\d{2}$` — the numeric-text honesty channel that must render alongside
 * any confidence colour (Req 4.2, INV-CLR-011). Colour can drain; the number
 * never lies.
 *
 * This is the single source of truth for the two-decimal channel: it lives in
 * the lib layer so both the design-system `ConfidenceChip` compound and the
 * `operations` surface consume the identical formatter.
 */
export function formatConfidence(x: number): string {
  const clamped = !Number.isFinite(x) ? 0 : x < 0 ? 0 : x > 1 ? 1 : x;
  return clamped.toFixed(2);
}

export function isBelowThreshold(value: number, threshold = 0.7): boolean {
  return value < threshold;
}
