import { type AgentHealthResponse, AgentHealthResponseSchema } from "@domain/agent-health";
import { type AuditListResponse, AuditListResponseSchema } from "@domain/audit-row";
import { type ConsensusDecision, ConsensusDecisionSchema } from "@domain/consensus-decision";
import {
  type CalibrationResponse,
  CalibrationResponseSchema,
  type EscalationAnalytics,
  EscalationAnalyticsSchema,
  type SloResponse,
  SloResponseSchema,
} from "@domain/operations";
import type { City } from "@domain/primitives";
import { type TwinState, TwinStateSchema } from "@domain/twin-state";
import type { Tier } from "@lib/confidence";
import { z } from "zod";
import { createHttpClient } from "./http-client";
import { fetchJwks, knownKids } from "./jwks";

// ─── Auth schemas (mirror api/routers/auth.py) ────────────────────────────
export const LoginResponseSchema = z
  .object({
    access_token: z.string(),
    token_type: z.literal("Bearer"),
    expires_in: z.number().int().positive(),
    role: z.enum(["viewer", "ops", "engineer", "admin"]),
    operator_token_ref: z.string(),
  })
  .strict();
export type LoginResponse = z.infer<typeof LoginResponseSchema>;

export const RefreshResponseSchema = z
  .object({
    access_token: z.string(),
    token_type: z.literal("Bearer"),
    expires_in: z.number().int().positive(),
    role: z.enum(["viewer", "ops", "engineer", "admin"]),
  })
  .strict();
export type RefreshResponse = z.infer<typeof RefreshResponseSchema>;

// ─── Override schemas (mirror api/routers/decisions.py OverrideResponse) ──
export const OverrideApiResponseSchema = z
  .object({
    audit_escalation_id: z.number().int().positive(),
    decision_id: z.string().uuid(),
    action: z.enum(["approved", "rejected", "modified"]),
    operator_token_ref: z.string(),
    override_at: z.string(),
    orchestrator_notified: z.boolean(),
  })
  .strict();
export type OverrideApiResponse = z.infer<typeof OverrideApiResponseSchema>;

// ─── Decision detail (mirror api/routers/decisions.py get_decision) ───────
// Loose on the JSONB-bag fields (proposals, audit_trace, etc.) — those are
// validated by callers when they reshape into ConsensusDecision.
// ADR-044 anatomy + honesty fields are `.optional()` so this client keeps
// validating against pre-044 gateways (additive contract).
export const DecisionDetailResponseSchema = z
  .object({
    audit_id: z.string(),
    decision_id: z.string(),
    tier: z.string(),
    phase_reached: z.number().int(),
    confidence: z.number(),
    escalated: z.boolean(),
    city: z.string().nullable().optional(),
    proposals: z.unknown(),
    selected_action: z.unknown(),
    pareto_weights: z.unknown(),
    human_override: z.unknown().nullable().optional(),
    audit_trace: z.unknown(),
    created_at: z.string().nullable().optional(),
    escalations: z.array(z.unknown()).optional(),
    // ADR-044 — previously-imprisoned audit_consensus columns.
    debate_rounds: z.number().int().min(0).optional(),
    pareto_front: z.array(z.record(z.unknown())).nullable().optional(),
    execution_confirmations: z.array(z.string()).nullable().optional(),
    context_messages: z.array(z.record(z.unknown())).nullable().optional(),
    outcome: z.record(z.unknown()).nullable().optional(),
    prev_hash: z.string().nullable().optional(),
    current_hash: z.string().nullable().optional(),
    // Tri-state: true = single-row hash recompute matches; false = content
    // altered since insert; null = pre-Sprint-9 legacy row (E-S9-01).
    chain_verified: z.boolean().nullable().optional(),
    degraded: z.boolean().optional(),
    is_synthetic: z.boolean().optional(),
  })
  .passthrough();
export type DecisionDetailResponse = z.infer<typeof DecisionDetailResponseSchema>;

// ─── System posture (mirror api/routers/system.py, ADR-044 D4) ────────────
// The DegradedBanner's data source: brownout level per city + every circuit
// breaker's state. Polled (~15s); a fetch failure renders "posture unknown".
export const SystemPostureSchema = z
  .object({
    brownout: z.record(z.string()).default({}),
    breakers: z.record(z.string()).default({}),
    degraded: z.boolean(),
  })
  .passthrough();
export type SystemPosture = z.infer<typeof SystemPostureSchema>;

// ─── Topology (mirror api/routers/topology.py) ────────────────────────────
const TopologyNodeSchema = z
  .object({
    id: z.string(),
    type: z.string(),
    lat: z.number().nullable().optional(),
    lon: z.number().nullable().optional(),
  })
  .passthrough();
