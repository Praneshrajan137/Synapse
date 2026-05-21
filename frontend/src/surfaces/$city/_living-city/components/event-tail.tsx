/**
 * SYNAPSE Atlas Console — Living City event tail.
 *
 * Right rail showing the merged 9-topic SSE feed in arrival order with
 * topic-severity badges and a per-topic filter row. We don't virtualise
 * here at S4 — operationally the tail is bound at 200 entries and the
 * DOM cost is dwarfed by the map. Virtualisation lands in S6 if RUM
 * shows TBT pressure.
 */
import { memo, useMemo, useState } from "react";

import { Badge } from "@shared/ui/badge";
import { cn } from "@shared/ui/cn";

import {
  TOPIC_SEVERITY,
  USER_VISIBLE_TOPICS,
  type TailEvent,
  type UserVisibleTopic,
} from "../model/event";

const SEVERITY_VARIANT: Record<string, "muted" | "warn" | "alert" | "critical"> = {
  info: "muted",
  warn: "warn",
  alert: "alert",
  critical: "critical",
};

export interface EventTailProps {
  readonly events: readonly TailEvent[];
  readonly className?: string;
  readonly maxRows?: number;
}

export const EventTail = memo(function EventTail({
  events,
  className,
  maxRows = 80,
}: EventTailProps) {
  const [filter, setFilter] = useState<UserVisibleTopic | "all">("all");

  const filtered = useMemo(() => {
    const base = filter === "all" ? events : events.filter((e) => e.topic === filter);
    // Most recent at the top.
    return base.slice(-maxRows).reverse();
  }, [events, filter, maxRows]);

  return (
    <aside
      aria-label="Live event tail"
      className={cn("flex h-full flex-col rounded-md border border-border bg-card", className)}
    >
      <header className="flex flex-wrap gap-1 border-b border-border p-2">
        <FilterChip
          active={filter === "all"}
          variant="muted"
          onClick={() => setFilter("all")}
        >
          all
        </FilterChip>
        {USER_VISIBLE_TOPICS.map((t) => (
          <FilterChip
            key={t}
            active={filter === t}
            variant={SEVERITY_VARIANT[TOPIC_SEVERITY[t]] ?? "muted"}
            onClick={() => setFilter(t)}
          >
            {t.replace("synapse.", "")}
          </FilterChip>
        ))}
      </header>
      <ol
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        className="flex flex-1 flex-col gap-1 overflow-auto p-2 text-ops-xs"
      >
        {filtered.map((e) => (
          <li
            key={e.id}
            className="flex items-start gap-2 rounded border border-border/60 bg-bg/40 p-2"
          >
            <Badge variant={SEVERITY_VARIANT[TOPIC_SEVERITY[e.topic]] ?? "muted"}>
              {e.topic.replace("synapse.", "")}
            </Badge>
            <time
              dateTime={new Date(e.receivedAt).toISOString()}
              className="shrink-0 text-muted-fg"
            >
              {new Date(e.receivedAt).toLocaleTimeString("en-IN", {
                timeZone: "Asia/Kolkata",
                hour12: false,
              })}
            </time>
            <pre className="ml-auto max-h-20 min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-pre-wrap break-words font-mono text-muted-fg">
              {previewBody(e.body)}
            </pre>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="p-3 text-center text-muted-fg">No events yet.</li>
        )}
      </ol>
    </aside>
  );
});

interface FilterChipProps {
  readonly active: boolean;
  readonly variant: "muted" | "warn" | "alert" | "critical";
  readonly onClick: () => void;
  readonly children: React.ReactNode;
}

function FilterChip({ active, variant, onClick, children }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-2 py-0.5 text-ops-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary/15 text-primary"
          : "border-border bg-bg text-muted-fg hover:bg-muted",
      )}
      data-variant={variant}
    >
      {children}
    </button>
  );
}

function previewBody(body: unknown): string {
  try {
    const json = JSON.stringify(body);
    return json.length > 220 ? `${json.slice(0, 220)}…` : json;
  } catch {
    return String(body);
  }
}
