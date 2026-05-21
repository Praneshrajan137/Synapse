import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { replayDecision, phaseName } from "@lib/replay";
import type { ConsensusDecision } from "@domain/consensus-decision";

// FE-INV-009 + FE-INV-028 — replay is referentially transparent (pure).

function fixture(overrides: Partial<ConsensusDecision> = {}): ConsensusDecision {
  return {
    decision_id: "11111111-1111-4111-8111-111111111111",
    timestamp: "2026-05-18T10:00:00.000Z",
    tier: "tier_3",
    proposals: [
      { agent_name: "demand_prophet", status: "proposed", confidence: 0.82, utility_score: 0.71 },
      { agent_name: "routing_navigator", status: "rejected", confidence: 0.6, utility_score: 0.5 },
      { agent_name: "inventory_sentinel", status: "selected", confidence: 0.9, utility_score: 0.85 },
    ],
    selected_action: { action_type: "reorder", agent_name: "inventory_sentinel" },
    pareto_weights: { cost: 0.4, time: 0.3, freshness: 0.3 },
    confidence: 0.86,
    audit_trace: ["proposal", "debate.r1", "debate.r2", "arbitration", "execute.ack", "learning"],
    phase_reached: 5,
    debate_rounds: 2,
    context_messages: [],
    execution_confirmations: ["agent_executor:ok"],
    human_override: null,
    escalated_to_human: false,
    ...overrides,
  };
}

describe("replayDecision", () => {
  it("returns the same slice for the same inputs (referentially transparent)", () => {
    const d = fixture();
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 5 }), (phase) => {
        const a = replayDecision(d, phase);
        const b = replayDecision(d, phase);
        return JSON.stringify(a) === JSON.stringify(b);
      }),
      { numRuns: 50 },
    );
  });

  it("clamps phase index into [1, 5]", () => {
    const d = fixture();
    expect(replayDecision(d, -3).phase).toBe(1);
    expect(replayDecision(d, 0).phase).toBe(1);
    expect(replayDecision(d, 99).phase).toBe(5);
  });

  it("hides debate outcomes at phase 1 and reveals selection at phase 3+", () => {
    const d = fixture();
    const p1 = replayDecision(d, 1);
    expect(p1.selectedAction).toBeNull();
    expect(p1.proposalsVisible.every((p) => (p.status ?? "proposed") === "proposed")).toBe(true);
    const p3 = replayDecision(d, 3);
    expect(p3.selectedAction).not.toBeNull();
  });

  it("audit trace grows monotonically with phase", () => {
    const d = fixture();
    const lengths = [1, 2, 3, 4, 5].map((p) => replayDecision(d, p).auditTraceSoFar.length);
    for (let i = 1; i < lengths.length; i++) {
      expect(lengths[i]).toBeGreaterThanOrEqual(lengths[i - 1]!);
    }
  });

  it("phaseName maps indices to canonical labels", () => {
    expect(phaseName(1)).toBe("proposal");
    expect(phaseName(3)).toBe("arbitration");
    expect(phaseName(5)).toBe("learning");
  });
});
