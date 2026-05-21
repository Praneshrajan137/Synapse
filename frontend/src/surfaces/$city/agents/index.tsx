/**
 * SYNAPSE Atlas Console — Agent Floor route (S4 deep work).
 *
 * Plan §5.5: 8 panels driven entirely by `virtual:atlas/agent-specs`.
 * Adding a new agent is a 1-PR change: drop `agents/<name>/spec.yaml`
 * and the panel materialises on the next dev refresh.
 *
 * Live data wiring at S4:
 *   - `useAgentStatuses` (10s poll) → health pill.
 *   - Compliance defaults to `pass` until the Prometheus derivation
 *     ships (S6 hardening). Surface still renders the structure.
 *   - Reward + latency series are fixture seeds for now; the live
 *     /metrics scrape lands alongside the Grafana dashboards in S6.
 */
import { createFileRoute, useParams } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { agentSpecs, type AgentSpec } from "virtual:atlas/agent-specs";

import { useAgentStatuses, specNameToSlug } from "./hooks/use-agent-statuses";
import { AgentDetailDrawer } from "./components/agent-detail-drawer";
import { AgentPanel } from "./components/agent-panel";
import { deriveCompliance, type ComplianceSummary } from "./model/compliance";
import type { TierLatency } from "./components/latency-vs-sla";

export const Route = createFileRoute("/$city/agents/")({
  component: AgentFloor,
});

const ZERO_REWARD: readonly number[] = [];

const ZERO_LATENCY: readonly TierLatency[] = [
  { tier: "tier_1", p99_ms: null },
  { tier: "tier_2", p99_ms: null },
  { tier: "tier_3", p99_ms: null },
  { tier: "tier_4", p99_ms: null },
];

function AgentFloor() {
  const { t } = useTranslation();
  const { city } = useParams({ from: "/$city/agents/" });
  const { statuses } = useAgentStatuses();

  // One compliance summary per agent — recomputed only when specs identity
  // changes (which happens on HMR after a spec.yaml edit).
  const compliances = useMemo<Record<string, ComplianceSummary>>(() => {
    const out: Record<string, ComplianceSummary> = {};
    for (const spec of agentSpecs) {
      out[spec.agent_name] = deriveCompliance(spec);
    }
    return out;
  }, []);

  const [openSpec, setOpenSpec] = useState<AgentSpec | null>(null);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-ops-xl font-bold tracking-tight">{t("agentFloor.title")}</h1>
        <p className="text-ops-sm text-muted-fg">
          {t(`city.${city}`)} · {agentSpecs.length} agents derived from spec.yaml
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {agentSpecs.map((spec) => {
          const slug = specNameToSlug(spec.agent_name);
          const health = statuses[slug];
          const compliance = compliances[spec.agent_name];
          if (!compliance) return null;
          return (
            <AgentPanel
              key={spec.agent_name}
              spec={spec}
              health={health}
              compliance={compliance}
              rewardSeries={ZERO_REWARD}
              latency={ZERO_LATENCY}
              currentState={spec.state_machine.initial_state}
              onOpenDetails={() => setOpenSpec(spec)}
            />
          );
        })}
      </div>

      <AgentDetailDrawer
        spec={openSpec}
        compliance={openSpec ? compliances[openSpec.agent_name] ?? null : null}
        cityId={city}
        onOpenChange={(o) => {
          if (!o) setOpenSpec(null);
        }}
      />
    </div>
  );
}
