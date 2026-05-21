/**
 * SYNAPSE Atlas Console — deterministic MSW fixtures.
 *
 * Used by REST + WS + SSE handlers. Seeds are pinned so Storybook
 * snapshots and Vitest contract tests are reproducible across runs.
 *
 * Every shape here aligns with packages/openapi/openapi.json. When the
 * snapshot refreshes via tests/contract/refresh_openapi_snapshot.py,
 * any drift surfaces as a TS compile error in handlers.ts.
 */
import type { components } from "../../api/__generated__/synapse";

// While Orval-generated types aren't yet in the repo (gitignored), we
// duplicate the small shapes we need. After the first `pnpm orval` run
// this duplication can be removed in favour of the generated `components`
// type. Until then, hand-typed fallbacks below.
type City = "bengaluru" | "mumbai";
type Tier = "tier_1" | "tier_2" | "tier_3" | "tier_4";

export const SEED = 20260430;

export const fixtureCity: City = "bengaluru";

export const fixtureSession = {
  authenticated: true as const,
  persona: "ops_controller",
  expires_at: "2026-05-01T18:00:00Z",
  elevated_until: null,
  claims: { city: ["bengaluru", "mumbai"] },
};

export const fixtureLogin = {
  persona: "ops_controller",
  csrf_token: "csrf-fixture-deadbeef",
  expires_at: "2026-05-01T18:00:00Z",
  claims: { city: ["bengaluru", "mumbai"] },
};

export const fixtureRecentDecisions = {
  count: 3,
  decisions: [
    {
      audit_id: "11111111-1111-1111-1111-111111111111",
      decision_id: "aaaa1111-aaaa-4aaa-aaaa-aaaa11111111",
      tier: "tier_2" as Tier,
      created_at: "2026-04-30T10:14:21Z",
    },
    {
      audit_id: "22222222-2222-2222-2222-222222222222",
      decision_id: "bbbb2222-bbbb-4bbb-bbbb-bbbb22222222",
      tier: "tier_3" as Tier,
      created_at: "2026-04-30T10:13:55Z",
    },
    {
      audit_id: "33333333-3333-3333-3333-333333333333",
      decision_id: "cccc3333-cccc-4ccc-cccc-cccc33333333",
      tier: "tier_4" as Tier,
      created_at: "2026-04-30T10:13:40Z",
    },
  ],
};

export const fixtureConsensusDecision = {
  id: "11111111-1111-1111-1111-111111111111",
  decision_id: "aaaa1111-aaaa-4aaa-aaaa-aaaa11111111",
  timestamp: "2026-04-30T10:14:21Z",
  tier: "tier_3" as Tier,
  phase_reached: 5,
  proposals: [
    {
      agent: "demand_prophet",
      action: { sku_id: "SKU-001", forecast: 412, horizon_min: 60 },
      confidence: 0.74,
      justification: "Conformal interval narrowed by post-monsoon stability.",
    },
    {
      agent: "inventory_sentinel",
      action: { sku_id: "SKU-001", reorder: 250 },
      confidence: 0.66,
      justification: "Safety-stock target undershot by 18%.",
    },
  ],
  selected_action: { sku_id: "SKU-001", reorder: 280, multiplier: 1.0 },
  pareto_weights: { revenue: 0.4, fill_rate: 0.4, co2: 0.2 },
  confidence: 0.68,
  debate_rounds: 2,
  escalated: true,
  human_override: null,
  execution_confirmations: [],
  context_messages: [
    { phase: 1, role: "system", content: "Ingest order batch ORD-9981." },
    { phase: 2, role: "agent:demand_prophet", content: "Forecast 412 ± 38." },
    { phase: 3, role: "agent:inventory_sentinel", content: "Reorder 250 proposed." },
    { phase: 4, role: "system", content: "Pareto knee selected." },
    { phase: 5, role: "system", content: "Awaiting human decision (escalated)." },
  ],
  audit_trace: [
    { hash: "0".repeat(64), prev: null, ts: "2026-04-30T10:14:20Z" },
    { hash: "f".repeat(64), prev: "0".repeat(64), ts: "2026-04-30T10:14:21Z" },
  ],
  pareto_front: [
    { revenue: 0.92, fill_rate: 0.81, co2: 0.55 },
    { revenue: 0.88, fill_rate: 0.85, co2: 0.50 },
    { revenue: 0.84, fill_rate: 0.88, co2: 0.46 },
  ],
  outcome: null,
  created_at: "2026-04-30T10:14:21Z",
};

export const fixtureAgents = {
  count: 8,
  agents: {
    "demand-prophet": "ok",
    "routing-navigator": "ok",
    "inventory-sentinel": "ok",
    "pricing-oracle": "ok",
    "disruption-shield": "ok",
    "supplier-trust": "ok",
    "sustainability-agent": "ok",
    "freshness-guardian": "ok",
  },
};

/**
 * Deterministic fixture-loop event tail per topic.
 * Used by the SSE handler in browser/Storybook so the Living City
 * surface has a believable stream without a backend.
 */
export const fixtureSseEvents: Record<string, ReadonlyArray<unknown>> = {
  "synapse.demand.forecast": [
    { sku_id: "SKU-001", store_id: "store-blr-12", forecast: 412, horizon_min: 60 },
    { sku_id: "SKU-002", store_id: "store-blr-12", forecast: 90, horizon_min: 60 },
  ],
  "synapse.routing.plan": [
    {
      route_id: "rt-abc1",
      rider_id: "rider-77",
      legs: [{ from: "store-blr-12", to: "addr-9981", eta_s: 540 }],
    },
  ],
  "synapse.disruption.alert": [
    { kind: "supplier_late", supplier_id: "sup-22", severity: 0.8 },
  ],
  "synapse.orchestrator.escalation": [
    {
      type: "escalation",
      decision_id: fixtureConsensusDecision.decision_id,
      tier: "tier_4",
      confidence: 0.31,
      proposals: fixtureConsensusDecision.proposals,
      recommended_action: fixtureConsensusDecision.selected_action,
      violations: [],
    },
  ],
  "synapse.metrics.agent": [
    { agent: "demand_prophet", reward: 0.74 },
    { agent: "routing_navigator", reward: 0.81 },
  ],
  "synapse.freshness.alert": [
    { store_id: "store-blr-12", sku_id: "SKU-009", hours_to_expiry: 4.2 },
  ],
  "synapse.pricing.update": [
    { sku_id: "SKU-001", final_price: 49.0, multiplier: 1.0, is_essential: false },
  ],
  "synapse.inventory.reorder": [
    { sku_id: "SKU-001", store_id: "store-blr-12", quantity: 280 },
  ],
  "synapse.orchestrator.decision": [
    { decision_id: fixtureConsensusDecision.decision_id, tier: "tier_3", confidence: 0.68 },
  ],
  "synapse.audit.log": [
    { decision_id: fixtureConsensusDecision.decision_id, hash: "f".repeat(64) },
  ],
};
