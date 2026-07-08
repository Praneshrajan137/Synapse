/**
 * Contract Fidelity — WebSocket channel + SSE stream catalog.
 *
 * The authoritative list of every real-time capability the Atlas Console is
 * entitled to consume: the multiplexed firehose WebSocket channels, the legacy
 * single-channel escalation WebSocket, and the demo-theater SSE stream.
 *
 * This is the channel/stream half of Input #1 of the Contract Fidelity Suite
 * (the HTTP half lives in `entitlements.ts`). Entries are typed as
 * `CapabilityEntitlement` with `kind: "ws" | "sse"` so the suite classifies
 * them alongside HTTP endpoints and reports Coverage_Status per channel/stream
 * (Requirements 1.5, 1.6).
 *
 * Source of truth mirrored here:
 *   • Backend  — `api/routers/firehose.py` `CHANNEL_TOPIC` (FE channel → Kafka
 *                topic map) on `/ws/firehose`; `orchestrator/inference/serve.py`
 *                `/ws/escalation`.
 *   • Frontend — `transport/firehose.ts` `FirehoseChannel` union + per-channel
 *                Zod `SCHEMAS`; `transport/ws-multiplex.ts` sequence-dedup
 *                envelope handling; `surfaces/demo-theater/useDemoRun.ts`
 *                `EventSource("/api/v1/demo/{job_id}/stream")`.
 *
 * `capabilityId` format — `"{router}.{METHOD}.{ref}"`; the pseudo-method is
 * `WS` for WebSocket channels and `SSE` for server-sent event streams, and
 * `ref` is the channel name (WS) or the stream path (SSE). Every firehose
 * channel shares the same `/ws/firehose` socket, so its `ref` is the channel
 * key (e.g. `firehose.WS.decision`) — that is the unit the Console binds a
 * listener + Zod schema to, and therefore the unit coverage is measured on.
 */

import type { CapabilityEntitlement } from "./types";

export type ChannelKind = "ws" | "sse";

/**
 * A `CapabilityEntitlement` enriched with the transport pseudo-method (`WS` or
 * `SSE`) and, for firehose channels, the backing Kafka `topic`. The pseudo
 * method is also encoded in `capabilityId`, so this stays assignable to the
 * base `CapabilityEntitlement`.
 */
export interface ChannelEntitlement extends CapabilityEntitlement {
  readonly method: "WS" | "SSE";
  /** Backing Kafka topic for firehose channels; null for non-firehose streams. */
  readonly topic: string | null;
}

function capabilityId(router: string, method: string, ref: string): string {
  return `${router}.${method}.${ref}`;
}

/** A multiplexed firehose channel (all share the `/ws/firehose` socket). */
function firehoseChannel(
  channel: string,
  topic: string,
  entitled: boolean,
): ChannelEntitlement {
  return {
    router: "firehose",
    method: "WS",
    ref: channel,
    capabilityId: capabilityId("firehose", "WS", channel),
    kind: "ws",
    entitled,
    topic,
  };
}

/**
 * Firehose WebSocket channels — mirrors `CHANNEL_TOPIC` in
 * `api/routers/firehose.py` and the `FirehoseChannel` union +
 * `SCHEMAS` map in `transport/firehose.ts`.
 *
 * Every channel is entitled: the Console registers a Zod-validated listener
 * for each (the `metric` channel is intentionally open-shape and passes
 * through un-schema'd — still an entitled channel, its payload is validated as
 * an open record).
 */
export const FIREHOSE_CHANNELS: readonly ChannelEntitlement[] = [
  firehoseChannel("decision", "synapse.orchestrator.decision", true),
  firehoseChannel("disruption", "synapse.disruption.alert", true),
  firehoseChannel("routing", "synapse.routing.plan", true),
  firehoseChannel("metric", "synapse.metrics.agent", true),
  firehoseChannel("twin", "synapse.twin.divergence", true),
  firehoseChannel("demand", "synapse.demand.forecast", true),
  firehoseChannel("freshness", "synapse.freshness.alert", true),
  firehoseChannel("pricing", "synapse.pricing.update", true),
  firehoseChannel("escalation", "synapse.orchestrator.escalation", true),
  firehoseChannel("cognition", "synapse.orchestrator.phase", true),
];

/**
 * Non-firehose real-time streams the Console consumes.
 *
 *  • The legacy single-channel escalation WebSocket (`/ws/escalation`,
 *    orchestrator) — still consumed by the Override Cockpit during the
 *    ADR-044 transition to the multiplexed `escalation` firehose channel.
 *  • The demo-theater SSE stream (`/api/v1/demo/{job_id}/stream`), consumed
 *    via `EventSource` in `surfaces/demo-theater/useDemoRun.ts`.
 */
export const STREAM_ENTITLEMENTS: readonly ChannelEntitlement[] = [
  {
    router: "escalations",
    method: "WS",
    ref: "/ws/escalation",
    capabilityId: capabilityId("escalations", "WS", "/ws/escalation"),
    kind: "ws",
    entitled: true,
    topic: null,
  },
  {
    router: "demo",
    method: "SSE",
    ref: "/api/v1/demo/{job_id}/stream",
    capabilityId: capabilityId("demo", "SSE", "/api/v1/demo/{job_id}/stream"),
    kind: "sse",
    entitled: true,
    topic: null,
  },
];

/** Every real-time channel/stream capability, WS and SSE alike. */
export const CHANNEL_ENTITLEMENTS: readonly ChannelEntitlement[] = [
  ...FIREHOSE_CHANNELS,
  ...STREAM_ENTITLEMENTS,
];

export default CHANNEL_ENTITLEMENTS;
