import { reshapeDecision } from "@hooks/use-decision";
import type { DecisionDetailResponse } from "@transport/synapse-api";
import { describe, expect, it } from "vitest";

// reshapeDecision is the shared, pure boundary between the decision-detail
// envelope and the strict ConsensusDecision that the analyst scrubber and the
// Council Theater choreography both consume (FE-INV-002). It must default the
// anatomy fields honestly and reject an invalid envelope rather than render it.

function buildRaw(overrides: Partial<DecisionDetailResponse> = {}): DecisionDetailResponse {
  return {
    audit_id: "aud-1",
    decision_id: "11111111-1111-4111-8111-111111111111",
    tier: "tier_3",
    phase_reached: 5,
    confidence: 0.82,
    escalated: false,
    created_at: "2026-06-16T10:00:00.000Z",
    proposals: [{ agent_name: "demand_prophet", utility_score: 0.8, confidence: 0.9 }],
    selected_action: { qty: 10 },
    pareto_weights: { cost: 1 },
    audit_trace: ["t1: collected"],
    debate_rounds: 2,
    pareto_front: [{ cost: 0.5 }],
    context_messages: [{ agent_name: "demand_prophet", content: "hi" }],
    execution_confirmations: ["ok"],
    ...overrides,
  } as DecisionDetailResponse;
}

describe("reshapeDecision", () => {
  it("maps the envelope into a validated ConsensusDecision + passes the raw through", () => {
    const raw = buildRaw();
    const { decision, raw: passedRaw } = reshapeDecision(raw, "fallback-id");
    expect(decision.decision_id).toBe("11111111-1111-4111-8111-111111111111");
    expect(decision.tier).toBe("tier_3");
    expect(decision.confidence).toBe(0.82);
    expect(decision.debate_rounds).toBe(2);
    expect(decision.timestamp).toBe("2026-06-16T10:00:00.000Z");
    expect(passedRaw).toBe(raw);
  });

  it("uses the fallback id when the envelope omits decision_id", () => {
    const raw = buildRaw({ decision_id: undefined as unknown as string });
    const { decision } = reshapeDecision(raw, "22222222-2222-4222-8222-222222222222");
    expect(decision.decision_id).toBe("22222222-2222-4222-8222-222222222222");
  });

  it("defaults the anatomy honestly when the envelope omits it", () => {
    const raw = buildRaw({
      debate_rounds: undefined,
      pareto_front: undefined,
      context_messages: undefined,
      execution_confirmations: undefined,
      escalated: true,
    });
    const { decision } = reshapeDecision(raw, "fallback-id");
    expect(decision.debate_rounds).toBe(0);
    expect(decision.pareto_front).toBeNull();
    expect(decision.context_messages).toEqual([]);
    expect(decision.execution_confirmations).toEqual([]);
    expect(decision.escalated_to_human).toBe(true);
  });

  it("throws a schema violation rather than returning an invalid decision", () => {
    const raw = buildRaw({ confidence: 9 });
    expect(() => reshapeDecision(raw, "fallback-id")).toThrow(/schema violation/);
  });
});
