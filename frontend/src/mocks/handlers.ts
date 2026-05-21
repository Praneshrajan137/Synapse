import { isCity } from "@/domain/city";
import type { ShockParams, ShockScenario } from "@/domain/twin";
import { AGENT_NAMES, type AgentName } from "@/ui/tokens";
import { http, HttpResponse } from "msw";
import {
  makeAuditRow,
  makeAuditTimeline,
  makeDecision,
  makeEscalations,
  makeKpis,
  makeRecentDecisions,
  makeTierDistribution,
} from "./data";
import { makeAgentDetail, makeMonteCarlo, makeTopics, makeTopology } from "./data8";

/**
 * MSW request handlers — the mock SYNAPSE gateway.
 *
 * Serves the contracts the surfaces consume so the UI is fully
 * demonstrable and testable without the Python stack. Swapped off for a
 * real backend by building with VITE_MOCK_API=false.
 */

function cityParam(request: Request): "bengaluru" | "mumbai" | undefined {
  const value = new URL(request.url).searchParams.get("city");
  return value && isCity(value) ? value : undefined;
}

export const handlers = [
  http.get("/health", () => HttpResponse.json({ status: "ok", service: "orchestrator" })),

  http.get("/api/v1/kpis", () => HttpResponse.json(makeKpis())),

  http.get("/api/v1/tier-distribution", () => HttpResponse.json(makeTierDistribution())),

  // Order matters: /recent must precede /:id.
  http.get("/api/v1/decisions/recent", ({ request }) => {
    const limit = Number(new URL(request.url).searchParams.get("limit") ?? "40");
    return HttpResponse.json(makeRecentDecisions(limit, cityParam(request)));
  }),

  http.get("/api/v1/decisions/:id", ({ params }) =>
    HttpResponse.json(makeDecision(String(params.id))),
  ),

  http.get("/api/v1/escalations", ({ request }) =>
    HttpResponse.json(makeEscalations(cityParam(request))),
  ),

  http.get("/api/v1/audit/timeline", ({ request }) => {
    const count = Number(new URL(request.url).searchParams.get("count") ?? "60");
    return HttpResponse.json(makeAuditTimeline(count, cityParam(request)));
  }),

  http.get("/api/v1/audit/:id", ({ params }) =>
    HttpResponse.json(makeAuditRow(String(params.id))),
  ),

  // HITL override submission — echoes the accepted override.
  http.post("/api/v1/decisions/:id/override", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      decisionId: String(params.id),
      accepted: true,
      override: body,
      at: Date.now(),
    });
  }),

  // --- Phase 8: Twin, Inspector, Streams -------------------------------
  http.get("/api/v1/twin/topology", ({ request }) => {
    const city = cityParam(request) ?? "bengaluru";
    return HttpResponse.json(makeTopology(city));
  }),

  http.post("/api/v1/twin/what-if", async ({ request }) => {
    const body = (await request.json()) as {
      scenario: ShockScenario;
      params: ShockParams;
    };
    return HttpResponse.json(makeMonteCarlo(body.scenario, body.params));
  }),

  http.get("/api/v1/agents/:name/detail", ({ params }) => {
    const name = String(params.name);
    if (!(AGENT_NAMES as readonly string[]).includes(name)) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(makeAgentDetail(name as AgentName));
  }),

  http.get("/api/v1/topics", () => HttpResponse.json(makeTopics())),
];
