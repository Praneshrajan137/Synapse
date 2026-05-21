import { useTopics } from "@/application/observability";
import type { KafkaTopic, TopicClass } from "@/domain/observability";
import { useEventStream } from "@/infrastructure/ws/useEventStream";
import { cn } from "@/ui/lib/cn";
import { clockTime } from "@/ui/lib/format";
import { Waves } from "lucide-react";
import { useState } from "react";

/**
 * Streams — the Kafka topic explorer (plan section 5.7, tenet T-9).
 * Sixteen topics as inspectable cards; a selected topic shows its spec
 * and a live tail.
 */

const CLASS_COLOR: Record<TopicClass, string> = {
  agent: "var(--color-sig-live)",
  orchestrator: "var(--color-sig-think)",
  telemetry: "var(--color-sig-trace)",
  audit: "var(--color-ink-secondary)",
  hitl: "var(--color-sig-warn)",
};

const CLASS_FILTERS: readonly (TopicClass | "all")[] = [
  "all",
  "agent",
  "orchestrator",
  "telemetry",
  "audit",
  "hitl",
];

function TopicCard({
  topic,
  selected,
  onSelect,
}: {
  topic: KafkaTopic;
  selected: boolean;
  onSelect: () => void;
}) {
  const color = CLASS_COLOR[topic.topicClass];
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "flex flex-col gap-2 rounded-lg border bg-paper p-3 text-left transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
        selected ? "border-sig-live/50" : "border-line-faint hover:border-line-strong",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className="size-2 shrink-0 rounded-full"
          style={{ backgroundColor: color }}
        />
        <span className="truncate font-mono text-2xs text-ink-primary">{topic.name}</span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-2xs text-ink-hint">
        <span>{topic.partitions} partitions</span>
        <span>{topic.retentionHours}h retention</span>
        <span className="tnum text-ink-secondary">{topic.messagesPerSec} msg/s</span>
        <span
          className="tnum"
          style={{ color: topic.consumerLag > 200 ? "var(--color-sig-warn)" : undefined }}
        >
          lag {topic.consumerLag}
        </span>
      </div>
    </button>
  );
}

function TopicInspector({ topic }: { topic: KafkaTopic }) {
  const { events, connected } = useEventStream<unknown>(topic.name);
  return (
    <aside className="flex w-[340px] shrink-0 flex-col border-l border-line-faint bg-paper">
      <header className="border-b border-line-faint px-3.5 py-3">
        <h2 className="font-mono text-xs text-ink-primary">{topic.name}</h2>
        <p className="mt-1 text-2xs text-ink-hint">
          {topic.topicClass} · {topic.partitions} partitions · {topic.retentionHours}h
        </p>
      </header>
      <div className="flex items-center justify-between border-b border-line-faint px-3.5 py-2 text-2xs">
        <span className="text-ink-secondary">Live tail</span>
        <span className="flex items-center gap-1.5 text-ink-hint">
          <span
            className={cn(
              "size-1.5 rounded-full",
              connected ? "bg-sig-ok" : "bg-ink-disabled",
            )}
          />
          {connected ? "streaming" : "idle"}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <p className="px-3.5 py-5 text-2xs leading-relaxed text-ink-hint">
            No frames yet. The tail subscribes to{" "}
            <code className="font-mono">/api/v1/stream/{topic.name}</code> over SSE;
            events appear here the moment the topic produces them.
          </p>
        ) : (
          <ul className="flex flex-col">
            {events
              .slice()
              .reverse()
              .map((event) => (
                <li
                  key={event.receivedAt}
                  className="border-b border-line-faint/60 px-3.5 py-1.5 font-mono text-2xs text-ink-hint"
                >
                  <span className="tnum text-ink-disabled">
                    {clockTime(event.receivedAt)}
                  </span>{" "}
                  {JSON.stringify(event.data).slice(0, 80)}
                </li>
              ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

export default function Streams() {
  const { data: topics } = useTopics();
  const [filter, setFilter] = useState<TopicClass | "all">("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);

  const visible = (topics ?? []).filter(
    (t) => filter === "all" || t.topicClass === filter,
  );
  const selected = topics?.find((t) => t.name === selectedName) ?? null;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-3 border-b border-line-faint bg-paper px-4 py-2.5">
        <h1 className="flex items-center gap-2 font-display text-sm font-semibold text-ink-primary">
          <Waves size={16} className="text-sig-live" aria-hidden="true" />
          Streams
        </h1>
        <div className="flex gap-1" role="tablist" aria-label="Filter topics by class">
          {CLASS_FILTERS.map((c) => (
            <button
              key={c}
              type="button"
              role="tab"
              aria-selected={filter === c}
              onClick={() => setFilter(c)}
              className={cn(
                "rounded-xs px-1.5 py-0.5 font-mono text-2xs transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sig-live",
                filter === c
                  ? "bg-elevated text-ink-primary"
                  : "text-ink-hint hover:text-ink-secondary",
              )}
            >
              {c}
            </button>
          ))}
        </div>
        <span className="ml-auto text-2xs text-ink-hint">{visible.length} topics</span>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
            {visible.map((topic) => (
              <TopicCard
                key={topic.name}
                topic={topic}
                selected={topic.name === selectedName}
                onSelect={() => setSelectedName(topic.name)}
              />
            ))}
          </div>
        </div>
        {selected && <TopicInspector topic={selected} />}
      </div>
    </div>
  );
}
