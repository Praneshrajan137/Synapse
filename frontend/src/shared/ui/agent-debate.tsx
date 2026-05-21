/**
 * SYNAPSE Atlas Console — AgentDebate panel (TS port).
 *
 * Renders the proposal grid + debate-round transcript for one decision.
 * Used inside Mission Control's drawer and in Decision Trace's expanded
 * row. Tokens drive colour; ConfidenceGauge re-used.
 */
import { memo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "./card";
import { ConfidenceGauge } from "./confidence-gauge";
import { cn } from "./cn";

export interface AgentProposal {
  readonly agent_name: string;
  readonly confidence: number;
  readonly utility_score?: number | null;
  readonly justification_trace?: readonly string[];
  readonly action?: unknown;
}

export interface DebateRound {
  readonly round_number: number;
  readonly llm_analysis?: string | null;
}

export interface AgentDebateProps {
  readonly proposals: readonly AgentProposal[];
  readonly debateRounds?: readonly DebateRound[];
  readonly className?: string;
}

export const AgentDebate = memo(function AgentDebate({
  proposals,
  debateRounds = [],
  className,
}: AgentDebateProps) {
  return (
    <div className={cn("space-y-6", className)}>
      <section aria-labelledby="agent-proposals-heading">
        <h3 id="agent-proposals-heading" className="mb-3 text-ops-lg font-semibold">
          Agent proposals
        </h3>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
          {proposals.map((p, i) => (
            <Card key={`${p.agent_name}-${i}`}>
              <CardHeader>
                <CardTitle className="text-ops-base">{p.agent_name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <ConfidenceGauge value={p.confidence} size={72} />
                {p.utility_score !== null && p.utility_score !== undefined && (
                  <div className="text-ops-xs text-muted-fg">
                    Utility: {p.utility_score.toFixed(3)}
                  </div>
                )}
                {p.justification_trace?.[0] && (
                  <div className="text-ops-xs text-muted-fg">
                    {p.justification_trace[0]}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {debateRounds.length > 0 && (
        <section aria-labelledby="debate-rounds-heading">
          <h3 id="debate-rounds-heading" className="mb-3 text-ops-lg font-semibold">
            Debate rounds
          </h3>
          <ol className="space-y-2">
            {debateRounds.map((round) => (
              <li key={round.round_number}>
                <Card>
                  <CardContent className="pt-4">
                    <strong className="text-ops-sm">Round {round.round_number}</strong>
                    <p className="mt-1 text-ops-sm text-muted-fg">
                      {round.llm_analysis ?? "No analysis"}
                    </p>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
});
