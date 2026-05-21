import { z } from "zod";

// Mirror of proto/domain/pricing_decision.schema.json (internal Pricing Oracle decision).
// JSON-Schema if/then for essential SKUs: multiplier ≤ 1.3 (I-6 hard guardrail).

export const PricingDecisionSchema = z
  .object({
    sku_id: z.string(),
    store_id: z.string(),
    category_id: z.string(),
    is_essential: z.boolean(),
    base_price: z.number().positive(),
    multiplier: z.number().positive(),
    final_price: z.number().positive(),
  })
  .strict()
  .refine(
    (v) => !v.is_essential || v.multiplier <= 1.3,
    { message: "Essential multiplier exceeds 1.3 cap (I-6)", path: ["multiplier"] },
  );

export type PricingDecision = z.infer<typeof PricingDecisionSchema>;
