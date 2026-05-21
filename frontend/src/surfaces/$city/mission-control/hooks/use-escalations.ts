/**
 * SYNAPSE Atlas Console — useEscalations.
 *
 * Composes:
 *   - `useWebSocket` (typed, full-jitter back-off, canonical-JSON send).
 *   - The Zod-validated `EscalationSchema` and `WsFrameSchema`.
 *   - The pure `rankEscalations` function from ../model/ranker.
 *
 * The hook owns the consolidated escalation state by keying on
 * `decision_id`. Late ACKs and duplicate broadcasts both deduplicate
 * cleanly: the latest copy of any decision wins.
 *
 * Returns a frozen ranked list so React's reference-equality kicks in
 * for memoised children when the list is unchanged.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { useWebSocket } from "@shared/realtime";

import {
  type Ack,
  type Escalation,
  WsFrameSchema,
} from "../model/escalation";
import { rankEscalations } from "../model/ranker";

interface UseEscalationsOptions {
  /** WebSocket URL — defaults to wss://<host>/ws/escalation. */
  readonly url?: string;
  readonly enabled?: boolean;
  /** Wall clock provider — overridden in tests for determinism. */
  readonly now?: () => number;
}

interface UseEscalationsResult {
  readonly escalations: readonly Escalation[];
  readonly connected: boolean;
  readonly send: (data: unknown) => boolean;
  readonly latestAck: Ack | null;
}

function defaultWsUrl(): string {
  if (typeof window === "undefined") return "wss://localhost/ws/escalation";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/escalation`;
}

export function useEscalations(options: UseEscalationsOptions = {}): UseEscalationsResult {
  const { url = defaultWsUrl(), enabled = true, now = Date.now } = options;

  const { messages, connected, send } = useWebSocket(url, {
    schema: WsFrameSchema,
    enabled,
    maxBuffer: 500,
  });

  // Index escalations by decision_id; rebuild on every new frame.
  const indexRef = useRef<Map<string, Escalation>>(new Map());
  const [latestAck, setLatestAck] = useState<Ack | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let mutated = false;
    for (const frame of messages) {
      if (frame.type === "escalation") {
        // Replace-on-collision so re-broadcasts don't render stale data.
        indexRef.current.set(frame.decision_id, frame);
        mutated = true;
      } else if (frame.type === "ack") {
        if (frame.decision_id) {
          // ACK clears the entry — orchestrator considers the decision settled.
          indexRef.current.delete(frame.decision_id);
          mutated = true;
        }
        setLatestAck(frame);
      }
    }
    if (mutated) setTick((t) => t + 1);
  }, [messages]);

  const ranked = useMemo<readonly Escalation[]>(
    () => rankEscalations(Array.from(indexRef.current.values()), now()),
    // `tick` and the `now` clock both invalidate the ranking. Including
    // both makes the dependency intent explicit even though the ref's
    // contents are what really moved.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tick, now],
  );

  return { escalations: ranked, connected, send, latestAck };
}
