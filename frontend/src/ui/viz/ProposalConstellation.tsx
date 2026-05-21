import type { AgentProposal } from "@/domain/decision";
import { useReducedMotion } from "@/ui/hooks/useReducedMotion";
import { AgentSigil } from "@/ui/icons";
import { AGENT_LABEL } from "@/ui/icons/AgentSigil";
import { cn } from "@/ui/lib/cn";
import { AGENT_NAMES, type AgentName, agentColor, springBase } from "@/ui/tokens";
import { motion } from "motion/react";
import { useMemo } from "react";

/**
 * ProposalConstellation — the eight agents in a fixed radial formation.
 *
 * Fixed angular placement so operators learn the layout (tenet T-5). A
 * node's size tracks its utility score; its ring tracks confidence.
 * Revealed nodes spring in with a slight per-agent variation — the
 * persona's motion signature. Edges to the orchestrator flow during
 * debate.
 */

export interface ProposalConstellationProps {
  proposals: readonly AgentProposal[];
  /** Agents whose proposals have arrived (drives progressive reveal). */
  revealed: ReadonlySet<AgentName>;
  debating: boolean;
  selectedAgent?: AgentName | null;
  onSelectAgent?: (agent: AgentName) => void;
  className?: string;
}

interface NodeLayout {
  agent: AgentName;
  x: number;
  y: number;
  proposal: AgentProposal | undefined;
}

export function ProposalConstellation({
  proposals,
  revealed,
  debating,
  selectedAgent,
  onSelectAgent,
  className,
}: ProposalConstellationProps) {
  const reduced = useReducedMotion();

  const nodes = useMemo<NodeLayout[]>(() => {
    return AGENT_NAMES.map((agent, i) => {
      const angle = (i / AGENT_NAMES.length) * Math.PI * 2 - Math.PI / 2;
      return {
        agent,
        x: 50 + Math.cos(angle) * 37,
        y: 50 + Math.sin(angle) * 37,
        proposal: proposals.find((p) => p.agentName === agent),
      };
    });
  }, [proposals]);

  return (
    <div className={cn("relative aspect-square w-full max-w-xl", className)}>
      {/* Edges to the orchestrator core */}
      <svg
        className="absolute inset-0 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {nodes.map((node) =>
          revealed.has(node.agent) ? (
            <g key={node.agent}>
              <line
                x1={50}
                y1={50}
                x2={node.x}
                y2={node.y}
                stroke={agentColor[node.agent]}
                strokeOpacity={0.18}
                strokeWidth={0.4}
              />
              <line
                x1={50}
                y1={50}
                x2={node.x}
                y2={node.y}
                stroke={agentColor[node.agent]}
                strokeWidth={0.5}
                strokeLinecap="round"
                className={debating ? "animate-flow" : undefined}
                strokeOpacity={debating ? 0.7 : 0}
              />
            </g>
          ) : null,
        )}
      </svg>

      {/* Orchestrator core */}
      <div
        className="absolute flex size-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-line-strong bg-elevated"
        style={{ left: "50%", top: "50%" }}
      >
        <img src="/synapse-mark.svg" alt="" width={22} height={22} />
      </div>

      {/* Agent nodes */}
      {nodes.map((node, i) => {
        const isRevealed = revealed.has(node.agent);
        const utility = node.proposal?.utilityScore ?? 0;
        const confidence = node.proposal?.confidence ?? 0;
        const size = 38 + utility * 26;
        const color = agentColor[node.agent];
        const selected = selectedAgent === node.agent;
        return (
          <motion.button
            key={node.agent}
            type="button"
            disabled={!node.proposal}
            onClick={() => node.proposal && onSelectAgent?.(node.agent)}
            className={cn(
              "absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full",
              "border bg-paper transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
              node.proposal ? "cursor-pointer" : "cursor-default",
            )}
            style={{
              left: `${node.x}%`,
              top: `${node.y}%`,
              width: size,
              height: size,
              borderColor: color,
              borderWidth: selected ? 2 : 1,
              boxShadow: selected
                ? `0 0 0 4px color-mix(in oklab, ${color} 22%, transparent)`
                : "none",
            }}
            initial={reduced ? false : { scale: 0.4, opacity: 0 }}
            animate={{
              scale: isRevealed ? 1 : 0.7,
              opacity: isRevealed ? 1 : 0.28,
            }}
            transition={{ ...springBase, stiffness: springBase.stiffness + i * 12 }}
            aria-label={`${AGENT_LABEL[node.agent]}${
              node.proposal
                ? ` — utility ${utility.toFixed(2)}, confidence ${confidence.toFixed(2)}`
                : " — no proposal"
            }`}
          >
            <AgentSigil agent={node.agent} size={size * 0.5} />
            {node.proposal && isRevealed && (
              <span
                className="tnum absolute -bottom-4 font-mono text-2xs"
                style={{ color }}
              >
                {utility.toFixed(2)}
              </span>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
