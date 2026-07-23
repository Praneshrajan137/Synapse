import { type AgentMetric, AgentMetricSchema } from "@domain/agent-metric";
import { type CognitionEvent, CognitionEventSchema } from "@domain/cognition-event";
import { type DecisionEnvelope, DecisionEnvelopeSchema } from "@domain/decision-envelope";
import { type DemandForecast, DemandForecastSchema } from "@domain/demand-forecast";
import { type DisruptionAlert, DisruptionAlertSchema } from "@domain/disruption-alert";
import { type EscalationMessage, EscalationMessageSchema } from "@domain/escalation";
import { type FreshnessAlert, FreshnessAlertSchema } from "@domain/freshness-alert";
import { type PricingUpdate, PricingUpdateSchema } from "@domain/pricing-update";
import type { City } from "@domain/primitives";
import { type RoutePlan, RoutePlanSchema } from "@domain/route-plan";
import { type TwinDivergenceEvent, TwinDivergenceEventSchema } from "@domain/twin-state";
import { type WsMultiplex, createWsMultiplex } from "./ws-multiplex";

// Typed wrapper around the WS multiplex pointed at /ws/firehose.
// Server envelope: { topic, seq, ts, payload }. We unwrap and Zod-validate
// per-channel payloads before dispatching to listeners.
//
// ADR-044: `decision` validates against the LEAN DecisionEnvelopeSchema (the
// outbox payload that actually flows — the previous strict ConsensusDecision
// schema rejected every live envelope), and the new `escalation` channel
// carries HITL escalations through the same multiplexed socket.

export type FirehoseChannel =
  | "decision"
  | "disruption"
  | "routing"
  | "demand"
  | "twin"
  | "freshness"
  | "pricing"
  | "escalation"
  | "cognition"
  | "metric";

interface ChannelPayloadMap {
  decision: DecisionEnvelope;
  disruption: DisruptionAlert;
  routing: RoutePlan;
  demand: DemandForecast;
  twin: TwinDivergenceEvent;
  freshness: FreshnessAlert;
  pricing: PricingUpdate;
  escalation: EscalationMessage;
  cognition: CognitionEvent;
  metric: AgentMetric;
}

const SCHEMAS = {
  decision: DecisionEnvelopeSchema,
  disruption: DisruptionAlertSchema,
  routing: RoutePlanSchema,
  demand: DemandForecastSchema,
  // Union: the DivergenceMonitor's alert shape (the real producer) OR a full
  // TwinState snapshot — alerts previously failed the snapshot schema and
  // the twin channel was silently dead (same defect class as `decision`).
  twin: TwinDivergenceEventSchema,
  freshness: FreshnessAlertSchema,
  pricing: PricingUpdateSchema,
  escalation: EscalationMessageSchema,
  cognition: CognitionEventSchema,
  // ADR-053: was `null` (open-shape/dead) — now a real producer emits this,
  // so it validates against the agent-metric schema like every other channel.
  metric: AgentMetricSchema,
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
  readonly host?: string | undefined;
  readonly topics: ReadonlyArray<FirehoseChannel>;
  readonly city: City;
  readonly sinceSeq?: number | undefined;
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
        // Every channel now has a Zod schema (ADR-053 gave `metric` a real
        // producer + payload contract) — validate before dispatching so a
        // poison message never reaches app code.
        const parsed = SCHEMAS[channel].safeParse(envelope.payload);
        if (!parsed.success) {
          // eslint-disable-next-line no-console
          console.warn(`firehose_${channel}_rejected`, parsed.error.issues);
          return;
        }
        listener(parsed.data as ChannelPayloadMap[typeof channel], {
          seq: envelope.seq,
          ts: envelope.ts,
        });
      });
    },
  };
}
