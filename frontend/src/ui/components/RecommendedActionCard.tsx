import { PayloadRenderer } from "@/aux/payload-renderers";
import type { AgentProposal, Escalation } from "@/domain/decision";
import { AgentSigil } from "@/ui/icons";
import { AGENT_LABEL } from "@/ui/icons/AgentSigil";
import { cn } from "@/ui/lib/cn";
import { Card, CardBody, CardHeader, CardTitle } from "@/ui/primitives";

/**
 * RecommendedActionCard — the orchestrator's selected action.
 *
 * Renders the payload through generative UI (section 6.1), the
 * structured justification ("Why this"), and a 7-day track-record bar
 * for the recommending agent — the trust-calibration delta (tenet T-8).
 */

export interface RecommendedActionCardProps {
  escalation: Escalation;
  /** The recommending agent's proposal, for the justification trace. */
  proposal: AgentProposal | undefined;
  /** 7-day in-band accuracy for this action type, 0..1. */
  trackRecord: number;
  className?: string;
}

export function RecommendedActionCard({
  escalation,
  proposal,
  trackRecord,
  className,
}: RecommendedActionCardProps) {
  return (
    <Card tone="elevated" className={cn("flex flex-col", className)}>
      <CardHeader>
        <CardTitle>Recommended action</CardTitle>
        <span className="flex items-center gap-1.5">
          <AgentSigil agent={escalation.recommendedAgent} size={16} />
          <span className="text-2xs text-ink-secondary">
            {AGENT_LABEL[escalation.recommendedAgent]}
          </span>
        </span>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <PayloadRenderer payload={escalation.recommendedAction} />

        {proposal && proposal.justificationTrace.length > 0 && (
          <div>
            <h4 className="mb-1 font-display text-2xs font-semibold uppercase tracking-[0.1em] text-ink-hint">
              Why this
            </h4>
            <ul className="flex flex-col gap-0.5">
              {proposal.justificationTrace.map((line) => (
                <li key={line} className="text-2xs text-ink-secondary">
                  • {line}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Trust calibration — the agent's recent track record. */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <h4 className="font-display text-2xs font-semibold uppercase tracking-[0.1em] text-ink-hint">
              7-day track record
            </h4>
            <span className="tnum font-mono text-2xs text-ink-secondary">
              {(trackRecord * 100).toFixed(0)}% in-band
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-membrane">
            <div
              className="h-full rounded-full bg-sig-trace"
              style={{ width: `${trackRecord * 100}%` }}
            />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
