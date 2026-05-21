import type { AuditRow, AuditTimelineEntry } from "@/domain/audit";
import type { City } from "@/domain/city";
import type {
  ActionPayload,
  AgentProposal,
  ConsensusPhase,
  ContextMessage,
  Decision,
  DecisionSummary,
  DecisionTier,
  Escalation,
  ParetoPoint,
} from "@/domain/decision";
import type { Kpi, TierDistribution } from "@/domain/kpi";
import { AGENT_NAMES, type AgentName } from "@/ui/tokens";

/**
 * Deterministic mock data for the SYNAPSE frontend.
 *
 * MSW serves these so every surface is demonstrable and testable
 * without the Python stack. A seeded PRNG keeps Replay reproducible —
 * the same decision id always yields the same decision (tenet T-1).
 */

/** mulberry32 — tiny deterministic PRNG. */
function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function pick<T>(r: () => number, items: readonly T[]): T {
  return items[Math.floor(r() * items.length)] as T;
}

const TIERS: readonly DecisionTier[] = ["tier_1", "tier_2", "tier_3", "tier_4"];

/**
 * Fixed reference epoch for decisions looked up by id (Replay / audit).
 * Keeping it constant — not Date.now() — makes makeDecision fully
 * deterministic, so the same id always reproduces the same decision.
 */
const REPLAY_EPOCH = Date.UTC(2026, 4, 20, 9, 0, 0);

const SKUS = [
  "SKU-MILK-1L",
  "SKU-BREAD-400",
  "SKU-EGGS-12",
  "SKU-COLA-500",
  "SKU-CHIPS-90",
];
const STORES_BLR = ["BLR-S-007", "BLR-S-012", "BLR-S-019", "BLR-S-024", "BLR-S-031"];
const STORES_MUM = ["MUM-S-003", "MUM-S-008", "MUM-S-014", "MUM-S-021", "MUM-S-029"];

/** Build the agent-specific action payload (drives generative UI). */
function makeAction(agent: AgentName, r: () => number, city: City): ActionPayload {
  const store = pick(r, city === "mumbai" ? STORES_MUM : STORES_BLR);
  const sku = pick(r, SKUS);
  switch (agent) {
    case "demand_prophet":
      return {
        kind: "demand.forecast.v1",
        data: {
          skuId: sku,
          storeId: store,
          horizons: {
            "15m": Math.round(20 + r() * 40),
            "1h": Math.round(80 + r() * 120),
            "6h": Math.round(400 + r() * 300),
            "24h": Math.round(1400 + r() * 700),
            "7d": Math.round(9000 + r() * 4000),
          },
          coverage: 0.9,
        },
      };
    case "routing_navigator":
      return {
        kind: "routing.plan.v1",
        data: {
          riderId: `R-${Math.floor(r() * 90) + 10}`,
          stops: Math.floor(r() * 4) + 2,
          etaMin: Math.round(6 + r() * 6),
        },
      };
    case "inventory_sentinel":
      return {
        kind: "inventory.reorder.v1",
        data: {
          skuId: sku,
          storeId: store,
          currentUnits: Math.floor(r() * 40),
          reorderUnits: Math.floor(r() * 120) + 40,
        },
      };
    case "freshness_guardian":
      return {
        kind: "freshness.alert.v1",
        data: {
          skuId: sku,
          storeId: store,
          shelfLifeHours: Math.round(r() * 18) + 2,
          markdownPct: Math.round(r() * 30) + 10,
        },
      };
    case "pricing_oracle": {
      const oldM = 1 + Math.round(r() * 20) / 100;
      return {
        kind: "pricing.update.v1",
        data: {
          skuId: sku,
          storeId: store,
          oldMultiplier: oldM,
          newMultiplier: Math.min(1.3, oldM + Math.round(r() * 12) / 100),
          essential: r() > 0.6,
        },
      };
    }
    case "disruption_shield":
      return {
        kind: "disruption.alert.v1",
        data: {
          kind: pick(r, ["warehouse_offline", "monsoon_flood", "supplier_default"]),
          severity: Math.round((0.6 + r() * 0.39) * 100) / 100,
          affectedStores: [store, pick(r, city === "mumbai" ? STORES_MUM : STORES_BLR)],
        },
      };
    case "supplier_trust":
      return {
        kind: "supplier.score.v1",
        data: {
          supplierId: `SUP-${Math.floor(r() * 40) + 10}`,
          trustScore: Math.round((0.5 + r() * 0.49) * 100) / 100,
          leadTimeDays: Math.round((1 + r() * 3) * 10) / 10,
        },
      };
    case "sustainability_agent":
      return {
        kind: "sustainability.carbon.v1",
        data: {
          co2KgPerDelivery: Math.round((0.4 + r() * 1.1) * 100) / 100,
          wastePredictionKg: Math.round(r() * 24 * 10) / 10,
        },
      };
    default:
      return { kind: "generic.v1", data: {} };
  }
}

