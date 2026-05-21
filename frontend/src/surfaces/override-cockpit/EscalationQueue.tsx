import { useMemo } from "react";
import { cn } from "@lib/cn";
import { ConfidenceChip, TierBadge } from "@ds/compounds";
import { fmt } from "@lib/formatters";
import type { EscalationEntry } from "@state/escalation.store";

interface EscalationQueueProps {
  readonly entries: ReadonlyArray<EscalationEntry>;
  readonly activeId: string | null;
  readonly onSelect: (id: string) => void;
}

/**
 * Left-column queue, sorted by confidence ascending (most-urgent first).
 * Acted entries are visually demoted but still present (FE-INV-017).
 */
export function EscalationQueue({ entries, activeId, onSelect }: EscalationQueueProps) {
  const sorted = useMemo(
    () =>
      [...entries].sort((a, b) => {
        if (a.status !== b.status) return a.status === "pending" ? -1 : 1;
        return a.message.confidence - b.message.confidence;
      }),
    [entries],
  );

  return (
    <aside
      aria-label="Escalation queue"
      className="syn-card flex h-full flex-col overflow-hidden"
    >
      <header className="border-b border-border px-3 py-2 text-2xs uppercase tracking-wide text-ink-muted">
        Queue · {entries.filter((e) => e.status === "pending").length} pending
      </header>
      <ul className="flex-1 divide-y divide-border overflow-auto">
        {sorted.length === 0 && (
          <li className="p-4 text-center text-xs text-ink-muted">No escalations</li>
        )}
        {sorted.map((entry) => {
          const msg = entry.message;
          const isActive = entry.id === activeId;
          const isActed = entry.status !== "pending";
          return (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => onSelect(entry.id)}
                aria-current={isActive ? "true" : undefined}
                className={cn(
                  "flex w-full flex-col gap-1 px-3 py-2 text-left transition-colors duration-fast ease-standard",
                  isActive ? "bg-surface-raised" : "hover:bg-surface-raised/60",
                  isActed && "opacity-50",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-2xs text-ink-muted">
                    {fmt.shortId(msg.decision_id)}
                  </span>
                  {msg.tier && <TierBadge tier={msg.tier} />}
                  <ConfidenceChip value={msg.confidence} />
                </div>
                <div className="text-2xs text-ink-subtle">
                  {fmt.relativeTime(new Date(entry.received_at).toISOString())}
                  {msg.violations.length > 0 &&
                    ` • ${msg.violations.length} violation${msg.violations.length === 1 ? "" : "s"}`}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
