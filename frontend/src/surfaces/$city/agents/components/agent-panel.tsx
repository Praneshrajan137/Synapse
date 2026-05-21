/**
 * SYNAPSE Atlas Console — Agent Floor panel (one per spec.yaml).
 *
 * Composes:
 *   - Title row with state-machine viz (current state highlighted).
 *   - Compliance summary (counts + open list of failures).
 *   - Reward sparkline (24 h).
 *   - Tier-latency vs SLA mini chart.
 *   - Health pill (from `/api/v1/agents/`).
 *
 * Click → drawer with the full compliance checklist + reachable
 * states. Plan §5.5 acceptance: panel is generated from the spec, not
 * hand-coded.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";
import type { AgentSpec } from "virtual:atlas/agent-specs";

import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { cn } from "@shared/ui/cn";

import { type ComplianceSummary } from "../model/compliance";
import { ComplianceChecklist } from "./compliance-checklist";
import { LatencyVsSla, type TierLatency } from "./latency-vs-sla";
import { RewardSparkline } from "./reward-sparkline";
import { StateMachineViz } from "./state-machine-viz";

export interface AgentPanelProps {
  readonly spec: AgentSpec;
  readonly health: string | undefined;
  readonly compliance: ComplianceSummary;
  readonly rewardSeries: readonly number[];
  readonly latency: readonly TierLatency[];
  readonly currentState?: string;
  readonly onOpenDetails: () => void;
}

export const AgentPanel = memo(function AgentPanel({
  spec,
  health,
  compliance,
  rewardSeries,
  latency,
  currentState,
  onOpenDetails,
}: AgentPanelProps) {
  const { t } = useTranslation();
  const healthVariant: "ok" | "warn" | "critical" =
    health === "ok" ? "ok" : health ? "warn" : "critical";

  // Top-3 failing items for the at-a-glance view; the drawer shows everything.
  const topFailures = compliance.items
    .filter((i) => i.status !== "pass")
    .slice(0, 3);

  return (
    <Card
      className={cn(
        "h-full",
        compliance.hasCriticalFailures && "border-safety-critical/60",
      )}
    >
      <CardHeader>
        <CardTitle className="flex items-start gap-3 text-ops-base">
          <span className="flex flex-col">
            <span>{t(`agentFloor.agents.${spec.agent_name}`)}</span>
            <span className="text-ops-xs font-normal text-muted-fg">v{spec.version}</span>
          </span>
          <Badge variant={healthVariant} className="ml-auto">
            {health ?? "unreachable"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 lg:grid-cols-[180px_1fr]">
        <StateMachineViz spec={spec} currentState={currentState} />
        <div className="flex flex-col gap-3">
          <RewardSparkline series={rewardSeries} width={260} height={32} />
          <LatencyVsSla rows={latency} />
          <div className="flex flex-wrap gap-2">
            <Badge variant="ok">{compliance.counts.pass} pass</Badge>
            {compliance.counts.watch > 0 && (
              <Badge variant="warn">{compliance.counts.watch} watch</Badge>
            )}
            {compliance.counts.fail > 0 && (
              <Badge variant="critical">{compliance.counts.fail} fail</Badge>
            )}
          </div>
          {topFailures.length > 0 && (
            <ComplianceChecklist
              summary={{
                items: topFailures,
                counts: compliance.counts,
                hasFailures: true,
                hasCriticalFailures: compliance.hasCriticalFailures,
              }}
              compact
            />
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenDetails}
            className="self-start"
            aria-label={`Open details for ${spec.agent_name}`}
          >
            Details →
          </Button>
        </div>
      </CardContent>
    </Card>
  );
});
