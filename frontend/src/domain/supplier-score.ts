import { z } from "zod";
import { ZConfidence, ZIsoTimestamp, ZUuid } from "./primitives";

// Mirror of proto/domain/supplier_score.schema.json (Supplier Trust).

const ZLeadTimePosterior = z
  .object({
    mean_days: z.number().min(0),
    std_days: z.number().min(0),
    p10_days: z.number().optional(),
    p90_days: z.number().optional(),
  })
  .passthrough();

export const SupplierScoreSchema = z
  .object({
    score_id: ZUuid,
    supplier_id: z.string(),
    trust_score: ZConfidence,
    trust_floor_applied: z.boolean().optional(),
    lead_time_posterior: ZLeadTimePosterior,
    delivery_reliability: ZConfidence,
    quality_score: ZConfidence.optional(),
    geopolitical_risk: ZConfidence.optional(),
    last_delivery_ts: ZIsoTimestamp.nullable().optional(),
    timestamp: ZIsoTimestamp,
    confidence: ZConfidence,
  })
  .passthrough();

export type SupplierScore = z.infer<typeof SupplierScoreSchema>;
