import { cn } from "@lib/cn";
import { ConfidenceChip } from "./ConfidenceChip";

interface AgentProposalChipProps {
  readonly agentName: string;
  readonly utilityScore?: number | undefined;
  readonly confidence?: number | undefined;
  readonly status?: "proposed" | "rejected" | "selected" | "modified" | undefined;
  readonly isWinner?: boolean | undefined;
  readonly className?: string | undefined;
  readonly onClick?: (() => void) | undefined;
}

const STATUS_CLASS = {
  proposed: "border-border",
  rejected: "border-confidence-risk/40 opacity-60",
  selected: "border-accent ring-1 ring-accent/40",
  modified: "border-signal-warning/40",
} as const;

/**
 * One agent's proposal at a glance. Renders in the Cockpit / Decision Theater
 * proposal row and the Reasoning Timeline. FE-INV-018 (P3) will gate which
 * tool chips appear under here based on tier.
 */
export function AgentProposalChip({
  agentName,
  utilityScore,
  confidence,
  status = "proposed",
  isWinner = false,
  className,
  onClick,
}: AgentProposalChipProps) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      {...(onClick ? { type: "button" as const } : {})}
      onClick={onClick}
      className={cn(
        "syn-card-raised flex flex-col gap-1 p-3 text-left text-sm transition-colors duration-fast ease-standard",
        STATUS_CLASS[status],
        isWinner && "border-accent",
        onClick && "hover:bg-surface",
        className,
      )}
      aria-label={`Agent ${agentName} proposal${isWinner ? ", selected" : ""}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold capitalize text-ink">
          {agentName.replace(/_/g, " ")}
        </span>
        {confidence !== undefined && <ConfidenceChip value={confidence} />}
      </div>
      {utilityScore !== undefined && (
        <div className="text-2xs text-ink-muted">
          Utility <span className="font-mono text-ink">{utilityScore.toFixed(3)}</span>
        </div>
      )}
      {isWinner && (
        <span className="self-start rounded bg-accent/15 px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide text-accent">
          Selected
        </span>
      )}
    </Tag>
  );
}