const JUSTIFICATIONS: Record<AgentName, string[]> = {
  demand_prophet: [
    "forecast +14% vs trend",
    "IPL match surge detected",
    "conformal band stable",
  ],
  routing_navigator: [
    "3 riders idle in zone",
    "OSRM ETA within budget",
    "fairness index 0.91",
  ],
  inventory_sentinel: [
    "stock below safety margin",
    "perishable shelf life 6h",
    "transfer viable",
  ],
  freshness_guardian: [
    "FSSAI cold-chain nominal",
    "spoilage risk rising",
    "markdown recommended",
  ],
  pricing_oracle: [
    "elasticity -1.3 (Double ML)",
    "competitor +8%",
    "1.3x essential cap respected",
  ],
  disruption_shield: ["twin divergence KL 0.14", "playbook retrieved", "severity 0.85"],
  supplier_trust: ["lead-time posterior shifted", "GNN embedding drift", "trust 0.81"],
  sustainability_agent: [
    "carbon within ESG target",
    "waste survival curve flat",
    "route CO2 -0.2kg",
  ],
};

function makeProposal(
  agent: AgentName,
  r: () => number,
  city: City,
  tier: DecisionTier,
): AgentProposal {
  const trace = JUSTIFICATIONS[agent];
  return {
    agentName: agent,
    utilityScore: Math.round((0.45 + r() * 0.5) * 100) / 100,
    confidence: Math.round((0.4 + r() * 0.58) * 100) / 100,
    justificationTrace: trace.slice(0, Math.floor(r() * 2) + 2),
    action: makeAction(agent, r, city),
    tier,
  };
}

function makeParetoFront(r: () => number): ParetoPoint[] {
  const n = 9;
  const points: ParetoPoint[] = [];
  const kneeIndex = Math.floor(n / 2);
  for (let i = 0; i < n; i += 1) {
    const t = i / (n - 1);
    points.push({
      cost: Math.round((0.2 + t * 0.7 + (r() - 0.5) * 0.06) * 100) / 100,
      time: Math.round((0.9 - t * 0.7 + (r() - 0.5) * 0.06) * 100) / 100,
      sustainability: Math.round((0.4 + r() * 0.5) * 100) / 100,
      fairness: Math.round((0.5 + r() * 0.4) * 100) / 100,
      knee: i === kneeIndex,
    });
  }
  return points;
}

function makeContext(
  proposals: readonly AgentProposal[],
  tier: DecisionTier,
  baseTime: number,
): ContextMessage[] {
  const messages: ContextMessage[] = [];
  let seq = 0;
  const push = (
    source: string,
    role: ContextMessage["role"],
    status: ContextMessage["status"],
    phase: ConsensusPhase,
    content: string,
  ) => {
    messages.push({
      id: `ctx-${seq}`,
      source,
      role,
      status,
      phase,
      sequence: seq,
      content,
      timestamp: baseTime + seq * 420,
    });
    seq += 1;
  };

  push(
    "system",
    "system",
    "active",
    "collecting",
    "SYNAPSE orchestrator — consensus protocol engaged.",
  );
  for (const p of proposals) {
    push(
      p.agentName,
      "user",
      "active",
      "collecting",
      JSON.stringify({
        utility: p.utilityScore,
        confidence: p.confidence,
        action: p.action.kind,
      }),
    );
  }
  if (tier === "tier_3" || tier === "tier_4") {
    push(
      "llm",
      "assistant",
      "reasoning",
      "debating",
      "Utility divergence exceeds 0.3 — opening debate. Weighing routing throughput against inventory safety margin under the surge scenario.",
    );
    push(
      "orchestrator",
      "assistant",
      "resolved",
      "arbitrating",
      "NSGA-II Pareto front computed; knee solution selected.",
    );
  }
  push(
    "orchestrator",
    "assistant",
    "resolved",
    "executing",
    "Selected action dispatched to agents for execution.",
  );
  return messages;
}

