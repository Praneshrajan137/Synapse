/**
 * SYNAPSE Atlas Console — Mission Control offline queue hook.
 *
 * Wraps `@shared/storage/idb-offline-queue` with a React surface:
 *   - On mount, hydrates pending entries from IndexedDB.
 *   - On every send, persists the entry BEFORE dispatching to the WS.
 *   - On every server ACK, drops the matching entry.
 *
 * This makes HITL decisions durable: a page reload mid-decide keeps the
 * pending queue intact; the next mount replays unACKed entries against
 * the freshly-opened socket.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ack as ackStorage,
  enqueue as enqueueStorage,
  readQueue,
  type QueuedResponse,
} from "@shared/storage/idb-offline-queue";

import type { ResponsePayload } from "../model/escalation";

export interface UseOfflineQueueResult {
  /** All pending entries — hydrated from IDB then live. */
  readonly pending: readonly QueuedResponse<ResponsePayload>[];
  /** Persist + return the queued entry; caller dispatches to the socket. */
  readonly enqueue: (
    decisionId: string,
    payload: ResponsePayload,
  ) => Promise<QueuedResponse<ResponsePayload>>;
  /** Drop the entry whose clientId matches the ACK. */
  readonly ack: (clientId: string) => Promise<void>;
}

export function useOfflineQueue(): UseOfflineQueueResult {
  const [pending, setPending] = useState<readonly QueuedResponse<ResponsePayload>[]>(
    [],
  );
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    void readQueue<ResponsePayload>().then((entries) => {
      if (mountedRef.current) setPending(entries);
    });
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const enqueue = useCallback<UseOfflineQueueResult["enqueue"]>(
    async (decisionId, payload) => {
      const entry = await enqueueStorage(decisionId, payload);
      if (mountedRef.current) {
        setPending((prev) => [...prev, entry]);
      }
      return entry;
    },
    [],
  );

  const ack = useCallback<UseOfflineQueueResult["ack"]>(async (clientId) => {
    await ackStorage(clientId);
    if (mountedRef.current) {
      setPending((prev) => prev.filter((e) => e.clientId !== clientId));
    }
  }, []);

  return { pending, enqueue, ack };
}
