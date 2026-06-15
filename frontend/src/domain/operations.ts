import { z } from "zod";

/**
 * Operations / Standing Watch contracts (Sprint 17, ADR-046).
 *
 * Mirror the additive supervisory endpoints:
 *   - GET /api/v1/system/slo          (api/routers/system.py)
 *   - GET /api/v1/system/calibration  (api/routers/system.py)
 *   - GET /api/v1/escalations/analytics (api/routers/escalations.py)
 *
 * Every "could be missing" number is `.nullable()` — a null window/Brier means
 * "no evidence", which the UI renders as "unknown", NEVER as a healthy 0
 * (FE-INV-042/043). Schemas are `.passthrough()` so a forward-compatible
 * gateway adding fields never breaks the client (additive contract, FE-INV-002).
 */

// ─── SLO burn ──────────────────────────────────────────────────────────────
export const SloSeverity = z.enum(["ok", "warning", "critical", "unknown"]);
export type SloSeverity = z.infer<typeof SloSeverity>;

const SloWindowSchema = z
  .object({
    window: z.string(),
    error_rate: z.number().nullable(),
    burn_rate: z.number().nullable(),
  })
  .passthrough();

const SloTierSchema = z
  .object({
    objective: z.number(),
    latency_target_s: z.number(),
    windows: z.object({ fast: SloWindowSchema, slow: SloWindowSchema }),
    budget_remaining_30d: z.number().nullable(),
    severity: SloSeverity,
  })
  .passthrough();

export const SloResponseSchema = z
  .object({
    tiers: z.record(SloTierSchema),
    ts: z.number(),
    source: z.enum(["prometheus", "unknown"]),
  })
  .passthrough();
export type SloResponse = z.infer<typeof SloResponseSchema>;
export type SloTier = z.infer<typeof SloTierSchema>;

// ─── Calibration ─────────────────────────────────────────────────────────────
export const CalibrationBinSchema = z
  .object({
    lo: z.number(),
    hi: z.number(),
    n: z.number().int().min(0),
    mean_confidence: z.number().nullable(),
    observed_rate: z.number().nullable(),
  })
  .passthrough();
export type CalibrationBin = z.infer<typeof CalibrationBinSchema>;

export const CalibrationResponseSchema = z
  .object({
    window_hours: z.number().int(),
    include_synthetic: z.boolean(),
    city: z.string().nullable(),
    n_total: z.number().int().min(0),
    n_scored: z.number().int().min(0),
    n_unknown: z.number().int().min(0),
    brier_score: z.number().nullable(),
    bins: z.array(CalibrationBinSchema),
    as_of: z.string(),
    note: z.string().optional(),
  })
  .passthrough();
export type CalibrationResponse = z.infer<typeof CalibrationResponseSchema>;

// ─── Escalation analytics ────────────────────────────────────────────────────
export const EscalationAnalyticsSchema = z
  .object({
    window_hours: z.number().int(),
    city: z.string().nullable(),
    total: z.number().int().min(0),
    overridden: z.number().int().min(0),
    pending: z.number().int().min(0),
    override_actions: z.object({
      approved: z.number().int().min(0),
      rejected: z.number().int().min(0),
      modified: z.number().int().min(0),
      none: z.number().int().min(0),
    }),
    resolution_time_ms: z.object({
      p50: z.number().nullable(),
      p90: z.number().nullable(),
      max: z.number().nullable(),
    }),
    top_reasons: z.array(z.object({ reason: z.string(), count: z.number().int() })),
    ts: z.number(),
  })
  .passthrough();
export type EscalationAnalytics = z.infer<typeof EscalationAnalyticsSchema>;
