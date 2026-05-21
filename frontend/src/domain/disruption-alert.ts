import { z } from "zod";
import { ZConfidence, ZIsoTimestamp, ZUuid } from "./primitives";

// Mirror of proto/domain/disruption_alert.schema.json (Disruption Shield).

const ZAnomalyScores = z
  .object({
    isolation_forest: z.number(),
    lstm_autoencoder: z.number(),
    gnn_structural: z.number(),
    ensemble_weighted: z.number(),
  })
  .strict();

const ZMonteCarloImpact = z
  .object({
    scenarios_run: z.number().int().min(0).optional(),
    expected_kpi_degradation_pct: z.number().optional(),
    p95_degradation_pct: z.number().optional(),
  })
  .strict()
  .optional();

export const DisruptionAlertSchema = z
  .object({
    alert_id: ZUuid,
    alert_level: z.number().int().min(1).max(10),
    anomaly_scores: ZAnomalyScores,
    affected_nodes: z.array(z.string()).min(1),
    disruption_type: z.string().optional(),
    playbook_id: z.string(),
    playbook_actions: z.string().optional(),
    reasoning_chain: z.string(),
    monte_carlo_impact: ZMonteCarloImpact,
    timestamp: ZIsoTimestamp,
    confidence: ZConfidence,
  })
  .strict();

export type DisruptionAlert = z.infer<typeof DisruptionAlertSchema>;
