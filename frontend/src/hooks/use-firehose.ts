import { useEffect, useRef, useState } from "react";
import { createFirehose, type FirehoseChannel, type FirehoseClient } from "@transport/firehose";
import { useCityStore } from "@state/city.store";
import { useFirehoseStore } from "@state/firehose.store";
import type { WsState } from "@transport/ws-multiplex";

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
  }));
  const lastSeq = useFirehoseStore((s) => s.lastSeq);
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
    const offState = client.onState(setState);
    setState(client.state());

    const offs: Array<() => void> = [];
    if (topics.includes("decision")) {
      offs.push(client.on("decision", (d, env) => append.decision(d, env.seq)));
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

    return () => {
      offs.forEach((off) => off());
      offState();
      client.close();
      ref.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, topics.join(",")]);

  return { state, connected: state === "open" };
}
