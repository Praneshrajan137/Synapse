// Feature: atlas-console-elevation, Property 37: Tool visibility is gated by tier consistent with the recorded phase
//
// Property 37 (Validates: Requirements 11.3) — `visibleTools` gates the
// recorded toolset by decision tier (FE-INV-018 / ADR-022):
//   • tiers 1–2 (RL fast path) expose ONLY `rl_*` tools,
//   • tier ≥ FULL_TOOLSET_MIN_TIER exposes the full recorded toolset, and
//   • the result is always a subset of the input in original order — the
//     function never fabricates a tool that was not recorded.

import type { Tier } from "@domain/primitives";
import { FULL_TOOLSET_MIN_TIER, RL_TOOL_PREFIX, tierOrdinal, visibleTools } from "@lib/replay";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

// Tools: a mix of RL-prefixed and non-RL names so both branches see coverage.
const toolArb = fc.oneof(
  fc.string({ minLength: 1 }).map((s) => `${RL_TOOL_PREFIX}${s}`),
  fc.string().filter((s) => !s.startsWith(RL_TOOL_PREFIX)),
);
const toolsArb = fc.array(toolArb, { maxLength: 12 });

// Tiers: the enum form, bare in-range numbers, and out-of-range/garbage numbers
// (tierOrdinal must clamp them into [1, 4]).
const tierArb: fc.Arbitrary<Tier | number> = fc.oneof(
  fc.constantFrom<Tier>("tier_1", "tier_2", "tier_3", "tier_4"),
  fc.integer({ min: -3, max: 8 }),
);

describe("visibleTools — Property 37: tier-gated tool visibility", () => {
  it("never fabricates a tool: the result is always a subset of the input", () => {
    fc.assert(
      fc.property(tierArb, toolsArb, (tier, tools) => {
        const visible = visibleTools(tier, tools);
        for (const t of visible) {
          expect(tools).toContain(t);
        }
        // Never longer than the input.
        expect(visible.length).toBeLessThanOrEqual(tools.length);
      }),
      { numRuns: 200 },
    );
  });

  it("exposes only rl_* tools for tiers 1–2", () => {
    fc.assert(
      fc.property(tierArb, toolsArb, (tier, tools) => {
        fc.pre(tierOrdinal(tier) < FULL_TOOLSET_MIN_TIER);
        const visible = visibleTools(tier, tools);
        expect(visible.every((t) => t.startsWith(RL_TOOL_PREFIX))).toBe(true);
        // Exactly the rl_* subset, in order.
        expect(visible).toStrictEqual(tools.filter((t) => t.startsWith(RL_TOOL_PREFIX)));
      }),
      { numRuns: 200 },
    );
  });

  it("exposes the full recorded toolset for tier ≥ 3", () => {
    fc.assert(
      fc.property(tierArb, toolsArb, (tier, tools) => {
        fc.pre(tierOrdinal(tier) >= FULL_TOOLSET_MIN_TIER);
        expect(visibleTools(tier, tools)).toStrictEqual(tools.slice());
      }),
      { numRuns: 200 },
    );
  });
});
