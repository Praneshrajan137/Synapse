import { describe, expect, it } from "vitest";
import { confidenceBand, isBelowThreshold, TIER_SLA_MS } from "../confidence";

// FE-INV-005 — tier SLAs encoded centrally so UX motion preset can read them.
describe("confidence helpers", () => {
  it("bands confidence into ok / warn / risk", () => {
    expect(confidenceBand(0.95)).toBe("ok");
    expect(confidenceBand(0.9)).toBe("ok");
    expect(confidenceBand(0.89)).toBe("warn");
    expect(confidenceBand(0.7)).toBe("warn");
    expect(confidenceBand(0.69)).toBe("risk");
    expect(confidenceBand(0)).toBe("risk");
  });

  it("isBelowThreshold respects default 0.7", () => {
    expect(isBelowThreshold(0.7)).toBe(false);
    expect(isBelowThreshold(0.69)).toBe(true);
  });

  it("exposes tier SLAs anchored to tier_router.py", () => {
    expect(TIER_SLA_MS.tier_1).toBe(100);
    expect(TIER_SLA_MS.tier_2).toBe(500);
    expect(TIER_SLA_MS.tier_3).toBe(15_000);
    expect(TIER_SLA_MS.tier_4).toBe(120_000);
  });
});
