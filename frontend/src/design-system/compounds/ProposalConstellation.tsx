import {
  AGENT_COLOR_VAR,
  AGENT_INITIALS,
  AGENT_LABEL,
  AGENT_NAMES,
  type AgentName,
} from "@lib/agent-identity";
import { cn } from "@lib/cn";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo } from "react";

// Re-export the frozen registry so existing importers
// (`@ds/compounds/ProposalConstellation`) keep working unchanged. The single
// source of truth now lives in `@lib/agent-identity` (INV-CLR-012).
export { AGENT_NAMES, type AgentName };

/**
 * ProposalConstellation — the eight agents in a fixed radial formation.
 *
 * Fixed angular placement so operators learn the layout: agents stay in
 * the same screen positions across every decision, every render. Node
 * size tracks utility score (0..1 → 38..64 px diameter); node ring colour
 * is the agent's chromatic identity from `--syn-agent-*` (INV-CLR-012,
 * mirroring `design-system/color/tokens/agents.tokens.json`).
 *
 * Revealed nodes spring in with a small per-agent stiffness variation —
 * the agent's "motion signature." Edges to the orchestrator core pulse
 * during the debate phase. `prefers-reduced-motion` collapses both to
 * instantaneous transitions (FE-P6).
 *
 * Used by Mission Control (live decision feed) and Decision Detail
 * (replay phase 1–2). Pairs with `AgentProposalChip` for the tabular
 * list view.
 *
 * @see frontend/spec/fe_invariants.yaml FE-INV-004 (every decision card
 *      carries tier+confidence+reasoning), FE-INV-007 (visual signal
 *      reflects confidence band).
 */

/** Spring tuning — base; per-agent stiffness is offset to stagger reveals. */
const SPRING_BASE = { type: "spring" as const, stiffness: 180, damping: 22 };

/**
 * The shape a `Proposal` from `@domain/consensus-decision` collapses into
 * for this viz. We accept the snake_case BE field directly so callers can
 * pass the parsed Zod payload without remapping.
 */
export interface ProposalLike {
  readonly agent_name?: string | undefined;
  readonly utility_score?: number | undefined;
  readonly confidence?: number | undefined;
}

export interface ProposalConstellationProps {
  /** Proposals to render. Order is irrelevant — agents have fixed positions. */
  readonly proposals: ReadonlyArray<ProposalLike>;
  /**
   * Agents whose proposals have "arrived" and should be drawn at full
   * size/opacity. Other agents render as dimmed placeholders. Omit to
   * derive automatically from `proposals` (an agent is revealed iff it
   * appears in `proposals`).
   */
  readonly revealed?: ReadonlySet<AgentName> | undefined;
  /** True during the debate phase — edges to the core pulse. */
  readonly debating?: boolean | undefined;
  /** Currently selected agent (rendered with a focus ring). */
  readonly selectedAgent?: AgentName | null | undefined;
  /** Click handler. If omitted, the buttons render as `aria-disabled`. */
  readonly onSelectAgent?: ((agent: AgentName) => void) | undefined;
  readonly className?: string | undefined;
}

