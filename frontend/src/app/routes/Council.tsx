import { useEscalations } from "@/application/decisions";
import { PayloadRenderer } from "@/aux-ui/payload-renderers";
import { ContextTape } from "@/ui/components/ContextTape";
import { CounterfactualPanel } from "@/ui/components/CounterfactualPanel";
import { EscalationHeader } from "@/ui/components/EscalationHeader";
import { ProposalLadder } from "@/ui/components/ProposalLadder";
import { RecommendedActionCard } from "@/ui/components/RecommendedActionCard";
import { useNow } from "@/ui/hooks/useNow";
import { AGENT_LABEL } from "@/ui/icons/AgentSigil";
import { Card, CardBody, CardHeader, CardTitle } from "@/ui/primitives";
import type { AgentName } from "@/ui/tokens";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

/**
 * Council — the HITL override surface. A single escalated decision,
 * interrogated and resolved inside the 300-second window
 * (plan section 5.3).
 */
export default function Council() {
  const params = useParams<{ decisionId?: string }>();
  const { data: escalations, isLoading } = useEscalations();
  const now = useNow(1000);
  const [selectedAgent, setSelectedAgent] = useState<AgentName | null>(null);

  const escalation =
    escalations?.find((e) => e.decision.id === params.decisionId) ?? escalations?.[0];

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-hint">
        Loading escalations…
      </div>
    );
  }

  if (!escalation) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <ShieldCheck size={32} className="text-sig-ok" aria-hidden="true" />
        <p className="text-sm text-ink-primary">No decisions awaiting human action</p>
        <p className="text-2xs text-ink-hint">
          Every decision is within its confidence threshold.
        </p>
      </div>
    );
  }

  const decision = escalation.decision;
  const recommendedProposal = decision.proposals.find(
    (p) => p.agentName === escalation.recommendedAgent,
  );
  const trackRecord = Math.min(
    0.97,
    0.6 + (recommendedProposal?.confidence ?? 0.5) * 0.35,
  );
  const selectedProposal = decision.proposals.find((p) => p.agentName === selectedAgent);

  return (
    <div className="flex h-full flex-col">
      <EscalationHeader escalation={escalation} now={now} />

      <div className="flex min-h-0 flex-1">
        <ProposalLadder
          proposals={decision.proposals}
          selectedAgent={selectedAgent}
          onSelect={(a) => setSelectedAgent((cur) => (cur === a ? null : a))}
          className="w-72 shrink-0 border-r border-line-faint"
        />

        <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          <RecommendedActionCard
            escalation={escalation}
            proposal={recommendedProposal}
            trackRecord={trackRecord}
          />
          {selectedProposal &&
            selectedProposal.agentName !== escalation.recommendedAgent && (
              <Card accent="var(--color-sig-think)">
                <CardHeader>
                  <CardTitle>
                    {AGENT_LABEL[selectedProposal.agentName]} · alternative
                  </CardTitle>
                  <span className="font-mono text-2xs text-ink-hint">
                    u {selectedProposal.utilityScore.toFixed(2)}
                  </span>
                </CardHeader>
                <CardBody>
                  <PayloadRenderer payload={selectedProposal.action} />
                </CardBody>
              </Card>
            )}
        </div>

        <CounterfactualPanel
          escalation={escalation}
          className="w-80 shrink-0 border-l border-line-faint"
        />
      </div>

      <ContextTape
        messages={decision.contextMessages.slice(-12)}
        follow={false}
        className="h-44 shrink-0 border-t border-line-faint"
      />
    </div>
  );
}
