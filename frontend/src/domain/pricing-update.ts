import { z } from "zod";
import { ZConfidence, ZIsoTimestamp, ZUuid } from "./primitives";

// Mirror of proto/domain/pricing_update.schema.json (Pricing Oracle).
// Note: the underlying proto/domain/pricing_decision.schema.json carries a
// JSON-Schema `if/then` enforcing multiplier ≤ 1.3 for essential SKUs (I-6
// hard guardrail). We replicate that here with a Zod refinement.

export const PricingUpdateSchema = z
  .object({
    pricing_id: ZUuid,
    sku_id: z.string(),
    store_id: z.string().optional(),
    category: z.string(),
    base_price: z.number().min(0),
    multiplier: z.number().min(0.5).max(2.0),
    final_price: z.number().min(0),
    is_essential: z.boolean(),
    elasticity_source: z.enum(["causal_doubleml", "correlation_fallback", "manual"]),
    causal_elasticity: z.number().nullable().optional(),
    competitor_delta_pct: z.number().nullable().optional(),
    demand_forecast_impact: z.number().nullable().optional(),
    essential_cap_enforced: z.boolean().optional(),
    timestamp: ZIsoTimestamp,
    confidence: ZConfidence,
    audit_id: ZUuid.optional(),
  })
  .strict()
  .refine((v) => !v.is_essential || v.multiplier <= 1.3, {
    message: "Essential SKU multiplier exceeds 1.3 cap (I-6 hard guardrail)",
    path: ["multiplier"],
  });

export type PricingUpdate = z.infer<typeof PricingUpdateSchema>;
