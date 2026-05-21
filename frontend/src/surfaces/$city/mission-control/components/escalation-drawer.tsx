/**
 * SYNAPSE Atlas Console — Mission Control detail drawer.
 *
 * Renders alongside the queue when a card is focused. Shows:
 *   - Full agent proposals (uses the shared AgentDebate primitive).
 *   - Pareto front scatter with knee point (Recharts; Visx swap in S6
 *     hardening).
 *   - Debate-round transcript (composed by AgentDebate too).
 *   - KV-cache hit indicator (I-13 — present when the orchestrator
 *     attached `cache_hit` metadata).
 *
 * No close button — focus management lives in the queue. The drawer
 * is just a panel that swaps content based on the focused decision.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { AgentDebate, type AgentProposal, type DebateRound } from "@shared/ui/agent-debate";
import { Badge, tierBadgeVariant } from "@shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { ParetoChart, type ParetoPoint } from "@shared/ui/pareto-chart";

import type { Escalation } from "../model/escalation";

export interface EscalationDrawerProps {
  readonly escalation: Escalation | null;
  /** Optional Pareto front; the orchestrator may not attach one to escalations. */
  readonly paretoFront?: readonly ParetoPoint[];
  readonly paretoKneeIndex?: number;
  /** Optional debate-round transcript. */
  readonly debateRounds?: readonly DebateRound[];
  /** Optional KV-cache (I-13) hit signal. */
  readonly kvCacheHit?: boolean;
}

export const EscalationDrawer = memo(function EscalationDrawer({
  escalation,
  paretoFront,
  paretoKneeIndex,
  debateRounds,
  kvCacheHit,
}: EscalationDrawerProps) {
  const { t } = useTranslation();
  if (!escalation) {
    return (
      <aside
        aria-label="Escalation detail"
        className="flex h-full items-center justify-center rounded-md border border-border bg-card p-6 text-ops-sm text-muted-fg"
      >
        Select an escalation to inspect its proposals + Pareto front.
      </aside>
    );
  }

  // Adapt the wire-format proposal to the shared AgentDebate shape.
  const proposals: readonly AgentProposal[] = escalation.proposals.map((p) => ({
    agent_name: p.agent,
    confidence: p.confidence,
    justification_trace: p.justification ? [p.justification] : [],
    action: p.action,
  }));

  return (
    <aside
      aria-label="Escalation detail"
      className="flex h-full flex-col gap-4 overflow-auto rounded-md border border-border bg-card p-4"
    >
      <header className="flex flex-wrap items-center gap-2">
        <Badge variant={tierBadgeVariant(escalation.tier)}>
          {t(`tier.${escalation.tier}`)}
        </Badge>
        <span className="font-mono text-ops-xs text-muted-fg">
          {escalation.decision_id}
        </span>
        {kvCacheHit !== undefined && (
          <Badge variant={kvCacheHit ? "ok" : "muted"} className="ml-auto">
            KV-cache {kvCacheHit ? "hit" : "miss"}
          </Badge>
        )}
      </header>

      <AgentDebate proposals={proposals} debateRounds={debateRounds} />

      {paretoFront && paretoFront.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-ops-base">
              {t("decisionTrace.drawer.paretoFront")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ParetoChart
              front={paretoFront}
              kneeIndex={paretoKneeIndex ?? 0}
              xKey={firstNumericKey(paretoFront[0]) ?? "x"}
              yKey={secondNumericKey(paretoFront[0]) ?? "y"}
            />
          </CardContent>
        </Card>
      )}
    </aside>
  );
});

function numericKeys(point: ParetoPoint): string[] {
  return Object.keys(point).filter((k) => typeof point[k] === "number");
}

function firstNumericKey(point: ParetoPoint | undefined): string | undefined {
  if (!point) return undefined;
  return numericKeys(point)[0];
}

function secondNumericKey(point: ParetoPoint | undefined): string | undefined {
  if (!point) return undefined;
  return numericKeys(point)[1];
}
