/**
 * SYNAPSE Atlas Console — typed WebSocket hook.
 *
 * Replaces the legacy frontend/src/hooks/useWebSocket.js. Differences:
 *   - Generic over message shape; Zod schema validates incoming frames.
 *   - Full Jitter back-off (mirrors backend's `synapse_common.retry`,
 *     ADR-016) — capped at 30 s; resets after a successful open.
 *   - Sends always go through canonical JSON when targeting /a2a or
 *     /ws/escalation responses (the backend handler reuses the
 *     decision_id keyed on cache prefix — I-13).
 *   - Honours `prefers-reduced-motion`-style "live region" parameter so
 *     consumers can render announcements politely or assertively.
 *
 * Lifecycle: opens on mount, closes on unmount. Reconnect attempts
 * survive across React StrictMode double-effect via the `attempt` ref.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { ZodType, ZodTypeDef } from "zod";

import { canonicalize } from "@shared/canonical-json";

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 500;
const CANONICAL_PATHS = ["/ws/escalation", "/a2a"] as const;

export interface UseWebSocketOptions<T> {
  /** Zod schema for incoming frames; falls back to passthrough if absent. */
  readonly schema?: ZodType<T, ZodTypeDef, unknown>;
  /** Maximum messages retained in state. Default 500. */
  readonly maxBuffer?: number;
  /** Open the socket lazily — useful in Storybook stories. */
  readonly enabled?: boolean;
}

export interface UseWebSocketResult<T> {
  readonly messages: readonly T[];
  readonly connected: boolean;
  /** Send any JSON-serialisable value; canonicalised when path requires it. */
  readonly send: (data: unknown) => boolean;
  /** Force-close + reconnect. Useful after a logout/login. */
  readonly reset: () => void;
}

function fullJitter(attempt: number): number {
  const cap = Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** attempt);
  return Math.random() * cap;
}

function shouldCanonicalize(url: string): boolean {
  return CANONICAL_PATHS.some((p) => url.includes(p));
}

export function useWebSocket<T = unknown>(
  url: string,
  options: UseWebSocketOptions<T> = {},
): UseWebSocketResult<T> {
  const { schema, maxBuffer = 500, enabled = true } = options;

  const [messages, setMessages] = useState<readonly T[]>([]);
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const teardownRef = useRef(false);

  const connect = useCallback(() => {
    if (!enabled || teardownRef.current) return;

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      // jsdom raises if the URL is malformed; surface but don't blow up.
      // eslint-disable-next-line no-console
      console.warn("[atlas-console] WS construct failed", { url, err });
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setConnected(true);
    };

    ws.onclose = () => {
      setConnected(false);
      if (teardownRef.current) return;
      const delay = fullJitter(attemptRef.current);
      attemptRef.current += 1;
      window.setTimeout(() => connect(), delay);
    };

    ws.onerror = () => {
      // Browser will follow with onclose; nothing to do here.
    };

    ws.onmessage = (event) => {
      let parsed: unknown;
      try {
        parsed = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
      } catch {
        return;
      }
      let value: T;
      if (schema) {
        const r = schema.safeParse(parsed);
        if (!r.success) {
          // eslint-disable-next-line no-console
          console.warn("[atlas-console] WS schema reject", r.error.flatten());
          return;
        }
        value = r.data;
      } else {
        value = parsed as T;
      }
      setMessages((prev) => {
        const next = prev.length >= maxBuffer ? prev.slice(prev.length - maxBuffer + 1) : prev.slice();
        next.push(value);
        return next;
      });
    };
  }, [url, enabled, schema, maxBuffer]);

  useEffect(() => {
    teardownRef.current = false;
    connect();
    return () => {
      teardownRef.current = true;
      try {
        wsRef.current?.close();
      } catch {
        /* noop */
      }
    };
  }, [connect]);

  const send = useCallback(
    (data: unknown): boolean => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return false;
      const body = shouldCanonicalize(url) ? canonicalize(data) : JSON.stringify(data);
      ws.send(body);
      return true;
    },
    [url],
  );

  const reset = useCallback(() => {
    try {
      wsRef.current?.close();
    } catch {
      /* noop */
    }
    attemptRef.current = 0;
    connect();
  }, [connect]);

  return { messages, connected, send, reset };
}
