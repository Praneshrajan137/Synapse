import type { AuditTimelineEntry } from "@/domain/audit";
import type { DecisionTier } from "@/domain/decision";
import { cn } from "@/ui/lib/cn";
import { clockTime } from "@/ui/lib/format";
import { Tooltip } from "@/ui/primitives";
import { type TierKey, tierColor } from "@/ui/tokens";
import { useState } from "react";

/**
 * ScrubberTimeline — the audit log as a navigable time axis (plan
 * section 5.4). Ticks are colored by tier; a tier filter narrows the
 * field. Selecting a tick loads that decision into the replica.
 */

const TIER_FILTERS: readonly { value: TierKey | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "tier_1", label: "T1" },
  { value: "tier_2", label: "T2" },
  { value: "tier_3", label: "T3" },
  { value: "tier_4", label: "T4" },
];

export interface ScrubberTimelineProps {
  entries: readonly AuditTimelineEntry[];
  selectedDecisionId: string | undefined;
  onSelect: (decisionId: string) => void;
  className?: string;
}

export function ScrubberTimeline({
  entries,
  selectedDecisionId,
  onSelect,
  className,
}: ScrubberTimelineProps) {
  const [filter, setFilter] = useState<TierKey | "all">("all");
  const visible = entries.filter((e) => filter === "all" || e.tier === filter);
  const ordered = [...visible].sort((a, b) => a.createdAt - b.createdAt);

  return (
    <section
      aria-label="Audit timeline"
      className={cn("flex flex-col gap-2 bg-paper px-4 py-2.5", className)}
    >
      <div className="flex items-center gap-3">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Audit Timeline
        </h2>
        <div className="flex gap-1" role="tablist" aria-label="Filter by tier">
          {TIER_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              role="tab"
              aria-selected={filter === f.value}
              onClick={() => setFilter(f.value)}
              className={cn(
                "rounded-xs px-1.5 py-0.5 font-mono text-2xs transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
                filter === f.value
                  ? "bg-elevated text-ink-primary"
                  : "text-ink-hint hover:text-ink-secondary",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-2xs text-ink-hint">{ordered.length} decisions</span>
      </div>

      <div className="relative flex h-9 items-center">
        <div className="absolute inset-x-0 h-px bg-line-strong" />
        <div className="relative flex w-full items-center justify-between">
          {ordered.map((entry) => {
            const selected = entry.decisionId === selectedDecisionId;
            return (
              <Tooltip
                key={entry.auditId}
                content={`${entry.summary} · ${clockTime(entry.createdAt)}`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(entry.decisionId)}
                  aria-label={`${entry.summary}, ${clockTime(entry.createdAt)}`}
                  aria-pressed={selected}
                  className={cn(
                    "rounded-full transition-transform hover:scale-150",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
                    selected && "scale-150",
                  )}
                  style={{
                    width: selected ? 11 : 7,
                    height: selected ? 11 : 7,
                    backgroundColor: tierColor[entry.tier as DecisionTier],
                    boxShadow: entry.escalated
                      ? "0 0 0 2px color-mix(in oklab, var(--color-sig-warn) 60%, transparent)"
                      : "none",
                  }}
                />
              </Tooltip>
            );
          })}
        </div>
      </div>
    </section>
  );
}