interface NodeLayout {
  readonly agent: AgentName;
  readonly x: number;
  readonly y: number;
  readonly proposal: ProposalLike | undefined;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

export function ProposalConstellation({
  proposals,
  revealed,
  debating = false,
  selectedAgent = null,
  onSelectAgent,
  className,
}: ProposalConstellationProps) {
  // Framer's hook returns `null` until the media query resolves; treat null
  // as "honour reduced motion" (pessimistic — animation is opt-in not opt-out).
  const reduced = useReducedMotion() ?? false;

  const nodes = useMemo<NodeLayout[]>(() => {
    const byAgent = new Map<string, ProposalLike>();
    for (const p of proposals) {
      if (p.agent_name) byAgent.set(p.agent_name, p);
    }
    return AGENT_NAMES.map((agent, i) => {
      // Fixed angular placement, top-anchored (−π/2) for visual continuity
      // with the existing KPI band header.
      const angle = (i / AGENT_NAMES.length) * Math.PI * 2 - Math.PI / 2;
      return {
        agent,
        x: 50 + Math.cos(angle) * 37,
        y: 50 + Math.sin(angle) * 37,
        proposal: byAgent.get(agent),
      };
    });
  }, [proposals]);

  const isRevealed = (agent: AgentName, proposal: ProposalLike | undefined): boolean => {
    if (revealed) return revealed.has(agent);
    return proposal !== undefined;
  };

  return (
    <figure
      className={cn("relative aspect-square w-full max-w-xl", className)}
      aria-label="Agent proposal constellation — eight specialists in fixed radial formation"
    >
      {/* Edges to the orchestrator core */}
      <svg
        className="absolute inset-0 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {nodes.map((node) =>
          isRevealed(node.agent, node.proposal) ? (
            <g key={node.agent}>
              {/* Static base edge */}
              <line
                x1={50}
                y1={50}
                x2={node.x}
                y2={node.y}
                stroke={AGENT_COLOR_VAR[node.agent]}
                strokeOpacity={0.18}
                strokeWidth={0.4}
              />
              {/* Debate-phase pulse edge */}
              <line
                x1={50}
                y1={50}
                x2={node.x}
                y2={node.y}
                stroke={AGENT_COLOR_VAR[node.agent]}
                strokeWidth={0.5}
                strokeLinecap="round"
                className={debating && !reduced ? "animate-pulse-confidence" : undefined}
                strokeOpacity={debating ? 0.7 : 0}
              />
            </g>
          ) : null,
        )}
      </svg>

      {/* Orchestrator core */}
      <div
        className="absolute flex size-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border-strong bg-surface-raised text-2xs font-mono font-semibold uppercase tracking-wider text-ink"
        style={{ left: "50%", top: "50%" }}
        aria-hidden="true"
      >
        SYN
      </div>

      {/* Agent nodes */}
      {nodes.map((node, i) => {
        const revealedNow = isRevealed(node.agent, node.proposal);
        const utility = clamp01(node.proposal?.utility_score ?? 0);
        const confidence = clamp01(node.proposal?.confidence ?? 0);
        const size = 38 + utility * 26;
        const color = AGENT_COLOR_VAR[node.agent];
        const selected = selectedAgent === node.agent;
        const interactive = Boolean(node.proposal && onSelectAgent);
        const label = node.proposal
          ? `${AGENT_LABEL[node.agent]} — utility ${utility.toFixed(2)}, confidence ${confidence.toFixed(2)}`
          : `${AGENT_LABEL[node.agent]} — no proposal yet`;
        return (
          <motion.button
            key={node.agent}
            type="button"
            disabled={!interactive}
            onClick={interactive ? () => onSelectAgent?.(node.agent) : undefined}
            className={cn(
              "absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full",
              "border bg-surface transition-colors duration-fast ease-standard",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              interactive ? "cursor-pointer" : "cursor-default",
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
              scale: revealedNow ? 1 : 0.7,
              opacity: revealedNow ? 1 : 0.28,
            }}
            transition={
              reduced
                ? { duration: 0 }
                : { ...SPRING_BASE, stiffness: SPRING_BASE.stiffness + i * 12 }
            }
            aria-label={label}
            aria-pressed={selected}
          >
            <span
              className="font-mono text-2xs font-semibold uppercase tracking-wide"
              style={{ color }}
              aria-hidden="true"
            >
              {AGENT_INITIALS[node.agent]}
            </span>
            {node.proposal && revealedNow && (
              <span
                className="absolute -bottom-4 font-mono text-2xs tabular-nums"
                style={{ color }}
                aria-hidden="true"
              >
                {utility.toFixed(2)}
              </span>
            )}
          </motion.button>
        );
      })}
    </figure>
  );
}
