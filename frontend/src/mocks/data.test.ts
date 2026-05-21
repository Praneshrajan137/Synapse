import { describe, expect, it } from "vitest";
import { makeDecision, makeEscalations, makeKpis, makeRecentDecisions } from "./data";

describe("mock data", () => {
  it("is deterministic — the same id yields the same decision (tenet T-1)", () => {
    const a = makeDecision("dec-fixed-001");
    const b = makeDecision("dec-fixed-001");
    expect(a).toEqual(b);
  });

  it("produces a coherent decision aggregate", () => {
    const d = makeDecision("dec-coherent");
    expect(d.proposals.length).toBeGreaterThan(0);
    expect(d.contextMessages.length).toBeGreaterThan(0);
    expect(d.confidence).toBeGreaterThanOrEqual(0);
    expect(d.confidence).toBeLessThanOrEqual(1);
    expect(["tier_1", "tier_2", "tier_3", "tier_4"]).toContain(d.tier);
  });

  it("context messages carry a monotonic, gapless sequence (append-only, I-14)", () => {
    const d = makeDecision("dec-seq");
    d.contextMessages.forEach((message, index) => {
      expect(message.sequence).toBe(index);
    });
  });

  it("escalations always carry at least one violation", () => {
    for (const escalation of makeEscalations()) {
      expect(escalation.violations.length).toBeGreaterThan(0);
      expect(escalation.decision.escalated).toBe(true);
    }
  });

  it("recent decisions are returned newest-first", () => {
    const recent = makeRecentDecisions(10);
    for (let i = 1; i < recent.length; i += 1) {
      expect(recent[i - 1]?.createdAt).toBeGreaterThanOrEqual(recent[i]?.createdAt ?? 0);
    }
  });

  it("exposes the six Bridge KPIs", () => {
    expect(makeKpis()).toHaveLength(6);
  });
});
