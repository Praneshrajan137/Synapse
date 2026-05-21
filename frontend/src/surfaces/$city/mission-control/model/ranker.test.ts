/**
 * SYNAPSE Atlas Console — ranker property tests.
 *
 * The plan §5.2 ordering rule has three load-bearing invariants:
 *   1. Tier dominates: every tier-4 outranks every tier-3, regardless
 *      of confidence and TTL.
 *   2. Lower confidence → higher score within a tier.
 *   3. Less time-to-timeout → higher score within a tier+confidence.
 *
 * Each property pins fast-check arbitraries to a fixed seed so CI is
 * reproducible. The "prop:" prefix lets `pnpm test:property` grep them.
 */
import { describe, expect, it } from "vitest";
import fc from "fast-check";

import { escalationScore, hasCriticalTier4, rankEscalations, timeToTimeoutSeconds } from "./ranker";
import type { Escalation, Tier } from "./escalation";

const NOW = Date.parse("2026-04-30T10:00:00Z");

function buildEscalation(partial: Partial<Escalation> & { tier: Tier; confidence: number }): Escalation {
  return {
    type: "escalation",
    decision_id: "00000000-0000-4000-8000-000000000000",
    proposals: [],
    violations: [],
    issued_at: "2026-04-30T09:59:30Z",
    timeout_seconds: 60,
    ...partial,
  };
}

describe("Mission Control ranker", () => {
  it("tier 4 always outranks tier 3 (categorical dominance)", () => {
    fc.assert(
      fc.property(
        fc.float({ min: 0, max: 1, noNaN: true }),
        fc.float({ min: 0, max: 1, noNaN: true }),
        fc.integer({ min: 1, max: 600 }),
        fc.integer({ min: 1, max: 600 }),
        (c4, c3, ttl4, ttl3) => {
          const t4 = buildEscalation({ tier: "tier_4", confidence: c4, timeout_seconds: ttl4 });
          const t3 = buildEscalation({ tier: "tier_3", confidence: c3, timeout_seconds: ttl3 });
          expect(escalationScore(t4, NOW)).toBeGreaterThan(escalationScore(t3, NOW));
        },
      ),
      { seed: 20260430, numRuns: 200 },
    );
  });

  it("prop: lower confidence ⇒ higher score within tier+TTL", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<Tier>("tier_1", "tier_2", "tier_3", "tier_4"),
        fc.integer({ min: 5, max: 600 }),
        (tier, ttl) => {
          const high = buildEscalation({ tier, confidence: 0.9, timeout_seconds: ttl });
          const low = buildEscalation({ tier, confidence: 0.2, timeout_seconds: ttl });
          expect(escalationScore(low, NOW)).toBeGreaterThan(escalationScore(high, NOW));
        },
      ),
      { seed: 20260430, numRuns: 100 },
    );
  });

  it("prop: less time-to-timeout ⇒ higher score within tier+confidence", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<Tier>("tier_1", "tier_2", "tier_3", "tier_4"),
        fc.float({ min: 0, max: 1, noNaN: true }),
        (tier, conf) => {
          const fresh = buildEscalation({ tier, confidence: conf, timeout_seconds: 600 });
          const stale = buildEscalation({ tier, confidence: conf, timeout_seconds: 5 });
          expect(escalationScore(stale, NOW)).toBeGreaterThan(escalationScore(fresh, NOW));
        },
      ),
      { seed: 20260430, numRuns: 100 },
    );
  });

  it("rankEscalations returns a permutation (no drops, no dupes)", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            tier: fc.constantFrom<Tier>("tier_1", "tier_2", "tier_3", "tier_4"),
            confidence: fc.float({ min: 0, max: 1, noNaN: true }),
            timeout_seconds: fc.integer({ min: 1, max: 600 }),
            decision_id: fc.uuid(),
          }),
          { maxLength: 25 },
        ),
        (entries) => {
          const escalations = entries.map((e) =>
            buildEscalation({ ...e, decision_id: e.decision_id }),
          );
          const ranked = rankEscalations(escalations, NOW);
          expect(ranked).toHaveLength(escalations.length);
          expect(new Set(ranked.map((e) => e.decision_id))).toEqual(
            new Set(escalations.map((e) => e.decision_id)),
          );
        },
      ),
      { seed: 20260430, numRuns: 100 },
    );
  });

  it("hasCriticalTier4 fires below 30s and not above", () => {
    const above = buildEscalation({ tier: "tier_4", confidence: 0.4, timeout_seconds: 60 });
    const below = buildEscalation({ tier: "tier_4", confidence: 0.4, timeout_seconds: 25 });
    expect(hasCriticalTier4([above], NOW)).toBe(false);
    expect(hasCriticalTier4([below], NOW)).toBe(true);
  });

  it("timeToTimeoutSeconds clamps at zero past expiry", () => {
    const expired = buildEscalation({
      tier: "tier_3",
      confidence: 0.5,
      issued_at: "2026-04-30T09:55:00Z",
      timeout_seconds: 60,
    });
    expect(timeToTimeoutSeconds(expired, NOW)).toBe(0);
  });
});
