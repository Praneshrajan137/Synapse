import { DecisionEnvelopeSchema } from "@domain/decision-envelope";
import { describe, expect, it } from "vitest";

// The decision channel's wire contract (ADR-044): the lean outbox payload
// from orchestrator/audit/logger.py. The previous strict ConsensusDecision
// schema silently rejected every live envelope — these tests pin the schema
// to what ACTUALLY flows so the live tail can never go quietly dark again.

const OUTBOX_PAYLOAD = {
  decision_id: "11111111-1111-4111-8111-111111111111",
  tier: "tier_2",
  confidence: 0.87,
  phase_reached: 4,
  escalated: false,
  selected_action: { action: "restock", sku_id: "SKU001" },
  timestamp: "2026-06-11T10:00:00+00:00",
  degraded: true,
  is_synthetic: false,
  agents: [{ agent_name: "demand_prophet", confidence: 0.87, degraded: true }],
};

describe("DecisionEnvelopeSchema — the lean live envelope (ADR-044)", () => {
  it("accepts the exact outbox payload shape", () => {
    const parsed = DecisionEnvelopeSchema.safeParse(OUTBOX_PAYLOAD);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.degraded).toBe(true);
      expect(parsed.data.agents[0]?.agent_name).toBe("demand_prophet");
    }
  });

  it("accepts a pre-ADR-044 envelope (no honesty fields) with safe defaults", () => {
    const legacy = {
      decision_id: "11111111-1111-4111-8111-111111111111",
      tier: "tier_1",
      confidence: 0.92,
      phase_reached: 4,
      escalated: true,
      selected_action: {},
    };
    const parsed = DecisionEnvelopeSchema.safeParse(legacy);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.degraded).toBe(false);
      expect(parsed.data.is_synthetic).toBe(false);
      // ADR-053: a pre-053 envelope with no initiator defaults to operator —
      // a real human decision, never fabricated autonomy.
      expect(parsed.data.initiator).toBe("operator");
      expect(parsed.data.agents).toEqual([]);
      expect(parsed.data.timestamp).toBeUndefined();
    }
  });

  it("carries an autonomous initiator when the SensorLoop self-initiated (ADR-053)", () => {
    const parsed = DecisionEnvelopeSchema.safeParse({
      ...OUTBOX_PAYLOAD,
      initiator: "autonomous",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.initiator).toBe("autonomous");
      // Autonomous is NOT synthetic — the load-bearing honesty guarantee.
      expect(parsed.data.is_synthetic).toBe(false);
    }
  });

  it("rejects an unknown initiator value", () => {
    expect(
      DecisionEnvelopeSchema.safeParse({ ...OUTBOX_PAYLOAD, initiator: "robot" }).success,
    ).toBe(false);
  });

  it("tolerates future additive keys (the ADR-044 contract is additive)", () => {
    const parsed = DecisionEnvelopeSchema.safeParse({
      ...OUTBOX_PAYLOAD,
      some_future_field: { anything: true },
    });
    expect(parsed.success).toBe(true);
  });

  it("rejects a non-decision payload", () => {
    expect(DecisionEnvelopeSchema.safeParse({ hello: "world" }).success).toBe(false);
    expect(DecisionEnvelopeSchema.safeParse({ ...OUTBOX_PAYLOAD, confidence: 7 }).success).toBe(
      false,
    );
    expect(DecisionEnvelopeSchema.safeParse({ ...OUTBOX_PAYLOAD, tier: "tier_9" }).success).toBe(
      false,
    );
  });
});
