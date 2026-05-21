import { z } from "zod";
import { ZConfidence, ZIsoTimestamp, ZUuid } from "./primitives";

// Mirror of proto/domain/carbon_report.schema.json (Sustainability Agent).

const ZWastePrediction = z
  .object({
    predicted_waste_kg: z.number(),
    survival_probability: ZConfidence.optional(),
    recommended_action: z.string().optional(),
  })
  .strict()
  .optional();

export const CarbonReportSchema = z
  .object({
    report_id: ZUuid,
    scope: z.enum(["route", "store", "agent_compute", "aggregate"]),
    entity_id: z.string().optional(),
    co2_kg: z.number().min(0),
    energy_kwh: z.number().min(0),
    waste_prediction: ZWastePrediction,
    pareto_weight: z.number().min(0).max(1).optional(),
    timestamp: ZIsoTimestamp,
  })
  .strict();

export type CarbonReport = z.infer<typeof CarbonReportSchema>;
