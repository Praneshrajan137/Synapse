import { z } from "zod";

// Shape of GET /api/v1/agents (api/routers/agents.py:26-42).
// BE returns { agents: { name: status }, count: number }.

export const AGENT_NAMES = [
  "demand_prophet",
  "routing_navigator",
  "inventory_sentinel",
  "freshness_guardian",
  "pricing_oracle",
  "disruption_shield",
  "supplier_trust",
  "sustainability_agent",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];

export const AgentStatusEnum = z.enum(["healthy", "degraded", "unhealthy", "unknown"]);
export type AgentStatus = z.infer<typeof AgentStatusEnum>;

// Pre-P2 shape (status-only). Kept for backwards-compatibility tests.
export const AgentHealthMapSchema = z.record(AgentStatusEnum);

// P2 shape: per-agent metric overlay merged with status probe.
export const AgentMetricsSchema = z
  .object({
    status: z.string(),
    latency_p50_ms: z.number().nullable().optional(),
    latency_p95_ms: z.number().nullable().optional(),
    latency_p99_ms: z.number().nullable().optional(),
    decisions_per_min: z.number().nullable().optional(),
    calibration_coverage_90: z.number().nullable().optional(),
  })
  .passthrough();

export const AgentHealthResponseSchema = z
  .object({
    agents: z.union([AgentHealthMapSchema, z.record(AgentMetricsSchema)]),
    count: z.number().int().min(0),
  })
  .passthrough();

export type AgentMetrics = z.infer<typeof AgentMetricsSchema>;
export type AgentHealthResponse = z.infer<typeof AgentHealthResponseSchema>;
