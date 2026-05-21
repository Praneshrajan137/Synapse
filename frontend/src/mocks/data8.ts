import type { City } from "@/domain/city";
import type { AgentDetail, KafkaTopic, TopicClass } from "@/domain/observability";
import type {
  KpiDistribution,
  MonteCarloResult,
  ShockParams,
  ShockScenario,
  TwinEdge,
  TwinNode,
  TwinTopology,
} from "@/domain/twin";
import type { AgentName } from "@/ui/tokens";
import { makeRecentDecisions } from "./data";

/**
 * Mock data for the Phase 8 surfaces — Twin, Inspector and Streams.
 * Deterministic per input so views are stable across renders.
 */

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

function hash(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/* ---- Twin topology ---------------------------------------------------- */

export function makeTopology(city: City): TwinTopology {
  const r = rng(hash(`topology-${city}`));
  const prefix = city === "mumbai" ? "MUM" : "BLR";
  const nodes: TwinNode[] = [];
  const edges: TwinEdge[] = [];

  const suppliers = 4;
  const warehouses = 3;
  const stores = 16;

  for (let i = 0; i < suppliers; i += 1) {
    nodes.push({
      id: `${prefix}-SUP-${i + 1}`,
      kind: "supplier",
      label: `Supplier ${i + 1}`,
      x: 0.08,
      y: 0.15 + (i / (suppliers - 1)) * 0.7,
      stress: r() * 0.5,
    });
  }
  for (let i = 0; i < warehouses; i += 1) {
    nodes.push({
      id: `${prefix}-WH-${i + 1}`,
      kind: "warehouse",
      label: `Warehouse ${i + 1}`,
      x: 0.34,
      y: 0.22 + (i / (warehouses - 1)) * 0.56,
      stress: r() * 0.6,
    });
  }
  for (let i = 0; i < stores; i += 1) {
    const col = i % 4;
    const row = Math.floor(i / 4);
    nodes.push({
      id: `${prefix}-S-${String(i + 1).padStart(3, "0")}`,
      kind: "store",
      label: `Store ${i + 1}`,
      x: 0.6 + col * 0.12 + (r() - 0.5) * 0.05,
      y: 0.16 + row * 0.22 + (r() - 0.5) * 0.05,
      stress: r(),
    });
  }

  const supplierNodes = nodes.filter((n) => n.kind === "supplier");
  const warehouseNodes = nodes.filter((n) => n.kind === "warehouse");
  const storeNodes = nodes.filter((n) => n.kind === "store");

  for (const s of supplierNodes) {
    for (const w of warehouseNodes) {
      if (r() > 0.4) edges.push({ from: s.id, to: w.id });
    }
  }
  for (const store of storeNodes) {
    const w = warehouseNodes[Math.floor(r() * warehouseNodes.length)];
    if (w) edges.push({ from: w.id, to: store.id });
  }

  return { nodes, edges };
}

/* ---- Monte Carlo what-if --------------------------------------------- */

const MC_KPIS: {
  id: string;
  label: string;
  unit: string;
  baseline: number;
  lowerBetter: boolean;
}[] = [
  { id: "fill_rate", label: "Fill rate", unit: "%", baseline: 96, lowerBetter: false },
  { id: "waste_rate", label: "Waste rate", unit: "%", baseline: 2.8, lowerBetter: true },
  {
    id: "delivery_p95",
    label: "Delivery p95",
    unit: "min",
    baseline: 11.6,
    lowerBetter: true,
  },
  { id: "on_time", label: "On-time", unit: "%", baseline: 94, lowerBetter: false },
  { id: "co2", label: "CO₂ / delivery", unit: "kg", baseline: 0.82, lowerBetter: true },
];

export function makeMonteCarlo(
  scenario: ShockScenario,
  params: ShockParams,
): MonteCarloResult {
  const r = rng(hash(`${scenario}-${JSON.stringify(params)}`));
  const stress =
    (params.demand - 1) * 0.4 +
    (params.leadTime - 1) * 0.3 +
    params.failureRate * 0.2 +
    params.spoilage * 0.1;

  const distributions: KpiDistribution[] = MC_KPIS.map((kpi) => {
    const direction = kpi.lowerBetter ? 1 : -1;
    const shift = kpi.baseline * stress * 0.18 * direction;
    const spread = kpi.baseline * (0.04 + stress * 0.06);
    const p50 = kpi.baseline + shift + (r() - 0.5) * spread * 0.4;
    return {
      id: kpi.id,
      label: kpi.label,
      unit: kpi.unit,
      baseline: kpi.baseline,
      p5: Math.round((p50 - spread) * 100) / 100,
      p50: Math.round(p50 * 100) / 100,
      p95: Math.round((p50 + spread) * 100) / 100,
    };
  });

  return { scenarioCount: 1000, distributions };
}

/* ---- Agent detail ---------------------------------------------------- */

const REWARD_FUNCTIONS: Record<AgentName, string> = {
  demand_prophet: "reward = -MAPE − 0.2·band_violation",
  routing_navigator: "reward = -total_time − 0.3·fairness_gap",
  inventory_sentinel: "reward = fill_rate − 0.5·holding_cost",
  freshness_guardian: "reward = -spoilage − 0.4·markdown_loss",
  pricing_oracle: "reward = margin − 0.6·cap_violation",
  disruption_shield: "reward = recovery_speed − 0.3·false_alarm",
  supplier_trust: "reward = -lead_time_error − 0.2·score_drift",
  sustainability_agent: "reward = -carbon − 0.3·food_waste",
};

export function makeAgentDetail(name: AgentName): AgentDetail {
  const r = rng(hash(`agent-${name}`));
  let reward = -0.8;
  const rewardCurve = Array.from({ length: 40 }, () => {
    reward += 0.06 - reward * 0.04 + (r() - 0.5) * 0.08;
    return Math.round(reward * 1000) / 1000;
  });
  const confidenceHistogram = Array.from({ length: 10 }, (_, i) =>
    Math.round((r() * 0.5 + (i > 6 ? 0.5 : 0.1)) * 100),
  );

  return {
    name,
    rewardFunction: REWARD_FUNCTIONS[name],
    p50LatencyMs: Math.round(20 + r() * 60),
    p99LatencyMs: Math.round(120 + r() * 380),
    decisionsPerMin: Math.round(8 + r() * 90),
    rewardCurve,
    confidenceHistogram,
    recentDecisions: makeRecentDecisions(8).map((d) => ({ ...d, leadAgent: name })),
    topicsProduced: [`synapse.${name.split("_")[0]}.update`],
    topicsConsumed: ["synapse.orchestrator.decision", "synapse.metrics.agent"],
    ...(name === "demand_prophet"
      ? {
          conformal: [
            { horizon: "15m", target: 0.9, actual: 0.91 },
            { horizon: "1h", target: 0.9, actual: 0.89 },
            { horizon: "6h", target: 0.9, actual: 0.88 },
            { horizon: "24h", target: 0.9, actual: 0.92 },
            { horizon: "7d", target: 0.9, actual: 0.86 },
          ],
        }
      : {}),
  };
}

/* ---- Kafka topics ---------------------------------------------------- */

const TOPIC_SPECS: {
  name: string;
  partitions: number;
  retentionHours: number;
  topicClass: TopicClass;
}[] = [
  {
    name: "synapse.demand.forecast",
    partitions: 8,
    retentionHours: 72,
    topicClass: "agent",
  },
  {
    name: "synapse.demand.drift_alert",
    partitions: 1,
    retentionHours: 24,
    topicClass: "agent",
  },
  {
    name: "synapse.routing.plan",
    partitions: 8,
    retentionHours: 24,
    topicClass: "agent",
  },
  {
    name: "synapse.inventory.state",
    partitions: 8,
    retentionHours: 72,
    topicClass: "agent",
  },
  {
    name: "synapse.inventory.reorder",
    partitions: 4,
    retentionHours: 48,
    topicClass: "agent",
  },
  {
    name: "synapse.pricing.update",
    partitions: 4,
    retentionHours: 24,
    topicClass: "agent",
  },
  {
    name: "synapse.disruption.alert",
    partitions: 2,
    retentionHours: 168,
    topicClass: "agent",
  },
  {
    name: "synapse.disruption.playbook",
    partitions: 2,
    retentionHours: 168,
    topicClass: "agent",
  },
  {
    name: "synapse.supplier.score",
    partitions: 2,
    retentionHours: 168,
    topicClass: "agent",
  },
  {
    name: "synapse.sustainability.carbon",
    partitions: 2,
    retentionHours: 168,
    topicClass: "agent",
  },
  {
    name: "synapse.freshness.alert",
    partitions: 4,
    retentionHours: 24,
    topicClass: "agent",
  },
  {
    name: "synapse.orchestrator.decision",
    partitions: 4,
    retentionHours: 720,
    topicClass: "orchestrator",
  },
  {
    name: "synapse.orchestrator.escalation",
    partitions: 1,
    retentionHours: 720,
    topicClass: "hitl",
  },
  {
    name: "synapse.twin.divergence",
    partitions: 1,
    retentionHours: 168,
    topicClass: "telemetry",
  },
  { name: "synapse.audit.log", partitions: 4, retentionHours: 8760, topicClass: "audit" },
  {
    name: "synapse.metrics.agent",
    partitions: 8,
    retentionHours: 24,
    topicClass: "telemetry",
  },
];

export function makeTopics(): KafkaTopic[] {
  return TOPIC_SPECS.map((spec) => {
    const r = rng(hash(spec.name));
    return {
      ...spec,
      messagesPerSec: Math.round(r() * 240 * 10) / 10,
      consumerLag: Math.floor(r() * r() * 800),
    };
  });
}
