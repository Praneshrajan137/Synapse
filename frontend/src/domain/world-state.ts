import { z } from "zod";

/**
 * A per-city standing world snapshot — the "perceive" phase of the autonomous
 * loop (ADR-052/053). Mirrors `proto/domain/world_state.schema.json` and
 * `packages/synapse_common/world/models.py::WorldState`.
 *
 * Two honesty invariants the UI must never soften:
 *   is_synthetic    — ALWAYS true; the world is a simulation. Label it, never
 *                     imply it is live commerce.
 *   clock_advancing — false ⇒ the sim clock has stalled = the world is
 *                     DEGRADED (I-7). Render degraded, never healthy.
 *
 * `.passthrough()` so additive backend fields never reject the snapshot.
 */
export const WorldStateSchema = z
  .object({
    city: z.string(),
    sim_time_min: z.number().min(0),
    // Per-SKU stock level.
    inventory: z.record(z.number()).default({}),
    pending_orders: z.number().int().min(0).default(0),
    fill_rate: z.number().min(0).max(1).default(1),
    spoilage_rate: z.number().min(0).max(1).default(0),
    avg_delivery_min: z.number().min(0).default(0),
    restocks_triggered: z.number().int().min(0).default(0),
    // Poisson lambda, orders/min.
    demand_rate: z.number().min(0).default(0),
    clock_advancing: z.boolean().default(true),
    is_synthetic: z.boolean().default(true),
    as_of: z.string(),
  })
  .passthrough();

export type WorldState = z.infer<typeof WorldStateSchema>;
