/**
 * SYNAPSE Atlas Console — Mission Control queue ranker.
 *
 * Plan §5.2 ordering rule:
 *
 *     score = tier_weight × (1 − confidence) × time_to_timeout_inv
 *
 * Higher score = more urgent (rendered first). The ranker is a pure
 * function of escalation + clock, so property tests can pin every
 * boundary case (`pnpm test:property`).
 *
 * Tier weights are spread across an order of magnitude so a tier-4
 * always outranks every tier-3, regardless of confidence — the ops
 * persona has been clear that tier escalations are categorical, not
 * comparable on a sliding scale.
 */
import type { Escalation, Tier } from "./escalation";

const TIER_WEIGHT: Record<Tier, number> = {
  tier_1: 1,
  tier_2: 4,
  tier_3: 16,
  tier_4: 64,
};

/**
 * Compute the queue score for one escalation given a wall-clock instant.
 * The clock is a parameter so tests can pin it.
 */
export function escalationScore(esc: Escalation, nowMs: number): number {
  const tierWeight = TIER_WEIGHT[esc.tier];
  const confidenceDeficit = clamp01(1 - esc.confidence);
  const ttlInv = timeToTimeoutInverse(esc, nowMs);
  return tierWeight * confidenceDeficit * ttlInv;
}

/**
 * Stable ordering: by score DESC; ties broken by issued_at ASC (older first
 * — fairness so a fast-arriving low-tier doesn't permanently leapfrog).
 *
 * Returns a NEW array; never mutates input. The caller passes a wall clock
 * so React renders are deterministic for any given tick.
 */
export function rankEscalations(
  list: readonly Escalation[],
  nowMs: number,
): readonly Escalation[] {
  const scored = list.map((e) => [e, escalationScore(e, nowMs)] as const);
  scored.sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1];
    const aTs = a[0].issued_at ?? "";
    const bTs = b[0].issued_at ?? "";
    return aTs < bTs ? -1 : aTs > bTs ? 1 : 0;
  });
  return scored.map(([e]) => e);
}

/**
 * Returns the seconds remaining before the escalation times out, given the
 * current wall clock. Falls back to the `timeout_seconds` field if the
 * escalation arrived without an `issued_at`.
 */
export function timeToTimeoutSeconds(esc: Escalation, nowMs: number): number {
  if (esc.timeout_seconds === undefined) return Number.POSITIVE_INFINITY;
  if (esc.issued_at === undefined) return Math.max(0, esc.timeout_seconds);
  const issuedMs = Date.parse(esc.issued_at);
  if (!Number.isFinite(issuedMs)) return Math.max(0, esc.timeout_seconds);
  const elapsedSec = (nowMs - issuedMs) / 1000;
  return Math.max(0, esc.timeout_seconds - elapsedSec);
}

/** Inverse of TTL with a soft floor — avoids divide-by-zero at expiry. */
function timeToTimeoutInverse(esc: Escalation, nowMs: number): number {
  const remaining = timeToTimeoutSeconds(esc, nowMs);
  if (!Number.isFinite(remaining)) {
    // No timeout supplied → treat as low urgency relative to those that have one.
    return 0.001;
  }
  return 1 / Math.max(1, remaining);
}

/**
 * Predicate used by `<UrgencyBar>` — true when any tier-4 escalation has
 * less than 30 s left before timeout.
 */
export function hasCriticalTier4(list: readonly Escalation[], nowMs: number): boolean {
  return list.some(
    (e) => e.tier === "tier_4" && timeToTimeoutSeconds(e, nowMs) <= 30,
  );
}

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
