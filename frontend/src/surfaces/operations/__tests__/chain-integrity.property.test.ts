import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { chainIntegrity, type ChainIntegrity } from "../logic";

// Feature: atlas-console-elevation
// Property 19: Audit-chain integrity is an exhaustive tri-state
//
// `chainIntegrity(chain_verified)` maps every possible backend value to
// EXACTLY one of three distinct states:
//   true            → "verified"    (single-row hash recompute matches)
//   false           → "altered"     (row content changed since insert — tamper)
//   null/undefined  → "pre-chain"   (pre-Sprint-9 legacy row, no chain values)
//
// A legacy (null/undefined) row is NEVER "verified" — absence of a chain is not
// proof of integrity.
//
// **Validates: Requirements 4.10**

const TRI_STATE: ReadonlyArray<ChainIntegrity> = ["verified", "altered", "pre-chain"];

describe("Property 19: audit-chain integrity is an exhaustive tri-state", () => {
  it("maps every possible chain_verified value to exactly one of the three states", () => {
    const arbChainVerified = fc.constantFrom<Array<boolean | null | undefined>>(
      true,
      false,
      null,
      undefined,
    );
    fc.assert(
      fc.property(arbChainVerified, (chainVerified) => {
        const result = chainIntegrity(chainVerified);
        // The result is always a member of the closed tri-state set.
        expect(TRI_STATE).toContain(result);
        // Exactly one bucket matches (the states are mutually exclusive words).
        expect(TRI_STATE.filter((s) => s === result)).toHaveLength(1);
      }),
      { numRuns: 200 },
    );
  });

  it("maps true→verified, false→altered, and null/undefined→pre-chain", () => {
    const arbNullish = fc.constantFrom<Array<null | undefined>>(null, undefined);
    fc.assert(
      fc.property(fc.boolean(), arbNullish, (b, nullish) => {
        expect(chainIntegrity(b)).toBe(b ? "verified" : "altered");
        expect(chainIntegrity(nullish)).toBe("pre-chain");
      }),
      { numRuns: 200 },
    );
  });

  it("never maps a legacy (null/undefined) chain to verified", () => {
    const arbNullish = fc.constantFrom<Array<null | undefined>>(null, undefined);
    fc.assert(
      fc.property(arbNullish, (nullish) => {
        expect(chainIntegrity(nullish)).not.toBe("verified");
      }),
      { numRuns: 100 },
    );
  });
});
