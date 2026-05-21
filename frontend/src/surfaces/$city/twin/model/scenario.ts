/**
 * SYNAPSE Atlas Console — Twin Studio scenario model.
 *
 * Mirrors the orchestrator's `POST /simulate` request + the
 * `WhatIfResult` shape (proto/domain/twin_state.schema.json). Zod-typed
 * so the form, the URL search-params, and the saved scenario library
 * share one schema.
 */
import { z } from "zod";

export const ScenarioInputSchema = z.object({
  demand_multiplier: z.coerce.number().min(0).max(10).default(1),
  lead_time_multiplier: z.coerce.number().min(0).max(10).default(1),
  failure_rate_multiplier: z.coerce.number().min(0).max(10).default(1),
  spoilage_rate_multiplier: z.coerce.number().min(0).max(10).default(1),
  n_scenarios: z.coerce.number().int().min(1).max(10_000).default(1_000),
  duration_hours: z.coerce.number().min(0.25).max(168).default(4),
});
export type ScenarioInput = z.infer<typeof ScenarioInputSchema>;

export const SimulateRequestSchema = ScenarioInputSchema.extend({
  name: z.string().min(1).max(200).optional(),
  description: z.string().max(2000).optional(),
});
export type SimulateRequest = z.infer<typeof SimulateRequestSchema>;

/**
 * Per-percentile time series — the fan-out viz consumes (p10, p50, p90).
 * The orchestrator returns each as `[{t, value}, …]`. We accept both an
 * array of objects and `{x, y}` pairs to absorb wire variations.
 */
const PercentilePointSchema = z.object({
  t: z.number(),
  value: z.number(),
});

export const WhatIfResultSchema = z
  .object({
    scenario_id: z.string().optional(),
    n_scenarios: z.number().int().nonnegative(),
    duration_hours: z.number().nonnegative(),
    /** Percentile bands keyed `p10`,`p50`,`p90`; orchestrator may add more. */
    percentiles: z.record(z.string(), z.array(PercentilePointSchema)),
    /** KL divergence sparkline against the live distribution (I-12). */
    kl_divergence: z.array(z.object({ t: z.number(), value: z.number() })),
    /** Difference vs the actual outcome at decision time. */
    counterfactual: z
      .object({
        revenue_delta: z.number().optional(),
        fill_rate_delta: z.number().optional(),
        co2_delta: z.number().optional(),
        details: z.record(z.string(), z.unknown()).optional(),
      })
      .optional(),
    duration_ms: z.number().int().nonnegative().optional(),
  })
  .passthrough();
export type WhatIfResult = z.infer<typeof WhatIfResultSchema>;

/** Saved scenario in the library (Zustand + IDB). */
export const SavedScenarioSchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1).max(120),
  createdAt: z.string().datetime({ offset: true }),
  input: ScenarioInputSchema,
});
export type SavedScenario = z.infer<typeof SavedScenarioSchema>;

/** I-12 KL-divergence threshold beyond which the twin is "drifting". */
export const KL_DIVERGENCE_THRESHOLD = 0.1;
