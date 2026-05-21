import { http, HttpResponse } from "msw";

// Minimal MSW handlers tracking the BE surface today.
// Contract drift between these and OpenAPI codegen will fail CI in P0+.

export const handlers = [
  http.get(/\/health$/, () =>
    HttpResponse.json({ status: "ok", service: "synapse-api" }),
  ),
  http.get(/\/ready$/, () =>
    HttpResponse.json({ status: "ready", orchestrator: "http://localhost:8085" }),
  ),
  http.get(/\/api\/v1\/agents$/, () =>
    HttpResponse.json({
      agents: {
        demand_prophet: "healthy",
        routing_navigator: "healthy",
        inventory_sentinel: "healthy",
        freshness_guardian: "healthy",
        pricing_oracle: "healthy",
        disruption_shield: "healthy",
        supplier_trust: "healthy",
        sustainability_agent: "healthy",
      },
      count: 8,
    }),
  ),
  http.get(/\/api\/v1\/decisions\/recent/, () =>
    HttpResponse.json({ decisions: [], count: 0 }),
  ),
];
