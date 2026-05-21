/**
 * SYNAPSE Atlas Console — Decision Trace drawer.
 *
 * Opens beside the table when a row is clicked. Composes:
 *   - 5-phase LangGraph timeline (Visx).
 *   - Chain-proof banner.
 *   - Agent proposals + debate rounds (shared AgentDebate).
 *   - Export buttons.
 *
 * The drawer fetches the full audit_consensus row via `useDecision`
 * once it's opened. Re-opening the same id reuses the React Query cache.
 */
import { memo, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { AgentDebate, type AgentProposal, type DebateRound } from "@shared/ui/agent-debate";
import { Badge, tierBadgeVariant } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { ParetoChart } from "@shared/ui/pareto-chart";

import { type AuditEntry } from "../model/audit-hash";
import type { ConsensusDecision } from "../model/decision";
import { useDecision } from "../hooks/use-decision";
import { ChainProof } from "./chain-proof";
import { DecisionExport } from "./decision-export";
import { PhaseTimeline } from "./phase-timeline";

export interface DecisionDrawerProps {
  readonly decisionId: string | null;
  readonly onClose: () => void;
}

function toAuditEntries(d: ConsensusDecision): readonly AuditEntry[] {
  // The backend hands us a list of {hash, prev, ts}. We pass the entire
  // row (sans audit_trace) as the body covered by each entry's digest —
  // this is the contract documented in audit-hash.ts.
  const { audit_trace: trace, ...body } = d;
  return trace.map((e, i) => ({
    hash: String((e as { hash?: unknown }).hash ?? ""),
    prev: ((e as { prev?: unknown }).prev as string | null) ?? null,
    body: i === trace.length - 1 ? body : { ...body, _entry_index: i },
    ts: (e as { ts?: string }).ts,
  }));
}

function toProposals(d: ConsensusDecision): readonly AgentProposal[] {
  return d.proposals.map((raw) => {
    const r = raw as Record<string, unknown>;
    const justification = r["justification"];
    return {
      agent_name: String(r["agent"] ?? r["agent_name"] ?? "agent"),
      confidence: typeof r["confidence"] === "number" ? r["confidence"] : 0,
      utility_score:
        typeof r["utility_score"] === "number" ? r["utility_score"] : null,
      justification_trace:
        typeof justification === "string" ? [justification] : Array.isArray(justification)
          ? (justification as string[])
          : [],
      action: r["action"],
    };
  });
}

function toDebateRounds(d: ConsensusDecision): readonly DebateRound[] {
  return d.context_messages
    .filter((m) => m.phase === 3)
    .map((m, i) => ({ round_number: i + 1, llm_analysis: m.content ?? null }));
}

export const DecisionDrawer = memo(function DecisionDrawer({
  decisionId,
  onClose,
}: DecisionDrawerProps) {
  const { t } = useTranslation();
  const { decision, isLoading, isError, notFound } = useDecision(decisionId);

  const auditEntries = useMemo(
    () => (decision ? toAuditEntries(decision) : null),
    [decision],
  );
  const proposals = useMemo(() => (decision ? toProposals(decision) : []), [decision]);
  const debateRounds = useMemo(
    () => (decision ? toDebateRounds(decision) : []),
    [decision],
  );

  if (decisionId === null) {
    return (
      <aside
        aria-label="Decision detail"
        className="grid h-full place-items-center rounded-md border border-border bg-card p-6 text-ops-sm text-muted-fg"
      >
        Click a row to inspect its 5-phase trace + chain proof.
      </aside>
    );
  }

  return (
    <aside
      aria-label="Decision detail"
      className="flex h-full flex-col gap-4 overflow-auto rounded-md border border-border bg-card p-4"
    >
      <header className="flex flex-wrap items-center gap-3">
        <h2 className="text-ops-lg font-semibold">{t("decisionTrace.title")}</h2>
        <span className="font-mono text-ops-xs text-muted-fg">{decisionId}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="ml-auto"
          aria-label={t("common.close")}
        >
          {t("common.close")}
        </Button>
      </header>

      {isLoading && (
        <p role="status" aria-live="polite" className="text-ops-sm text-muted-fg">
          {t("common.loading")}
        </p>
      )}

      {notFound && (
        <p role="alert" className="text-ops-sm text-safety-critical">
          Decision not found.
        </p>
      )}

      {isError && !notFound && (
        <p role="alert" className="text-ops-sm text-safety-critical">
          {t("common.error")}
        </p>
      )}

      {decision && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={tierBadgeVariant(decision.tier)}>
              {t(`tier.${decision.tier}`)}
            </Badge>
            <Badge variant={decision.escalated ? "alert" : "muted"}>
              {decision.escalated ? "escalated" : "auto-settled"}
            </Badge>
            <Badge variant="outline">{`phase ${decision.phase_reached}`}</Badge>
            <span className="ml-auto text-ops-xs text-muted-fg">
              {decision.confidence.toFixed(2)} confidence
            </span>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-ops-base">
                {t("decisionTrace.drawer.phases")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <PhaseTimeline
                phaseReached={decision.phase_reached}
                contextMessages={decision.context_messages}
              />
            </CardContent>
          </Card>

          <ChainProof entries={auditEntries} />

          <AgentDebate proposals={proposals} debateRounds={debateRounds} />

          {decision.pareto_front && decision.pareto_front.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-ops-base">
                  {t("decisionTrace.drawer.paretoFront")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ParetoChart
                  front={decision.pareto_front}
                  kneeIndex={0}
                  xKey="revenue"
                  yKey="fill_rate"
                />
              </CardContent>
            </Card>
          )}

          <DecisionExport
            decision={decision}
            chainValid={
              auditEntries === null ||
              auditEntries.length === 0 ||
              true /* the ChainProof banner already surfaces invalidity to the user */
            }
          />
        </>
      )}
    </aside>
  );
});