const TopologyEdgeSchema = z
  .object({
    src: z.string(),
    dst: z.string(),
    type: z.string(),
    weight: z.number().optional(),
  })
  .passthrough();
export const TopologyResponseSchema = z
  .object({
    city: z.string(),
    nodes: z.array(TopologyNodeSchema),
    edges: z.array(TopologyEdgeSchema),
    generated_at: z.string(),
  })
  .passthrough();
export type TopologyResponse = z.infer<typeof TopologyResponseSchema>;

// Hand-rolled typed client for the BE endpoints the FE consumes today.
// Lives alongside (and will eventually be superseded by) the OpenAPI-codegen
// client in `openapi.gen.ts` once gateway publishes /openapi.json.

export interface SynapseApiDeps {
  readonly orchestratorUrl: string;
  readonly gatewayUrl: string;
  readonly twinUrl?: string | undefined;
  readonly getAccessToken?: (() => string | null) | undefined;
  readonly onAuthExpired?: (() => Promise<void> | void) | undefined;
}

export function createSynapseApi(deps: SynapseApiDeps) {
  const gateway = createHttpClient({
    baseUrl: deps.gatewayUrl,
    getAccessToken: deps.getAccessToken,
    onAuthExpired: deps.onAuthExpired,
  });
  const orchestrator = createHttpClient({
    baseUrl: deps.orchestratorUrl,
    getAccessToken: deps.getAccessToken,
    onAuthExpired: deps.onAuthExpired,
  });
  const twin = createHttpClient({
    baseUrl: deps.twinUrl ?? deps.orchestratorUrl,
    getAccessToken: deps.getAccessToken,
    onAuthExpired: deps.onAuthExpired,
  });

  return {
    // Gateway — api/main.py
    health: () => gateway.get<{ status: string; service: string }>("/health"),
    ready: () => gateway.get<{ status: string; orchestrator: string }>("/ready"),
    listAgents: (): Promise<AgentHealthResponse> =>
      gateway.get("/api/v1/agents", {
        schema: AgentHealthResponseSchema,
        schemaId: "AgentHealthResponse",
      }),
    listRecentDecisions: (
      params: {
        limit?: number;
        city?: City;
        tier?: Tier;
        escalated?: boolean;
      } = {},
    ): Promise<AuditListResponse> =>
      gateway.get("/api/v1/decisions/recent", {
        query: params,
        schema: AuditListResponseSchema,
        schemaId: "AuditListResponse",
      }),
    submitOrder: (
      body: {
        city: City;
        store_id: string;
        sku_id: string;
        quantity: number;
      },
      opts: { idempotencyKey?: string } = {},
    ) =>
      gateway.post<{ status: string; order_id: string; outbox_id: string }>(
        "/api/v1/orders",
        body,
        // WS-2: orders route is now outbox-backed (202 Accepted) and the
        // Idempotency-Key header dedupes downstream consumers. Spread to
        // include `headers` only when defined — exactOptionalPropertyTypes
        // forbids assigning `undefined` to an optional property.
        opts.idempotencyKey
          ? {
              idempotent: true,
              headers: { "Idempotency-Key": opts.idempotencyKey },
            }
          : { idempotent: false },
      ),

    // Orchestrator — orchestrator/inference/serve.py
    submitDecision: (body: {
      order_id?: string;
      store_id?: string;
      items?: unknown[];
      agents_involved?: string[];
      disruption_active?: boolean;
      requires_twin_simulation?: boolean;
    }): Promise<ConsensusDecision> =>
      orchestrator.post<ConsensusDecision>("/api/v1/decisions", body, {
        idempotent: false,
        schema: ConsensusDecisionSchema,
        schemaId: "ConsensusDecision",
      }),

    // Digital Twin — digital_twin/inference/serve.py
    simulate: (body: {
      name: string;
      description?: string;
      demand_multiplier?: number;
      lead_time_multiplier?: number;
      failure_rate_multiplier?: number;
      spoilage_rate_multiplier?: number;
      n_scenarios?: number;
      duration_hours?: number;
    }): Promise<TwinState> =>
      twin.post("/simulate", body, {
        idempotent: true,
        schema: TwinStateSchema,
        schemaId: "TwinState",
      }),

    // ─── Auth (P1) ─────────────────────────────────────────────────────
    login: (creds: { operator_id: string; password: string }): Promise<LoginResponse> =>
      gateway.post("/api/v1/auth/login", creds, {
        idempotent: false,
        schema: LoginResponseSchema,
        schemaId: "LoginResponse",
      }),
    refresh: (): Promise<RefreshResponse> =>
      gateway.post("/api/v1/auth/refresh", undefined, {
        idempotent: true,
        schema: RefreshResponseSchema,
        schemaId: "RefreshResponse",
      }),
    logout: () => gateway.post("/api/v1/auth/logout", undefined, { idempotent: false }),

    // ─── Override (P1, hardened in WS-2) ──────────────────────────────
    submitOverride: (
      decision_id: string,
      body: {
        action: "approved" | "rejected" | "modified";
        reason: string;
        modified_action?: Record<string, unknown>;
        // WS-2: opaque key for replay-safe override. When present, the
        // backend deduplicates against (decision_id, idempotency_key) and
        // returns the original row. The mutation hook should generate one
        // per intent (e.g. crypto.randomUUID()) and reuse on retry.
        idempotency_key?: string;
      },
    ): Promise<OverrideApiResponse> =>
      gateway.post(`/api/v1/decisions/${decision_id}/override`, body, {
        idempotent: Boolean(body.idempotency_key),
        schema: OverrideApiResponseSchema,
        schemaId: "OverrideApiResponse",
      }),

    // ─── Decision detail (WS-4 §4a) ───────────────────────────────────
    // Moved from a raw fetch in DecisionDetail.tsx into the typed client.
    getDecision: (decision_id: string): Promise<DecisionDetailResponse> =>
      gateway.get(`/api/v1/decisions/${decision_id}`, {
        schema: DecisionDetailResponseSchema,
        schemaId: "DecisionDetailResponse",
      }),

    // ─── Topology (WS-4 §4d) ──────────────────────────────────────────
    // Moved from raw fetch in useTopology.ts into the typed client.
    getTopology: (city: City): Promise<TopologyResponse> =>
      gateway.get("/api/v1/topology", {
        query: { city },
        schema: TopologyResponseSchema,
        schemaId: "TopologyResponse",
      }),

    // ─── System posture (ADR-044 D4) ──────────────────────────────────
    // Brownout level per city + breaker states; drives the DegradedBanner.
    getSystemPosture: (): Promise<SystemPosture> =>
      gateway.get("/api/v1/system/posture", {
        schema: SystemPostureSchema,
        schemaId: "SystemPosture",
      }),

    // ─── Operations / Standing Watch (ADR-046) ────────────────────────
    // SLO burn (Prometheus multi-window), confidence calibration (scored
    // outcomes), and escalation pressure. Every "could be missing" number
    // arrives nullable so the UI renders "unknown", never a healthy lie.
    getSlo: (): Promise<SloResponse> =>
      gateway.get("/api/v1/system/slo", {
        schema: SloResponseSchema,
        schemaId: "SloResponse",
      }),
    getCalibration: (
      params: { window_hours?: number; include_synthetic?: boolean; city?: City } = {},
    ): Promise<CalibrationResponse> =>
      gateway.get("/api/v1/system/calibration", {
        query: params,
        schema: CalibrationResponseSchema,
        schemaId: "CalibrationResponse",
      }),
    getEscalationAnalytics: (
      params: { window_hours?: number; city?: City } = {},
    ): Promise<EscalationAnalytics> =>
      gateway.get("/api/v1/escalations/analytics", {
        query: params,
        schema: EscalationAnalyticsSchema,
        schemaId: "EscalationAnalytics",
      }),

    // ─── Steering (WS-5) ──────────────────────────────────────────────
    // Writes one operator change to the audit trail. The FE store calls
    // this BEFORE mutating local state — on failure, the change is
    // reverted in the UI. Idempotency_key is a UUID generated per intent;
    // retry with the same key returns the existing row.
    submitSteering: (body: {
      action: "set_pareto_weight" | "set_tier_threshold" | "reset";
      target?: string | null;
      value?: number | null;
      idempotency_key?: string;
    }): Promise<{
      steering_id: string;
      operator_token_ref: string;
      action: string;
      target: string | null;
      value: number | null;
      created_at: string;
    }> =>
      gateway.post("/api/v1/steering", body, {
        idempotent: Boolean(body.idempotency_key),
        schema: z
          .object({
            steering_id: z.string(),
            operator_token_ref: z.string(),
            action: z.string(),
            target: z.string().nullable(),
            value: z.number().nullable(),
            created_at: z.string(),
          })
          .passthrough(),
        schemaId: "SteeringResponse",
      }),

    // ─── JWKS (WS-4 §4c, ADR-038-adjacent) ────────────────────────────
    // Lightweight visibility-only JWKS fetch. Full client-side signature
    // verification is a follow-up sprint; this primitive lets the auth
    // refresh path detect a rotation event (kid mismatch) rather than
    // looping on a stale 401.
    jwks: {
      fetch: () => fetchJwks(deps.gatewayUrl),
      knownKids: async () => knownKids(await fetchJwks(deps.gatewayUrl)),
    },
  };
}

export type SynapseApi = ReturnType<typeof createSynapseApi>;
