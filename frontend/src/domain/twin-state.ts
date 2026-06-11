import { z } from "zod";
import { ZIsoTimestamp, ZSyncStatus, ZUuid } from "./primitives";

// Mirror of proto/domain/twin_state.schema.json (Digital Twin).

const ZNodeCounts = z
  .object({
    dark_stores: z.number().int().min(0).optional(),
    warehouses: z.number().int().min(0).optional(),
    suppliers: z.number().int().min(0).optional(),
    skus: z.number().int().min(0).optional(),
    riders: z.number().int().min(0).optional(),
  })
  .strict();

const ZSimulationMetrics = z
  .object({
    avg_delivery_time_min: z.number().optional(),
    fill_rate: z.number().optional(),
    waste_rate: z.number().optional(),
    orders_per_hour: z.number().optional(),
  })
  .strict()
  .optional();

export const TwinStateSchema = z
  .object({
    snapshot_id: ZUuid,
    timestamp: ZIsoTimestamp,
    kl_divergence: z.number().min(0),
    sync_status: ZSyncStatus,
    node_counts: ZNodeCounts.optional(),
    simulation_metrics: ZSimulationMetrics,
  })
  .strict();

export type TwinState = z.infer<typeof TwinStateSchema>;

/**
 * The divergence ALERT the DivergenceMonitor actually publishes to
 * `synapse.twin.divergence` (digital_twin/sync/divergence_monitor.py):
 * fired when KL(twin ‖ live) crosses the re-sync threshold. NOT the same
 * shape as a TwinState snapshot — the firehose `twin` channel previously
 * validated alerts against TwinStateSchema and silently rejected every one.
 */
export const DivergenceAlertSchema = z
  .object({
    agent_name: z.string(),
    kl_divergence: z.number().min(0),
    threshold: z.number().optional(),
    // Unix seconds (float) from time.time() — not ISO.
    timestamp: z.number().optional(),
    action: z.string().optional(),
  })
  .passthrough();

export type DivergenceAlert = z.infer<typeof DivergenceAlertSchema>;

/**
 * What flows on the firehose `twin` channel: divergence alerts (the only
 * producer today) or full snapshots (the What-If simulate path re-uses the
 * buffer). Both carry `kl_divergence` — the field every consumer reads.
 */
export const TwinDivergenceEventSchema = z.union([TwinStateSchema, DivergenceAlertSchema]);
export type TwinDivergenceEvent = z.infer<typeof TwinDivergenceEventSchema>;