const PHASE_FOR_TIER: Record<DecisionTier, ConsensusPhase> = {
  tier_1: "executing",
  tier_2: "executing",
  tier_3: "learning",
  tier_4: "learning",
};

const LATENCY_FOR_TIER: Record<DecisionTier, number> = {
  tier_1: 80,
  tier_2: 460,
  tier_3: 12_400,
  tier_4: 88_000,
};

/** Build a complete, deterministic decision from its id. */
export function makeDecision(
  id: string,
  opts: { city?: City; createdAt?: number } = {},
): Decision {
  const r = rng(hashString(id));
  const city: City = opts.city ?? (r() > 0.5 ? "bengaluru" : "mumbai");
  const tier = pick(r, TIERS);
  const nAgents = tier === "tier_1" ? 1 : tier === "tier_2" ? 3 : 5 + Math.floor(r() * 3);
  const agents = [...AGENT_NAMES].sort(() => r() - 0.5).slice(0, nAgents);
  const createdAt = opts.createdAt ?? REPLAY_EPOCH - Math.floor(r() * 3_600_000);

  const proposals = agents.map((a) => makeProposal(a, r, city, tier));
  const lead = [...proposals].sort(
    (a, b) => b.utilityScore - a.utilityScore,
  )[0] as AgentProposal;
  const confidence = lead.confidence;
  const escalated = confidence < 0.65 || r() > 0.82;
  const contextMessages = makeContext(proposals, tier, createdAt);

  return {
    id,
    city,
    tier,
    phase: PHASE_FOR_TIER[tier],
    status: escalated ? "escalated" : "executed",
    confidence,
    proposals,
    contextMessages,
    selectedAction: lead.action,
    paretoFront: tier === "tier_1" ? [] : makeParetoFront(r),
    debateRounds: tier === "tier_3" || tier === "tier_4" ? Math.floor(r() * 3) + 1 : 0,
    escalated,
    auditId: `audit-${id}`,
    humanOverride: null,
    outcome:
      r() > 0.4
        ? {
            fillRateDelta: Math.round((r() - 0.3) * 60) / 10,
            wasteRateDelta: Math.round((r() - 0.6) * 30) / 10,
            marginDelta: Math.round((r() - 0.4) * 5000),
            onTimeDelta: Math.round((r() - 0.35) * 50) / 10,
            measuredAt: createdAt + 86_400_000,
          }
        : null,
    latencyMs: LATENCY_FOR_TIER[tier] + Math.floor(r() * LATENCY_FOR_TIER[tier] * 0.2),
    createdAt,
    summary: summarize(lead),
  };
}

function summarize(p: AgentProposal): string {
  const d = p.action.data;
  const horizons = d.horizons as Record<string, number> | undefined;
  switch (p.action.kind) {
    case "pricing.update.v1":
      return `Pricing Oracle — set ${String(d.skuId)} multiplier to ${String(d.newMultiplier)}x`;
    case "inventory.reorder.v1":
      return `Inventory Sentinel — reorder ${String(d.reorderUnits)}u of ${String(d.skuId)}`;
    case "routing.plan.v1":
      return `Routing Navigator — assign rider ${String(d.riderId)}, ${String(d.stops)} stops`;
    case "demand.forecast.v1":
      return `Demand Prophet — 24h forecast ${String(horizons?.["24h"])}u`;
    case "disruption.alert.v1":
      return `Disruption Shield — ${String(d.kind)} severity ${String(d.severity)}`;
    case "freshness.alert.v1":
      return `Freshness Guardian — markdown ${String(d.skuId)} by ${String(d.markdownPct)}%`;
    case "supplier.score.v1":
      return `Supplier Trust — score ${String(d.supplierId)} at ${String(d.trustScore)}`;
    case "sustainability.carbon.v1":
      return `Sustainability — CO₂ ${String(d.co2KgPerDelivery)}kg/delivery`;
    default:
      return `${p.agentName} — action proposed`;
  }
}

export function toSummary(d: Decision): DecisionSummary {
  const lead = [...d.proposals].sort((a, b) => b.utilityScore - a.utilityScore)[0];
  return {
    id: d.id,
    city: d.city,
    tier: d.tier,
    confidence: d.confidence,
    escalated: d.escalated,
    status: d.status,
    leadAgent: lead?.agentName ?? "demand_prophet",
    summary: d.summary,
    createdAt: d.createdAt,
  };
}

