import { useCallback, useEffect, useRef, useState } from "react";

/**
 * WebSocket hook (ported from the legacy JSX hook) — bidirectional,
 * low-latency channel for HITL escalation and live context streams.
 *
 * Retains the legacy exponential-backoff reconnect with full jitter,
 * capped at 30s, aligned with ADR-016 (no fixed-delay retries).
 */

export interface UseWebSocketResult<T> {
  readonly messages: ReadonlyArray<T>;
  readonly connected: boolean;
  readonly send: (data: unknown) => void;
}

const MAX_BACKOFF_MS = 30_000;

export function useWebSocket<T = unknown>(
  url: string,
  options: { enabled?: boolean } = {},
): UseWebSocketResult<T> {
  const { enabled = true } = options;
  const [messages, setMessages] = useState<ReadonlyArray<T>>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const closedByUs = useRef(false);

  useEffect(() => {
    if (!enabled || typeof WebSocket === "undefined") {
      return;
    }
    closedByUs.current = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    function connect(): void {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        attemptRef.current = 0;
      };
      ws.onclose = () => {
        setConnected(false);
        if (closedByUs.current) return;
        // Full jitter backoff (ADR-016).
        const ceiling = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attemptRef.current);
        attemptRef.current += 1;
        reconnectTimer = setTimeout(connect, Math.random() * ceiling);
      };
      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          setMessages((prev) => [...prev, JSON.parse(event.data) as T]);
        } catch {
          // Ignore malformed frames.
        }
      };
    }

    connect();

    return () => {
      closedByUs.current = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [url, enabled]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { messages, connected, send };
}
