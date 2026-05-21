/**
 * SYNAPSE Atlas Console — MSW REST handlers.
 *
 * Mirrors packages/openapi/openapi.json. Used by Storybook (browser
 * worker) and Vitest (node server). Surface-specific overrides should
 * call `server.use(...)` inside the test, not extend this set globally.
 */
import { http, HttpResponse, delay } from "msw";

import {
  fixtureAgents,
  fixtureConsensusDecision,
  fixtureLogin,
  fixtureRecentDecisions,
  fixtureSession,
} from "./fixtures";

const BASE = "*";

export const restHandlers = [
  // ─── Auth ────────────────────────────────────────────────────────────────
  http.post(`${BASE}/auth/login`, async () => {
    await delay(20);
    return HttpResponse.json(fixtureLogin, {
      status: 200,
      headers: {
        "Set-Cookie":
          "synapse_session=msw-fixture-sid; Path=/; HttpOnly; SameSite=Strict",
      },
    });
  }),
  http.post(`${BASE}/auth/logout`, () => HttpResponse.json({ status: "ok" })),
  http.post(`${BASE}/auth/refresh`, () => HttpResponse.json(fixtureLogin)),
  http.post(`${BASE}/auth/reauth`, () =>
    HttpResponse.json({ status: "ok", elevated_until: "2026-04-30T10:20:00Z" }),
  ),
  http.get(`${BASE}/auth/session`, () => HttpResponse.json(fixtureSession)),

  // ─── Decisions ───────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/decisions/recent`, () =>
    HttpResponse.json(fixtureRecentDecisions),
  ),
  http.get(`${BASE}/api/v1/decisions/:decisionId`, ({ params }) => {
    const id = String(params["decisionId"] ?? "");
    if (id === fixtureConsensusDecision.decision_id) {
      return HttpResponse.json(fixtureConsensusDecision);
    }
    return HttpResponse.json({ detail: `no decision with id ${id}` }, { status: 404 });
  }),
  http.post(`${BASE}/api/v1/decisions`, async () => {
    await delay(40);
    return HttpResponse.json({
      decision_id: fixtureConsensusDecision.decision_id,
      tier: fixtureConsensusDecision.tier,
      confidence: fixtureConsensusDecision.confidence,
      phase_reached: fixtureConsensusDecision.phase_reached,
      audit_id: fixtureConsensusDecision.id,
      escalated: fixtureConsensusDecision.escalated,
    });
  }),

  // ─── Orders ──────────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/orders`, () =>
    HttpResponse.json({ status: "accepted", city: "bengaluru" }),
  ),

  // ─── Agents ──────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/agents`, () => HttpResponse.json(fixtureAgents)),

  // ─── RUM (B4) ────────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/rum`, () =>
    HttpResponse.json({ status: "ok", kind: "rum", samples_recorded: "0" }),
  ),

  // ─── Health ──────────────────────────────────────────────────────────────
  http.get(`${BASE}/health`, () =>
    HttpResponse.json({ status: "ok", service: "synapse-atlas-console" }),
  ),
];
