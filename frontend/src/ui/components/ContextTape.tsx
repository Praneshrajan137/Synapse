import type { ContextMessage } from "@/domain/decision";
import { cn } from "@/ui/lib/cn";
import { clockTime } from "@/ui/lib/format";
import { AGENT_NAMES, type AgentName, agentColor, signal } from "@/ui/tokens";
import { useEffect, useRef } from "react";

/**
 * ContextTape — the append-only consensus context (invariant I-14).
 *
 * The metaphor is the constraint: the tape only ever grows. There are
 * no edit or delete affordances — rows are immutable once shown
 * (tenet T-3). LLM reasoning is marked with the reasoning signal.
 */

function sourceColor(source: string): string {
  if ((AGENT_NAMES as readonly string[]).includes(source)) {
    return agentColor[source as AgentName];
  }
  if (source === "llm") return signal.think;
  if (source === "pareto" || source === "orchestrator") return signal.trace;
  return signal.live;
}

function MessageCard({ message }: { message: ContextMessage }) {
  const color = sourceColor(message.source);
  const isReasoning = message.status === "reasoning";
  return (
    <li
      className="border-b border-line-faint/60 px-3 py-2"
      style={isReasoning ? { borderLeft: `2px solid ${signal.think}` } : undefined}
    >
      <div className="mb-0.5 flex items-center gap-2">
        <span className="font-mono text-2xs font-semibold" style={{ color }}>
          [{message.source}|{message.status}]
        </span>
        <span className="tnum ml-auto font-mono text-2xs text-ink-disabled">
          {clockTime(message.timestamp)}
        </span>
      </div>
      <p
        className={cn(
          "whitespace-pre-wrap break-words text-2xs leading-relaxed",
          isReasoning ? "text-ink-secondary" : "font-mono text-ink-hint",
        )}
      >
        {message.content}
      </p>
    </li>
  );
}

export interface ContextTapeProps {
  messages: readonly ContextMessage[];
  className?: string;
  /** Auto-scroll to the newest message as the tape grows. */
  follow?: boolean;
}

export function ContextTape({ messages, className, follow = true }: ContextTapeProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (follow) endRef.current?.scrollIntoView({ block: "end" });
  }, [follow]);

  return (
    <section
      aria-label="Consensus context"
      className={cn("flex flex-col bg-paper", className)}
    >
      <header className="flex h-9 shrink-0 items-center justify-between border-b border-line-faint px-3">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Context Tape
        </h2>
        <span className="text-2xs text-ink-hint">append-only · {messages.length}</span>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ol>
          {messages.map((message) => (
            <MessageCard key={message.id} message={message} />
          ))}
        </ol>
        <div ref={endRef} />
      </div>
    </section>
  );
}
