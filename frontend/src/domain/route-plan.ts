import { z } from "zod";
import { ZUuid } from "./primitives";

// Mirror of proto/domain/route_plan.schema.json (Routing Navigator).

export const RouteStopSchema = z
  .object({
    stop_id: z.string().optional(),
    sequence: z.number().int().min(0).optional(),
    lat: z.number().optional(),
    lon: z.number().optional(),
    eta_min: z.number().min(0).optional(),
    order_id: z.string().optional(),
  })
  .passthrough();

export const RoutePlanSchema = z
  .object({
    route_id: ZUuid,
    rider_id: z.string(),
    store_id: z.string(),
    stops: z.array(RouteStopSchema).min(1),
    total_distance_km: z.number().min(0),
    total_time_min: z.number().min(0),
    fuel_estimate_liters: z.number().min(0).optional(),
    freshness_violations: z.number().int().min(0).optional(),
  })
  .passthrough();

export type RouteStop = z.infer<typeof RouteStopSchema>;
export type RoutePlan = z.infer<typeof RoutePlanSchema>;
