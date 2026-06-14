import { useCityStore } from "@state/city.store";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import { type FirehoseChannel, type FirehoseClient, createFirehose } from "@transport/firehose";
import type { WsState } from "@transport/ws-multiplex";
import { useEffect, useRef, useState } from "react";

interface UseFirehoseOptions {
  readonly topics: ReadonlyArray<FirehoseChannel>;
}

export interface UseFirehoseResult {
  readonly state: WsState;
  readonly connected: boolean;
}

/**
 * Mounts the firehose multiplex for the active city. Re-subscribes on
 * city switch — flushes channel buffers to keep cross-city data from
 * leaking (FE-INV-016).
 */
export function useFirehose({ topics }: UseFirehoseOptions): UseFirehoseResult {
  const city = useCityStore((s) => s.city);
  const flushAll = useFirehoseStore((s) => s.flushAll);
  const append = useFirehoseStore((s) => ({
    decision: s.appendDecision,
    disruption: s.appendDisruption,
    routing: s.appendRoute,
    demand: s.appendDemand,
    twin: s.appendTwin,
    pricing: s.appendPricing,
    freshness: s.appendFreshness,
  }));
  const appendEscalation = useEscalationStore((s) => s.append);
  const lastSeq = useFirehoseStore((s) => s.lastSeq);
  const setConnection = useFirehoseStore((s) => s.setConnection);
  const [state, setState] = useState<WsState>("idle");
  const ref = useRef<FirehoseClient | null>(null);

  useEffect(() => {
    flushAll();
    const client = createFirehose({
      topics,
      city,
      sinceSeq: lastSeq[topics[0] ?? "decision"],
    });
    ref.current = client;
    const onState = (s: WsState) => {
      setState(s);
      // Lift to the global store so the attention beacon can read it (Shell).
      setConnection(s);
    };
    const offState = client.onState(onState);
    onState(client.state());

    const offs: Array<() => void> = [];
    if (topics.includes("decision")) {
      offs.push(
        client.on("decision", (d, env) =>
          // Pre-ADR-044 envelopes carry no payload timestamp — fall back to
          // the server envelope ts so relative-time rendering never breaks.
          append.decision({ ...d, timestamp: d.timestamp ?? env.ts }, env.seq),
        ),
      );
    }
    if (topics.includes("escalation")) {
      // ADR-044: HITL escalations push through the multiplexed socket; the
      // store ignores duplicate decision_ids (the legacy /ws/escalation
      // socket may deliver the same message during the transition).
      offs.push(client.on("escalation", (m) => appendEscalation(m)));
    }
    if (topics.includes("disruption")) {
      offs.push(client.on("disruption", (d, env) => append.disruption(d, env.seq)));
    }
    if (topics.includes("routing")) {
      offs.push(client.on("routing", (r, env) => append.routing(r, env.seq)));
    }
    if (topics.includes("demand")) {
      offs.push(client.on("demand", (d, env) => append.demand(d, env.seq)));
    }
    if (topics.includes("twin")) {
      offs.push(client.on("twin", (t, env) => append.twin(t, env.seq)));
    }
    if (topics.includes("pricing")) {
      offs.push(client.on("pricing", (p, env) => append.pricing(p, env.seq)));
    }
    if (topics.includes("freshness")) {
      offs.push(client.on("freshness", (f, env) => append.freshness(f, env.seq)));
    }

    return () => {
      for (const off of offs) off();
      offState();
      client.close();
      ref.current = null;
      // No socket on this surface anymore — don't show a phantom "offline".
      setConnection("idle");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, topics.join(",")]);

  return { state, connected: state === "open" };
}
