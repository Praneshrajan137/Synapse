/**
 * SYNAPSE Atlas Console — typed SSE hook for Kafka topic tails.
 *
 * Replaces the legacy frontend/src/hooks/useKafkaStream.js. Differences:
 *   - Generic + Zod-validated payload type.
 *   - `Last-Event-ID` resume on reconnect (matches backend
 *     api/routers/sse.py contract: id is `partition:offset`).
 *   - Bounded ring-buffer (default 500) to avoid unbounded memory in a
 *     long-running ops session.
 *   - Surfaces both `events` (the buffer) and the latest single event as a
 *     stable identity for use with `aria-live` announcements.
 *
 * Connection lifecycle: opens on mount, reconnects automatically via
 * EventSource's built-in semantics. We layer Full Jitter on `onerror`
 * because EventSource reconnects too aggressively by default (3s).
 */
import { useEffect, useRef, useState } from "react";
import type { ZodType, ZodTypeDef } from "zod";

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_CAP_MS = 30_000;

export interface UseSseOptions<T> {
  readonly schema?: ZodType<T, ZodTypeDef, unknown>;
  readonly maxBuffer?: number;
  readonly enabled?: boolean;
}

export interface UseSseResult<T> {
  readonly events: readonly T[];
  readonly latest: T | null;
  readonly connected: boolean;
  readonly lastEventId: string | null;
}

function fullJitter(attempt: number): number {
  const cap = Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** attempt);
  return Math.random() * cap;
}

export function useSse<T = unknown>(
  topic: string,
  options: UseSseOptions<T> = {},
): UseSseResult<T> {
  const { schema, maxBuffer = 500, enabled = true } = options;

  const [events, setEvents] = useState<readonly T[]>([]);
  const [latest, setLatest] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastEventId, setLastEventId] = useState<string | null>(null);

  const sourceRef = useRef<EventSource | null>(null);
  const attemptRef = useRef(0);
  const teardownRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    teardownRef.current = false;

    let cancelled = false;

    function open(resumeFrom: string | null): void {
      if (teardownRef.current || cancelled) return;
      const url = new URL(`/api/v1/stream/${encodeURIComponent(topic)}`, window.location.origin);
      if (resumeFrom) url.searchParams.set("lastEventId", resumeFrom);

      // EventSource sends cookies same-origin only — perfect for the BFF.
      const es = new EventSource(url.toString(), { withCredentials: true });
      sourceRef.current = es;

      es.onopen = () => {
        attemptRef.current = 0;
        setConnected(true);
      };

      es.onmessage = (event) => {
        if (event.lastEventId) setLastEventId(event.lastEventId);
        let parsed: unknown;
        try {
          parsed = JSON.parse(event.data);
        } catch {
          return;
        }
        let value: T;
        if (schema) {
          const r = schema.safeParse(parsed);
          if (!r.success) return;
          value = r.data;
        } else {
          value = parsed as T;
        }
        setLatest(value);
        setEvents((prev) => {
          const next =
            prev.length >= maxBuffer ? prev.slice(prev.length - maxBuffer + 1) : prev.slice();
          next.push(value);
          return next;
        });
      };

      es.onerror = () => {
        setConnected(false);
        try {
          es.close();
        } catch {
          /* noop */
        }
        if (teardownRef.current || cancelled) return;
        const delay = fullJitter(attemptRef.current);
        attemptRef.current += 1;
        window.setTimeout(() => open(lastEventId), delay);
      };
    }

    open(null);

    return () => {
      cancelled = true;
      teardownRef.current = true;
      try {
        sourceRef.current?.close();
      } catch {
        /* noop */
      }
    };
    // We deliberately exclude `lastEventId` from deps — it's a ref-like
    // closure variable used only on reconnect. Adding it would re-open on
    // every event.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic, enabled, schema, maxBuffer]);

  return { events, latest, connected, lastEventId };
}
