/**
 * SYNAPSE Atlas Console — Living City KPI domain.
 *
 * The KPI band reads the `synapse.metrics.agent` SSE topic (or any
 * future Prometheus push) and reduces a sliding window to the five
 * tiles in plan §5.1. We keep the reducer pure so property tests can
 * pin invariants (no NaN, monotone smoothing, window pruning).
 */
import { z } from "zod";

export const KPISchema = z.object({
  orders_min: z.number().nullable().default(null),
  avg_delivery_min: z.number().nullable().default(null),
  fill_rate: z.number().min(0).max(1).nullable().default(null),
  waste_rate: z.number().min(0).max(1).nullable().default(null),
  carbon_per_delivery: z.number().nullable().default(null),
});
export type KPI = z.infer<typeof KPISchema>;

export const EMPTY_KPI: KPI = {
  orders_min: null,
  avg_delivery_min: null,
  fill_rate: null,
  waste_rate: null,
  carbon_per_delivery: null,
};

/**
 * `synapse.metrics.agent` payload shape (loose). Each frame is a single
 * agent's reward/latency/throughput snapshot. The Living City surface
 * folds these into KPI tiles using a 1-minute sliding window.
 */
export const MetricsFrameSchema = z
  .object({
    agent: z.string().optional(),
    /** Compatible with the recorded fixture set in tests. */
    reward: z.number().optional(),
    latency_ms: z.number().nonnegative().optional(),
    throughput: z.number().nonnegative().optional(),
    ts: z.string().datetime({ offset: true }).optional(),
    /** Free-form per-tile overrides — backend can short-circuit the reducer. */
    tile_overrides: z
      .object({
        orders_min: z.number().optional(),
        avg_delivery_min: z.number().optional(),
        fill_rate: z.number().min(0).max(1).optional(),
        waste_rate: z.number().min(0).max(1).optional(),
        carbon_per_delivery: z.number().optional(),
      })
      .optional(),
  })
  .passthrough();
export type MetricsFrame = z.infer<typeof MetricsFrameSchema>;

/**
 * Reduce a sliding window of metrics frames into the 5-tile KPI shape.
 * Window pruning is the caller's responsibility; this function is a
 * pure folder over whatever set you hand it.
 */
export function reduceKPI(frames: readonly MetricsFrame[]): KPI {
  if (frames.length === 0) return EMPTY_KPI;
  const tiles: KPI = { ...EMPTY_KPI };
  let latestOverride: KPI = { ...EMPTY_KPI };
  let throughputSum = 0;
  let throughputCount = 0;
  let latencySum = 0;
  let latencyCount = 0;

  for (const f of frames) {
    if (f.tile_overrides) {
      // Latest wins — the reducer respects authoritative server-emitted tiles.
      latestOverride = { ...latestOverride, ...f.tile_overrides };
    }
    if (typeof f.throughput === "number") {
      throughputSum += f.throughput;
      throughputCount += 1;
    }
    if (typeof f.latency_ms === "number") {
      latencySum += f.latency_ms;
      latencyCount += 1;
    }
  }

  if (throughputCount > 0) {
    tiles.orders_min = throughputSum / throughputCount;
  }
  if (latencyCount > 0) {
    // latency_ms → minutes for the operator-friendly tile.
    tiles.avg_delivery_min = latencySum / latencyCount / 1000 / 60;
  }
  return mergeKPI(tiles, latestOverride);
}

function mergeKPI(base: KPI, override: KPI): KPI {
  return {
    orders_min: override.orders_min ?? base.orders_min,
    avg_delivery_min: override.avg_delivery_min ?? base.avg_delivery_min,
    fill_rate: override.fill_rate ?? base.fill_rate,
    waste_rate: override.waste_rate ?? base.waste_rate,
    carbon_per_delivery: override.carbon_per_delivery ?? base.carbon_per_delivery,
  };
}
