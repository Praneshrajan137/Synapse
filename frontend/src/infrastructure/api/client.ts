import type { AuditRow, AuditTimelineEntry } from "@/domain/audit";
import type { City } from "@/domain/city";
import type {
  Decision,
  DecisionSummary,
  Escalation,
  HumanOverride,
} from "@/domain/decision";
import type { Kpi, TierDistribution } from "@/domain/kpi";
import type { AgentDetail, KafkaTopic } from "@/domain/observability";
import type {
  MonteCarloResult,
  ShockParams,
  ShockScenario,
  TwinTopology,
} from "@/domain/twin";

/**
 * Typed SYNAPSE gateway client.
 *
 * A thin fetch wrapper — React Query owns caching, retries and polling.
 * Served by MSW in mock mode (the default) or a real FastAPI gateway.
 */

const BASE = "/api/v1";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

function cityQuery(city?: City): string {
  return city ? `&city=${city}` : "";
}

export interface OverrideRequest {
  action: HumanOverride["action"];
  reason: string;
  operator: string;
  modifiedPayload?: Record<string, unknown>;
}

export const api = {
  kpis: () => getJson<Kpi[]>("/kpis"),
  tierDistribution: () => getJson<TierDistribution>("/tier-distribution"),

  recentDecisions: (limit: number, city?: City) =>
    getJson<DecisionSummary[]>(`/decisions/recent?limit=${limit}${cityQuery(city)}`),
  decision: (id: string) => getJson<Decision>(`/decisions/${id}`),

  escalations: (city?: City) =>
    getJson<Escalation[]>(`/escalations?_=1${cityQuery(city)}`),

  auditTimeline: (count: number, city?: City) =>
    getJson<AuditTimelineEntry[]>(`/audit/timeline?count=${count}${cityQuery(city)}`),
  auditRow: (id: string) => getJson<AuditRow>(`/audit/${id}`),

  submitOverride: (decisionId: string, request: OverrideRequest) =>
    postJson<{ accepted: boolean; at: number }>(
      `/decisions/${decisionId}/override`,
      request,
    ),

  twinTopology: (city?: City) =>
    getJson<TwinTopology>(`/twin/topology?_=1${cityQuery(city)}`),
  twinWhatIf: (scenario: ShockScenario, params: ShockParams) =>
    postJson<MonteCarloResult>("/twin/what-if", { scenario, params }),

  agentDetail: (name: string) => getJson<AgentDetail>(`/agents/${name}/detail`),

  topics: () => getJson<KafkaTopic[]>("/topics"),
};
