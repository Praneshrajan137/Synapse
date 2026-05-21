import { useRecentDecisions } from "@/application/decisions";
import type { DecisionSummary } from "@/domain/decision";
import { ConfidenceGauge } from "@/ui/components/ConfidenceGauge";
import { TierBadge } from "@/ui/components/TierBadge";
import { useNow } from "@/ui/hooks/useNow";
import { AgentSigil } from "@/ui/icons";
import { cn } from "@/ui/lib/cn";
import { relativeTime, shortId } from "@/ui/lib/format";
import { Skeleton } from "@/ui/primitives";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";
import { useNavigate } from "react-router-dom";

/**
 * DecisionTape — the live, append-only stream of orchestrator decisions.
 * Virtualized; newest at the top. A row links to the decision's Replay.
 */

function TapeRow({ decision, now }: { decision: DecisionSummary; now: number }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => navigate(`/replay/${decision.id}`)}
      className={cn(
        "flex w-full items-center gap-3 border-b border-line-faint/60 px-3 py-2 text-left",
        "transition-colors hover:bg-elevated/60",
        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sig-live",
      )}
    >
      <AgentSigil agent={decision.leadAgent} size={20} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-xs text-ink-primary">{decision.summary}</span>
        <span className="flex items-center gap-2 text-2xs text-ink-hint">
          <span className="font-mono">{shortId(decision.id)}</span>
          {decision.escalated && <span className="text-sig-warn">escalated</span>}
        </span>
      </div>
      <TierBadge tier={decision.tier} />
      <ConfidenceGauge value={decision.confidence} size={28} showValue={false} />
      <span className="tnum w-9 shrink-0 text-right font-mono text-2xs text-ink-disabled">
        {relativeTime(decision.createdAt, now)}
      </span>
    </button>
  );
}

export function DecisionTape({ className }: { className?: string }) {
  const { data, isLoading } = useRecentDecisions(60);
  const now = useNow(5_000);
  const scrollRef = useRef<HTMLDivElement>(null);
  const rows = data ?? [];

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 49,
    overscan: 8,
  });

  return (
    <section
      aria-label="Decision tape"
      className={cn("flex min-h-0 flex-col bg-paper", className)}
    >
      <header className="flex h-9 items-center justify-between border-b border-line-faint px-3">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Decision Tape
        </h2>
        <span className="text-2xs text-ink-hint">{rows.length} recent</span>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-col gap-2 p-3">
            {Array.from({ length: 6 }, (_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed skeleton
              <Skeleton key={i} shape="line" className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map((item) => {
              const decision = rows[item.index];
              if (!decision) return null;
              return (
                <div
                  key={decision.id}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${item.start}px)`,
                  }}
                >
                  <TapeRow decision={decision} now={now} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
