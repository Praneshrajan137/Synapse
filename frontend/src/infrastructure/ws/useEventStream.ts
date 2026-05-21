import { useEffect, useRef, useState } from "react";

/**
 * Server-Sent Events stream hook (ported from the legacy JSX hook).
 *
 * Mirrors a Kafka topic via the gateway's SSE bridge
 * (GET /api/v1/stream/:topic). Keeps a bounded ring buffer so a
 * long-lived feed cannot grow without limit.
 */

export interface StreamEvent<T = unknown> {
  readonly topic: string;
  readonly data: T;
  readonly receivedAt: number;
}

export interface UseEventStreamResult<T> {
  readonly events: ReadonlyArray<StreamEvent<T>>;
  readonly connected: boolean;
}

export interface UseEventStreamOptions {
  /** Ring-buffer size. Defaults to 500 (legacy parity). */
  limit?: number;
  /** Set false to suspend the subscription. */
  enabled?: boolean;
}

export function useEventStream<T = unknown>(
  topic: string,
  options: UseEventStreamOptions = {},
): UseEventStreamResult<T> {
  const { limit = 500, enabled = true } = options;
  const [events, setEvents] = useState<ReadonlyArray<StreamEvent<T>>>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") {
      return;
    }

    const source = new EventSource(`/api/v1/stream/${encodeURIComponent(topic)}`);
    sourceRef.current = source;

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (event: MessageEvent<string>) => {
      try {
        const data = JSON.parse(event.data) as T;
        setEvents((prev) => {
          const next = [...prev, { topic, data, receivedAt: Date.now() }];
          return next.length > limit ? next.slice(next.length - limit) : next;
        });
      } catch {
        // Drop malformed frames silently — the stream stays healthy.
      }
    };

    return () => {
      source.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [topic, limit, enabled]);

  return { events, connected };
}
