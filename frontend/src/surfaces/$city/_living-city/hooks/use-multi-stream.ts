/**
 * SYNAPSE Atlas Console — multi-topic SSE merge.
 *
 * Living City's right rail tails N topics simultaneously. Each
 * subscription is its own EventSource (the SSE bridge gives us
 * consumer-group-per-connection — see api/routers/sse.py), so
 * back-pressure on one topic can't stall the others.
 *
 * This hook is the merge layer: it composes per-topic `useSse` calls
 * and emits a single chronological tail. The bound is configurable;
 * Living City uses 200 to keep the DOM lean while still showing a
 * useful operational story.
 */
import { useEffect, useRef, useState } from "react";

import { useSse } from "@shared/realtime";

import {
  type TailEvent,
  TailEventBodySchema,
  type UserVisibleTopic,
} from "../model/event";

interface UseMultiStreamOptions {
  readonly topics: readonly UserVisibleTopic[];
  readonly maxBuffer?: number;
}

interface UseMultiStreamResult {
  readonly events: readonly TailEvent[];
  readonly connectionsHealthy: number;
  readonly connectionsTotal: number;
}

function newTailId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function useMultiStream(options: UseMultiStreamOptions): UseMultiStreamResult {
  const { topics, maxBuffer = 200 } = options;

  // Stable buffer ref — we mutate it from inside per-topic effects to keep
  // chronological order without N independent state slots fighting each other.
  const bufferRef = useRef<TailEvent[]>([]);
  const [tick, setTick] = useState(0);

  /* eslint-disable react-hooks/rules-of-hooks -- topics is constant per mount */
  const subscriptions = topics.map((topic) =>
    useSse<unknown>(topic, { schema: TailEventBodySchema, maxBuffer }),
  );
  /* eslint-enable react-hooks/rules-of-hooks */

  // For each subscription, append its newly-arrived events into the merged
  // chronological buffer and trim from the head when over capacity.
  useEffect(() => {
    let mutated = false;
    subscriptions.forEach((sub, i) => {
      const topic = topics[i];
      if (!topic) return;
      const expected = bufferRef.current.filter((e) => e.topic === topic).length;
      const fresh = sub.events.slice(expected);
      for (const body of fresh) {
        bufferRef.current.push({
          id: newTailId(),
          topic,
          receivedAt: Date.now(),
          body,
        });
        mutated = true;
      }
    });
    if (bufferRef.current.length > maxBuffer) {
      bufferRef.current.splice(0, bufferRef.current.length - maxBuffer);
      mutated = true;
    }
    if (mutated) setTick((t) => t + 1);
  }, [subscriptions, topics, maxBuffer]);

  const connectionsHealthy = subscriptions.filter((s) => s.connected).length;

  // The buffer is referentially stable; consumers re-render on `tick` only
  // when something actually changed. Returning a fresh slice is cheap and
  // gives downstream memoisation accurate identity.
  return {
    events: bufferRef.current.slice(),
    connectionsHealthy,
    connectionsTotal: subscriptions.length,
    // tick included implicitly via state subscription — referenced to satisfy
    // exhaustive-deps in derived memos.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ...({ _tick: tick } as any),
  };
}
