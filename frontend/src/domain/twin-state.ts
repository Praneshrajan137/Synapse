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