/** A rolling list of recent decisions — the Bridge tape source. */
export function makeRecentDecisions(count: number, city?: City): DecisionSummary[] {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const id = `dec-${Math.floor(now / 60_000) - i}`;
    return toSummary(makeDecision(id, { city, createdAt: now - i * 47_000 }));
  });
}

/** Currently-open escalations for the Council queue. */
export function makeEscalations(city?: City): Escalation[] {
  const now = Date.now();
  const ids = ["dec-esc-1", "dec-esc-2"];
  return ids.map((id, i) => {
    const decision = {
      ...makeDecision(id, { city, createdAt: now - i * 90_000 }),
      escalated: true,
    };
    const lead = [...decision.proposals].sort(
      (a, b) => b.utilityScore - a.utilityScore,
    )[0];
    return {
      decision,
      recommendedAction: decision.selectedAction,
      recommendedAgent: lead?.agentName ?? "pricing_oracle",
      violations:
        decision.confidence < 0.5
          ? [
              {
                code: "low_confidence",
                detail: `Confidence ${decision.confidence.toFixed(2)} below Tier ${decision.tier.slice(-1)} threshold`,
              },
            ]
          : [
              {
                code: "twin_divergence",
                detail: "Digital-twin KL divergence 0.14 exceeds 0.1",
              },
            ],
      deadlineAt: now + (300_000 - i * 64_000),
    };
  });
}

export function makeKpis(): Kpi[] {
  const series = (base: number, jitter: number, seed: number): number[] => {
    const r = rng(seed);
    return Array.from(
      { length: 24 },
      () => Math.round((base + (r() - 0.5) * jitter) * 100) / 100,
    );
  };
  return [
    {
      id: "fill_rate",
      label: "Fill rate",
      value: 96.4,
      unit: "%",
      precision: 1,
      series: series(96, 4, 11),
      trend: "up",
      polarity: "higher-better",
      trackRecord: 0.91,
    },
    {
      id: "waste_rate",
      label: "Waste rate",
      value: 2.8,
      unit: "%",
      precision: 1,
      series: series(3, 1.5, 22),
      trend: "down",
      polarity: "lower-better",
    },
    {
      id: "delivery_p95",
      label: "Delivery p95",
      value: 11.6,
      unit: "min",
      precision: 1,
      series: series(11.5, 3, 33),
      trend: "flat",
      polarity: "lower-better",
    },
    {
      id: "on_time",
      label: "On-time",
      value: 94.2,
      unit: "%",
      precision: 1,
      series: series(94, 5, 44),
      trend: "up",
      polarity: "higher-better",
    },
    {
      id: "escalation_rate",
      label: "Escalations / h",
      value: 4,
      unit: "",
      precision: 0,
      series: series(5, 6, 55),
      trend: "down",
      polarity: "lower-better",
    },
    {
      id: "co2",
      label: "CO₂ / delivery",
      value: 0.82,
      unit: "kg",
      precision: 2,
      series: series(0.85, 0.3, 66),
      trend: "down",
      polarity: "lower-better",
    },
  ];
}

export function makeTierDistribution(): TierDistribution {
  return { tier_1: 0.83, tier_2: 0.11, tier_3: 0.05, tier_4: 0.01 };
}

export function makeAuditRow(id: string): AuditRow {
  const decisionId = id.replace(/^audit-/, "");
  const decision = makeDecision(decisionId);
  const r = rng(hashString(id));
  const hash = Array.from({ length: 16 }, () => Math.floor(r() * 16).toString(16)).join(
    "",
  );
  return {
    id,
    decision,
    contentHash: hash,
    immutableSince: decision.createdAt + decision.latencyMs + 1200,
    trace: [
      `tier=${decision.tier}`,
      `phase=${decision.contextMessages.length}`,
      `audit_id=${id}`,
      `confidence=${decision.confidence.toFixed(2)}`,
      `escalated=${decision.escalated}`,
    ],
  };
}

export function makeAuditTimeline(count: number, city?: City): AuditTimelineEntry[] {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const decisionId = `dec-hist-${i}`;
    const d = makeDecision(decisionId, { city, createdAt: now - i * 220_000 });
    return {
      auditId: `audit-${decisionId}`,
      decisionId,
      tier: d.tier,
      escalated: d.escalated,
      createdAt: d.createdAt,
      summary: d.summary,
    };
  });
}
