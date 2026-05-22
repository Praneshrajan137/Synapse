import { cn } from "@lib/cn";

const PHASES = [
  { id: 1, label: "Proposal" },
  { id: 2, label: "Debate" },
  { id: 3, label: "Arbitration" },
  { id: 4, label: "Execution" },
  { id: 5, label: "Learning" },
] as const;

interface ReasoningTimelineProps {
  readonly phaseReached: number;
  readonly activePhase?: number;
  readonly className?: string;
}

/** Vertical stepper of the 5 consensus phases (ADR-007). */
export function ReasoningTimeline({
  phaseReached,
  activePhase,
  className,
}: ReasoningTimelineProps) {
  return (
    <ol className={cn("space-y-2", className)} aria-label="Consensus phases">
      {PHASES.map((p) => {
        const reached = p.id <= phaseReached;
        const active = p.id === activePhase;
        return (
          <li key={p.id} className="flex items-center gap-3">
            <span
              aria-hidden
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full border text-2xs font-semibold",
                active
                  ? "border-accent bg-accent text-ink-inverse"
                  : reached
                    ? "border-confidence-ok bg-confidence-ok/15 text-confidence-ok"
                    : "border-border bg-surface text-ink-subtle",
              )}
            >
              {p.id}
            </span>
            <span
              className={cn(
                "text-sm",
                active ? "text-ink" : reached ? "text-ink-muted" : "text-ink-subtle",
              )}
            >
              {p.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
