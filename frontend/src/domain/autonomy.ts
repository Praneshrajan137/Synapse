import { z } from "zod";
import { WorldStateSchema } from "./world-state";

/**
 * The Autonomy Spine read (ADR-053) — `GET /api/v1/system/autonomy`.
 *
 * Joins the orchestrator SensorLoop's self-initiation record with the twin's
 * live per-city world_state. Honest degradation (I-7):
 *   - `sensor` is null when the orchestrator/sensor is unreachable.
 *   - a world entry is null when that city's world is unreachable/missing.
 *   - `degraded` is true if any part is missing OR a world clock has stalled.
 * A total blackout is a 503 (the hook surfaces it as "autonomy unknown"),
 * distinct from a partial degrade — the UI must not conflate the two.
 */
export const SensorStatusSchema = z
  .object({
    running: z.boolean(),
    cities: z.array(z.string()).default([]),
    poll_interval_s: z.number().optional(),
    reorder_point: z.number().optional(),
    polls: z.number().int().min(0).default(0),
    // The honest headline: "the system has acted on its own N times".
    decisions_triggered: z.number().int().min(0).default(0),
  })
  .passthrough();

export type SensorStatus = z.infer<typeof SensorStatusSchema>;

export const AutonomyResponseSchema = z
  .object({
    sensor: SensorStatusSchema.nullable(),
    // city -> WorldState | null (null = that world unreachable).
    worlds: z.record(WorldStateSchema.nullable()).default({}),
    degraded: z.boolean(),
    as_of: z.string(),
  })
  .passthrough();

export type AutonomyResponse = z.infer<typeof AutonomyResponseSchema>;
