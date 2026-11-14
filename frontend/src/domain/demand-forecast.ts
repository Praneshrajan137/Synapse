import { z } from "zod";
import { ZConfidence, ZIsoTimestamp } from "./primitives";

// Mirror of proto/domain/demand_forecast.schema.json (Demand Prophet output).
// Conformal 90% interval per ADR-009 / MAPIE.

const ZHorizonMap = z
  .object({
    "15min": z.number().min(0).optional(),
    "1h": z.number().min(0).optional(),
    "6h": z.number().min(0).optional(),
    "24h": z.number().min(0).optional(),
    "7d": z.number().min(0).optional(),
  })
  .passthrough();

export const DemandForecastSchema = z
  .object({
    sku_id: z.string(),
    store_id: z.string(),
    forecast_timestamp: ZIsoTimestamp,
    horizons: ZHorizonMap,
    // zod 4: z.record() takes an explicit key schema; an enum key would be exhaustive.
    lower_90: z.record(z.string(), z.number()),
    upper_90: z.record(z.string(), z.number()),
    confidence: ZConfidence,
    drift_detected: z.boolean(),
  })
  .passthrough();

export type DemandForecast = z.infer<typeof DemandForecastSchema>;
