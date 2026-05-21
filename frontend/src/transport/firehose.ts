import { createWsMultiplex, type WsMultiplex } from "./ws-multiplex";
import { ConsensusDecisionSchema, type ConsensusDecision } from "@domain/consensus-decision";
import { DisruptionAlertSchema, type DisruptionAlert } from "@domain/disruption-alert";
import { DemandForecastSchema, type DemandForecast } from "@domain/demand-forecast";
import { RoutePlanSchema, type RoutePlan } from "@domain/route-plan";
import { TwinStateSchema, type TwinState } from "@domain/twin-state";
import { FreshnessAlertSchema, type FreshnessAlert } from "@domain/freshness-alert";
import { PricingUpdateSchema, type PricingUpdate } from "@domain/pricing-update";
import type { City } from "@domain/primitives";

// Typed wrapper around the WS multiplex pointed at /ws/firehose.
// Server envelope: { topic, seq, ts, payload }. We unwrap and Zod-validate
// per-channel payloads before dispatching to listeners.

export type FirehoseChannel =
  | "decision"
  | "disruption"
  | "routing"
  | "demand"
  | "twin"
  | "freshness"
  | "pricing"
  | "metric";

interface ChannelPayloadMap {
  decision: ConsensusDecision;
  disruption: DisruptionAlert;
  routing: RoutePlan;
  demand: DemandForecast;
  twin: TwinState;
  freshness: FreshnessAlert;
  pricing: PricingUpdate;
  metric: Record<string, unknown>;
}

const SCHEMAS = {
  decision: ConsensusDecisionSchema,
  disruption: DisruptionAlertSchema,
  routing: RoutePlanSchema,
  demand: DemandForecastSchema,
  twin: TwinStateSchema,
  freshness: FreshnessAlertSchema,
  pricing: PricingUpdateSchema,
  metric: null,
} as const;

export interface FirehoseClient {
  state: WsMultiplex["state"];
  onState: WsMultiplex["onState"];
  close: WsMultiplex["close"];
  on<C extends FirehoseChannel>(
    channel: C,
    listener: (payload: ChannelPayloadMap[C], envelope: { seq: number; ts: string }) => void,
  ): () => void;
}

export interface CreateFirehoseOptions {
  readonly host?: string;
  readonly topics: ReadonlyArray<FirehoseChannel>;
  readonly city: City;
  readonly sinceSeq?: number;
}

export function createFirehose(opts: CreateFirehoseOptions): FirehoseClient {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = opts.host ?? window.location.host;
  const url = () => {
    const params = new URLSearchParams({
      topics: opts.topics.join(","),
      city: opts.city,
    });
    if (opts.sinceSeq) params.set("since_seq", String(opts.sinceSeq));
    return `${proto}://${host}/ws/firehose?${params.toString()}`;
  };
  const mux = createWsMultiplex({ url, heartbeatMs: 20_000 });

  return {
    state: mux.state.bind(mux),
    onState: mux.onState.bind(mux),
    close: mux.close.bind(mux),
    on(channel, listener) {
      return mux.on(channel, (rawEnvelope) => {
        const envelope = rawEnvelope as { seq?: number; ts?: string; payload?: unknown };
        if (typeof envelope.seq !== "number" || typeof envelope.ts !== "string") return;
        const schema = SCHEMAS[channel];
        if (!schema) {
          // metric channel is open-shape; pass through as-is.
          listener(
            (envelope.payload ?? {}) as ChannelPayloadMap[typeof channel],
            { seq: envelope.seq, ts: envelope.ts },
          );
          return;
        }
        const parsed = schema.safeParse(envelope.payload);
        if (!parsed.success) {
          // eslint-disable-next-line no-console
          console.warn(`firehose_${channel}_rejected`, parsed.error.issues);
          return;
        }
        listener(
          parsed.data as ChannelPayloadMap[typeof channel],
          { seq: envelope.seq, ts: envelope.ts },
        );
      });
    },
  };
}
