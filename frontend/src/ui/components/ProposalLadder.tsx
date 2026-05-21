import type { AgentProposal } from "@/domain/decision";
import { AgentSigil } from "@/ui/icons";
import { AGENT_LABEL } from "@/ui/icons/AgentSigil";
import { cn } from "@/ui/lib/cn";
import { type AgentName, agentColor } from "@/ui/tokens";

/**
 * ProposalLadder — every agent proposal for the decision, ranked by
 * utility. Selecting a rung surfaces its full justification and action.
 */

export interface ProposalLadderProps {
  proposals: readonly AgentProposal[];
  selectedAgent: AgentName | null;
  onSelect: (agent: AgentName) => void;
  className?: string;
}

export function ProposalLadder({
  proposals,
  selectedAgent,
  onSelect,
  className,
}: ProposalLadderProps) {
  const ranked = [...proposals].sort((a, b) => b.utilityScore - a.utilityScore);

  return (
    <section
      aria-label="Agent proposals"
      className={cn("flex flex-col bg-paper", className)}
    >
      <header className="flex h-9 shrink-0 items-center border-b border-line-faint px-3">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Proposals · ranked
        </h2>
      </header>
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {ranked.map((proposal, index) => {
          const selected = selectedAgent === proposal.agentName;
          const color = agentColor[proposal.agentName];
          return (
            <li key={proposal.agentName}>
              <button
                type="button"
                onClick={() => onSelect(proposal.agentName)}
                aria-pressed={selected}
                className={cn(
                  "flex w-full items-center gap-2.5 border-b border-line-faint/60 px-3 py-2.5 text-left",
                  "transition-colors hover:bg-elevated/60",
                  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sig-live",
                  selected && "bg-elevated",
                )}
              >
                <span className="w-4 shrink-0 font-mono text-2xs text-ink-disabled">
                  {index + 1}
                </span>
                <AgentSigil agent={proposal.agentName} size={20} />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="truncate text-xs text-ink-primary">
                    {AGENT_LABEL[proposal.agentName]}
                  </span>
                  <div className="flex h-1.5 overflow-hidden rounded-full bg-membrane">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${proposal.utilityScore * 100}%`,
                        backgroundColor: color,
                      }}
                    />
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end">
                  <span className="tnum font-mono text-2xs" style={{ color }}>
                    u {proposal.utilityScore.toFixed(2)}
                  </span>
                  <span className="tnum font-mono text-2xs text-ink-hint">
                    c {proposal.confidence.toFixed(2)}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
