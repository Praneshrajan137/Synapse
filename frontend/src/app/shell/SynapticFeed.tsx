import { useEventStream } from "@/infrastructure/ws/useEventStream";
import { cn } from "@/ui/lib/cn";
import { Activity } from "lucide-react";

/**
 * Synaptic Feed — the right-edge append-only stream of orchestrator
 * events (plan tenet T-9: streams are first-class).
 *
 * Phase 3 subscribes to the orchestrator decision topic; Phase 8's
 * Streams surface generalizes this to all 16 topics with filtering. The
 * feed is append-only by interface contract — rows are never reordered
 * or mutated once shown (mirrors invariant I-14).
 */

const FEED_TOPIC = "synapse.orchestrator.decision";

interface Decisionish {
  decision_id?: string;
  tier?: string;
  confidence?: number;
  escalated?: boolean;
}

function summarize(data: unknown): { id: string; detail: string; alert: boolean } {
  if (typeof data === "object" && data !== null) {
    const d = data as Decisionish;
    const id = d.decision_id ? d.decision_id.slice(0, 8) : "decision";
    const parts: string[] = [];
    if (d.tier) parts.push(d.tier.replace("tier_", "T"));
    if (typeof d.confidence === "number") parts.push(`conf ${d.confidence.toFixed(2)}`);
    return {
      id,
      detail: parts.join(" · ") || "received",
      alert: d.escalated === true,
    };
  }
  return { id: "event", detail: "received", alert: false };
}

export function SynapticFeed() {
  const { events, connected } = useEventStream<unknown>(FEED_TOPIC);
  const newestFirst = [...events].reverse();

  return (
    <aside
      aria-label="Synaptic Feed"
      className="z-feed flex h-full w-80 shrink-0 flex-col border-l border-line-faint bg-paper"
    >
      <div className="flex h-10 items-center justify-between border-b border-line-faint px-3.5">
        <span className="flex items-center gap-2">
          <Activity size={14} className="text-sig-live" aria-hidden="true" />
          <span className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
            Synaptic Feed
          </span>
        </span>
        <span className="flex items-center gap-1.5 text-2xs text-ink-hint">
          <span
            className={cn(
              "size-1.5 rounded-full",
              connected ? "bg-sig-ok" : "bg-ink-disabled",
            )}
            aria-hidden="true"
          />
          {connected ? "live" : "idle"}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {newestFirst.length === 0 ? (
          <p className="px-3.5 py-6 text-2xs leading-relaxed text-ink-hint">
            Awaiting the orchestrator decision stream. Events appear here the moment the
            consensus protocol emits them.
          </p>
        ) : (
          <ul className="flex flex-col">
            {newestFirst.map((event) => {
              const { id, detail, alert } = summarize(event.data);
              const time = new Date(event.receivedAt).toLocaleTimeString([], {
                hour12: false,
              });
              return (
                <li
                  key={`${event.receivedAt}-${id}`}
                  className="flex items-center gap-2.5 border-b border-line-faint/60 px-3.5 py-2"
                >
                  <span
                    className={cn(
                      "size-1.5 shrink-0 rounded-full",
                      alert ? "bg-sig-warn" : "bg-sig-live",
                    )}
                    aria-hidden="true"
                  />
                  <span className="flex-1 truncate font-mono text-2xs text-ink-secondary">
                    {id}
                  </span>
                  <span className="truncate text-2xs text-ink-hint">{detail}</span>
                  <span className="tnum shrink-0 font-mono text-2xs text-ink-disabled">
                    {time}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
