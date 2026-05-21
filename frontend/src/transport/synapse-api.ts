import { z } from "zod";
import { createHttpClient } from "./http-client";
import { AgentHealthResponseSchema, type AgentHealthResponse } from "@domain/agent-health";
import { AuditListResponseSchema, type AuditListResponse } from "@domain/audit-row";
import {
  ConsensusDecisionSchema,
  type ConsensusDecision,
} from "@domain/consensus-decision";
import { TwinStateSchema, type TwinState } from "@domain/twin-state";
import type { City } from "@domain/primitives";
import type { Tier } from "@lib/confidence";

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

// Hand-rolled typed client for the BE endpoints the FE consumes today.
// Lives alongside (and will eventually be superseded by) the OpenAPI-codegen
// client in `openapi.gen.ts` once gateway publishes /openapi.json.

export interface SynapseApiDeps {
  readonly orchestratorUrl: string;
  readonly gatewayUrl: string;
  readonly twinUrl?: string;
  readonly getAccessToken?: () => string | null;
  readonly onAuthExpired?: () => Promise<void> | void;
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
    ready: () =>
      gateway.get<{ status: string; orchestrator: string }>("/ready"),
    listAgents: (): Promise<AgentHealthResponse> =>
      gateway.get("/api/v1/agents", {
        schema: AgentHealthResponseSchema,
        schemaId: "AgentHealthResponse",
      }),
    listRecentDecisions: (params: {
      limit?: number;
      city?: City;
      tier?: Tier;
      escalated?: boolean;
    } = {}): Promise<AuditListResponse> =>
      gateway.get("/api/v1/decisions/recent", {
        query: params,
        schema: AuditListResponseSchema,
        schemaId: "AuditListResponse",
      }),
    submitOrder: (body: {
      city: City;
      store_id: string;
      sku_id: string;
      quantity: number;
    }) =>
      gateway.post<{ status: string; city: City }>("/api/v1/orders", body, {
        idempotent: false,
      }),

    // Orchestrator — orchestrator/inference/serve.py
    submitDecision: (body: {
      order_id?: string;
      store_id?: string;
      items?: unknown[];
      agents_involved?: string[];
      disruption_active?: boolean;
      requires_twin_simulation?: boolean;
    }): Promise<ConsensusDecision> =>
      orchestrator.post("/api/v1/decisions", body, {
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

    // ─── Override (P1) ─────────────────────────────────────────────────
    submitOverride: (
      decision_id: string,
      body: {
        action: "approved" | "rejected" | "modified";
        reason: string;
        modified_action?: Record<string, unknown>;
      },
    ): Promise<OverrideApiResponse> =>
      gateway.post(`/api/v1/decisions/${decision_id}/override`, body, {
        idempotent: false,
        schema: OverrideApiResponseSchema,
        schemaId: "OverrideApiResponse",
      }),
  };
}

export type SynapseApi = ReturnType<typeof createSynapseApi>;
