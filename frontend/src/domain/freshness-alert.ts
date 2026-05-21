import { z } from "zod";
import { ZConfidence, ZIsoTimestamp, ZUuid } from "./primitives";

// Mirror of proto/domain/freshness_alert.schema.json (Freshness Guardian).

export const FreshnessAlertSchema = z
  .object({
    alert_id: ZUuid,
    store_id: z.string(),
    sku_id: z.string(),
    days_to_expiry: z.number().min(0),
    quality_score: ZConfidence,
    markdown_applied: z.boolean(),
    markdown_pct: z.number().min(0).max(100),
    temperature_deviation_hours: z.number().min(0).optional(),
    rebalance_recommended: z.boolean().optional(),
    target_store_id: z.string().nullable().optional(),
    fssai_compliant: z.boolean(),
    timestamp: ZIsoTimestamp,
    confidence: ZConfidence,
  })
  .strict();

export type FreshnessAlert = z.infer<typeof FreshnessAlertSchema>;
