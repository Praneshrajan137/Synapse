import {
  ConsensusDecisionSchema,
  DemandForecastSchema,
  EscalationMessageSchema,
  OverrideResponseSchema,
  PricingDecisionSchema,
  PricingUpdateSchema,
  RoutePlanSchema,
} from "@domain/index";
import { describe, expect, it } from "vitest";

// FE-INV-002 — every domain Zod mirror parses valid samples and rejects
// samples that violate the canonical JSON-schema constraints.

describe("domain Zod schemas mirror proto/domain", () => {
  it("DemandForecast accepts a valid sample", () => {
    const result = DemandForecastSchema.safeParse({
      sku_id: "sku-001",
      store_id: "store-001",
      forecast_timestamp: "2026-05-18T10:00:00.000Z",
      horizons: { "15min": 12, "1h": 48 },
      lower_90: { "15min": 8 },
      upper_90: { "15min": 16 },
      confidence: 0.87,
      drift_detected: false,
    });
    expect(result.success).toBe(true);
  });

  it("DemandForecast rejects confidence > 1", () => {
    const result = DemandForecastSchema.safeParse({
      sku_id: "sku-001",
      store_id: "store-001",
      forecast_timestamp: "2026-05-18T10:00:00.000Z",
      horizons: {},
      lower_90: {},
      upper_90: {},
      confidence: 1.4,
      drift_detected: false,
    });
    expect(result.success).toBe(false);
  });

  it("PricingDecision enforces essential cap (1.3x) per I-6", () => {
    const valid = PricingDecisionSchema.safeParse({
      sku_id: "rice-5kg",
      store_id: "store-001",
      category_id: "essentials",
      is_essential: true,
      base_price: 250,
      multiplier: 1.25,
      final_price: 312.5,
    });
    expect(valid.success).toBe(true);

    const violation = PricingDecisionSchema.safeParse({
      sku_id: "rice-5kg",
      store_id: "store-001",
      category_id: "essentials",
      is_essential: true,
      base_price: 250,
      multiplier: 1.5,
      final_price: 375,
    });
    expect(violation.success).toBe(false);
  });

  it("PricingUpdate inherits the same essential-cap guardrail", () => {
    const result = PricingUpdateSchema.safeParse({
      pricing_id: "11111111-1111-4111-8111-111111111111",
      sku_id: "sku-essential",
      category: "essentials",
      base_price: 100,
      multiplier: 1.5,
      final_price: 150,
      is_essential: true,
      elasticity_source: "manual",
      timestamp: "2026-05-18T10:00:00.000Z",
      confidence: 0.9,
    });
    expect(result.success).toBe(false);
  });

  it("RoutePlan requires at least one stop", () => {
    const result = RoutePlanSchema.safeParse({
      route_id: "11111111-1111-4111-8111-111111111111",
      rider_id: "rider-001",
      store_id: "store-001",
      stops: [],
      total_distance_km: 0,
      total_time_min: 0,
    });
    expect(result.success).toBe(false);
  });

  it("ConsensusDecision applies defaults for context_messages / debate_rounds", () => {
    const result = ConsensusDecisionSchema.safeParse({
      decision_id: "11111111-1111-4111-8111-111111111111",
      timestamp: "2026-05-18T10:00:00.000Z",
      tier: "tier_2",
      proposals: [],
      selected_action: {},
      pareto_weights: {},
      confidence: 0.82,
      audit_trace: ["ok"],
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.debate_rounds).toBe(0);
      expect(result.data.context_messages).toEqual([]);
    }
  });

  it("EscalationMessage requires type=escalation", () => {
    const wrong = EscalationMessageSchema.safeParse({
      type: "other",
      decision_id: "11111111-1111-4111-8111-111111111111",
      confidence: 0.5,
    });
    expect(wrong.success).toBe(false);
  });

  it("OverrideResponse constrains action enum", () => {
    const ok = OverrideResponseSchema.safeParse({
      decision_id: "11111111-1111-4111-8111-111111111111",
      response: { action: "approved" },
    });
    expect(ok.success).toBe(true);

    const wrong = OverrideResponseSchema.safeParse({
      decision_id: "11111111-1111-4111-8111-111111111111",
      response: { action: "noop" },
    });
    expect(wrong.success).toBe(false);
  });
});
