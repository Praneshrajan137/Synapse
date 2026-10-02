import { useCityStore } from "@state/city.store";
import { useEscalationStore } from "@state/escalation.store";
import { useFirehoseStore } from "@state/firehose.store";
import {
  type FirehoseChannel,
  type FirehoseClient,
  type FirehoseListener,
  type FirehoseRejection,
  createFirehose,
} from "@transport/firehose";
import type { WsState } from "@transport/ws-multiplex";
import { useEffect, useRef, useState } from "react";

interface UseFirehoseOptions {
  readonly topics: ReadonlyArray<FirehoseChannel>;
}

export interface UseFirehoseResult {
  readonly state: WsState;
  readonly connected: boolean;
  /**
   * Payloads this socket REJECTED on schema validation that no accepted frame
   * on the same channel has superseded yet: at most one (the latest) per
   * channel, least recent first, and empty while the feed is clean. A surface
   * reads its own channels here to render the schema-violation `error` state
   * (Req 8.2) instead of presenting its last good data as a healthy feed.
   */
  readonly rejections: ReadonlyArray<FirehoseRejection>;
}

/** Stable empty value, so a clean feed never re-renders its consumer. */
const NO_REJECTIONS: ReadonlyArray<FirehoseRejection> = [];

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
    cognition: s.appendCognition,
    metric: s.appendMetric,
  }));
  const appendEscalation = useEscalationStore((s) => s.append);
  const lastSeq = useFirehoseStore((s) => s.lastSeq);
  const setConnection = useFirehoseStore((s) => s.setConnection);
  const [state, setState] = useState<WsState>("idle");
  const [rejections, setRejections] = useState<ReadonlyArray<FirehoseRejection>>(NO_REJECTIONS);
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

    // Rejections THIS client reported that no accepted frame has superseded,
    // keyed by channel. Re-inserting on each rejection keeps Map order equal to
    // recency, so the published list is least recent first.
    const unresolved = new Map<FirehoseChannel, FirehoseRejection>();
    const publish = (): void => {
      setRejections(unresolved.size === 0 ? NO_REJECTIONS : [...unresolved.values()]);
    };
    const offRejection = client.onRejection((rejection) => {
      unresolved.delete(rejection.channel);
      unresolved.set(rejection.channel, rejection);
      publish();
    });

    const offs: Array<() => void> = [];
    // Every accepted frame passes through here, so the next VALID frame on a
    // channel clears that channel's rejection — valid data has resumed there
    // (Req 8.2 recovery). A valid frame on a different channel does not.
    const subscribe = <C extends FirehoseChannel>(
      channel: C,
      handle: FirehoseListener<C>,
    ): void => {
      offs.push(
        client.on(channel, (payload, envelope) => {
          handle(payload, envelope);
          if (unresolved.delete(channel)) publish();
        }),
      );
    };

    if (topics.includes("decision")) {
      subscribe("decision", (d, env) =>
        // Pre-ADR-044 envelopes carry no payload timestamp — fall back to
        // the server envelope ts so relative-time rendering never breaks.
        append.decision({ ...d, timestamp: d.timestamp ?? env.ts }, env.seq),
      );
    }
    if (topics.includes("escalation")) {
      // ADR-044: HITL escalations push through the multiplexed socket; the
      // store ignores duplicate decision_ids (the legacy /ws/escalation
      // socket may deliver the same message during the transition).
      subscribe("escalation", (m) => appendEscalation(m));
    }
    if (topics.includes("disruption")) {
      subscribe("disruption", (d, env) => append.disruption(d, env.seq));
    }
    if (topics.includes("routing")) {
      subscribe("routing", (r, env) => append.routing(r, env.seq));
    }
    if (topics.includes("demand")) {
      subscribe("demand", (d, env) => append.demand(d, env.seq));
    }
    if (topics.includes("twin")) {
      subscribe("twin", (t, env) => append.twin(t, env.seq));
    }
    if (topics.includes("pricing")) {
      subscribe("pricing", (p, env) => append.pricing(p, env.seq));
    }
    if (topics.includes("freshness")) {
      subscribe("freshness", (f, env) => append.freshness(f, env.seq));
    }
    if (topics.includes("cognition")) {
      // ADR-051: live council cognition (FSM phase transitions) → the CouncilStrip
      // shows the agents thinking/debating in real time, derived from real events.
      subscribe("cognition", (c, env) => append.cognition(c, env.seq));
    }
    if (topics.includes("metric")) {
      // ADR-053: live per-agent telemetry — the `metric` channel finally has a
      // real producer (emit_agent_metrics), so the KPI band can read real
      // measured confidence/degraded per agent instead of only buffer proxies.
      subscribe("metric", (m, env) => append.metric(m, env.seq));
    }

    return () => {
      for (const off of offs) off();
      offRejection();
      offState();
      client.close();
      ref.current = null;
      // No socket on this surface anymore — don't show a phantom "offline".
      setConnection("idle");
      // A closed client's rejections no longer describe this surface's feed.
      setRejections(NO_REJECTIONS);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, topics.join(",")]);

  return { state, connected: state === "open", rejections };
}
