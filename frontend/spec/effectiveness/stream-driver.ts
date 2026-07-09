/**
 * Effectiveness_Harness — scripted WS/SSE stream driver (Req 1.2, 1.3, 2.5).
 *
 * This module feeds the *same* `WebSocket`/`EventSource` surfaces the Console
 * already consumes (`transport/ws-multiplex.ts`, `transport/firehose.ts`, and
 * the Demo Theater SSE in `surfaces/demo-theater/useDemoRun.ts`) with a
 * deterministic, ordered message sequence keyed by a single seed, for every
 * real-time channel (design "B. Harness — MSW browser worker + stream driver").
 *
 * Two layers live here:
 *
 *   1. {@link scriptStream} — a *pure* function that, for a fixed `(channel,
 *      seed)`, returns a byte-identical, identically-ordered
 *      {@link StreamMessage} sequence on every invocation (Req 1.3). The seed is
 *      the only entropy source; every payload is derived from — and, for a
 *      schema-bound channel, validated against — the same `Domain_Schema` the
 *      Console validates at runtime (via the shared fixture factory).
 *
 *   2. {@link createStreamDriver} — installs the controllable transport doubles
 *      and returns a {@link StreamDriver} that can `drive` a channel's scripted
 *      sequence into the live surface, `injectSchemaViolation` on demand (so
 *      Requirement 8's schema-violation transition is exercised
 *      deterministically — Req 2.5), and `flap` a connection.
 *
 * The stream driver never patches an app code path: it only replaces the
 * network edge (the `WebSocket`/`EventSource` constructors) with seeded doubles,
 * exactly as `browser-worker.ts` replaces the `fetch` edge.
 */

import { buildFixture, buildSchemaViolatingFixture, makeRng, type Rng } from "./fixture-factory";
import type { SchemaId } from "./schema-registry";
import {
  ScriptedEventSource,
  ScriptedWebSocket,
  StreamTransportController,
} from "./stream-transport";

// ─────────────────────────────────────────────────────────────────────────
// Channel model — every real-time channel the Console subscribes to
// ─────────────────────────────────────────────────────────────────────────

/** Firehose WebSocket channels (mirrors `transport/firehose.ts` `SCHEMAS`). */
export type FirehoseStreamChannel =
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

/** Server-Sent-Events channels (the Demo Theater run stream). */
export type SseStreamChannel = "demo";

/** Every real-time channel the harness can script. */
export type StreamChannel = FirehoseStreamChannel | SseStreamChannel;

/** How a channel reaches the Console: multiplexed WebSocket or SSE. */
export type StreamTransport = "ws" | "sse";

interface ChannelSpec {
  readonly transport: StreamTransport;
  /** The bound `Domain_Schema` id, or `null` for an open-shape channel (Req 2.4). */
  readonly schemaId: SchemaId | null;
}

/**
 * The authoritative per-channel binding. Firehose channel → `schemaId` mirrors
 * `transport/firehose.ts` (where `metric` is open-shape / `null`). The `demo`
 * SSE stream carries the surface-local `DemoEvent` shape, which has no
 * `Domain_Schema` — so it is open-shape too.
 */
const CHANNELS: Readonly<Record<StreamChannel, ChannelSpec>> = {
  decision: { transport: "ws", schemaId: "DecisionEnvelope" },
  disruption: { transport: "ws", schemaId: "DisruptionAlert" },
  routing: { transport: "ws", schemaId: "RoutePlan" },
  demand: { transport: "ws", schemaId: "DemandForecast" },
  twin: { transport: "ws", schemaId: "TwinDivergenceEvent" },
  freshness: { transport: "ws", schemaId: "FreshnessAlert" },
  pricing: { transport: "ws", schemaId: "PricingUpdate" },
  escalation: { transport: "ws", schemaId: "EscalationMessage" },
  cognition: { transport: "ws", schemaId: "CognitionEvent" },
  metric: { transport: "ws", schemaId: null },
  demo: { transport: "sse", schemaId: null },
};

/** Every channel id the driver knows about. */
export const STREAM_CHANNELS: readonly StreamChannel[] = Object.keys(CHANNELS) as StreamChannel[];

/** The bound `schemaId` for `channel`, or `null` when the channel is open-shape. */
export function channelSchemaId(channel: StreamChannel): SchemaId | null {
  return CHANNELS[channel].schemaId;
}

/** The transport (`ws` | `sse`) a channel arrives on. */
export function channelTransport(channel: StreamChannel): StreamTransport {
  return CHANNELS[channel].transport;
}

/** True iff `channel` is bound to a `Domain_Schema` (so it can host a violation). */
export function isSchemaBoundChannel(channel: StreamChannel): boolean {
  return CHANNELS[channel].schemaId !== null;
}

function isKnownChannel(channel: string): channel is StreamChannel {
  return Object.hasOwn(CHANNELS, channel);
}

// ─────────────────────────────────────────────────────────────────────────
// Scripting constants and deterministic seed derivation
// ─────────────────────────────────────────────────────────────────────────

/** Sequence numbers start here; monotonic per channel, used as the dedup key. */
const BASE_SEQ = 1;
/** Deterministic delivery cadence between consecutive scripted messages. */
const OFFSET_STEP_MS = 250;
/** Message-count band per channel; the exact count is derived from the seed. */
const MIN_MESSAGES = 4;
const MAX_MESSAGES = 8;
/** Base wall-clock used to derive a deterministic ISO `ts` from an offset. */
const BASE_TS_MS = Date.UTC(2024, 0, 1, 0, 0, 0);

/**
 * Derive a stable 32-bit seed from `(seed, channel, index)`. Same inputs ⇒ same
 * output, so a per-message payload is reproducible while distinct messages
 * differ. Uses an FNV-style fold over the channel name.
 */
function deriveSeed(seed: number, channel: string, index: number): number {
  let h = seed >>> 0;
  for (let i = 0; i < channel.length; i += 1) {
    h = (Math.imul(h, 31) + channel.charCodeAt(i)) >>> 0;
  }
  h = (Math.imul(h, 31) + (index + 1)) >>> 0;
  return h >>> 0;
}

/** Deterministic message count for a channel, within [MIN, MAX]. */
function messageCount(seed: number, channel: StreamChannel): number {
  const rng = makeRng(deriveSeed(seed, `${channel}#count`, 0));
  const span = MAX_MESSAGES - MIN_MESSAGES + 1;
  return MIN_MESSAGES + Math.floor(rng() * span);
}

/** A deterministic ISO timestamp for a delivery offset (the envelope `ts`). */
function tsForOffset(offsetMs: number): string {
  return new Date(BASE_TS_MS + offsetMs).toISOString();
}

// ─────────────────────────────────────────────────────────────────────────
// StreamMessage + scriptStream (pure, deterministic — Req 1.3)
// ─────────────────────────────────────────────────────────────────────────

/** One scripted, deterministic streamed message (design Data Models). */
export interface StreamMessage {
  readonly channel: string;
  /** Monotonic per channel; the dedup key applied by `ws-multiplex`. */
  readonly seq: number;
  readonly payload: unknown;
  /** Deterministic delivery offset from stream start, in milliseconds. */
  readonly offsetMs: number;
}

/**
 * Build the deterministic message payload for one channel message. A
 * schema-bound channel derives (and re-validates) its payload from the bound
 * `Domain_Schema` via the shared fixture factory; an open-shape channel gets a
 * deterministic open-shape body appropriate to its surface.
 */
function scriptPayload(channel: StreamChannel, seed: number, index: number): unknown {
  const spec = CHANNELS[channel];
  const msgSeed = deriveSeed(seed, channel, index);
  if (spec.schemaId !== null) {
    const result = buildFixture({
      capabilityId: `${channel}.${spec.transport.toUpperCase()}.stream`,
      schemaId: spec.schemaId,
      seed: msgSeed,
    });
    return result.body;
  }
  return openShapePayload(channel, makeRng(msgSeed), index);
}

/** A deterministic open-shape payload for a schema-less channel. */
function openShapePayload(channel: StreamChannel, rng: Rng, index: number): unknown {
  if (channel === "demo") {
    const kinds = ["log", "segment", "done"] as const;
    const kind = kinds[Math.floor(rng() * kinds.length)] ?? "log";
    if (kind === "segment") {
      const segments = [
        "01_living_map",
        "02_ipl_signal",
        "03_disruption",
        "04_debate",
        "05_evidence",
      ] as const;
      return { type: "segment", segment: segments[index % segments.length], ts: index };
    }
    if (kind === "done") {
      return { type: "done", exit_code: 0, ts: index };
    }
    return { type: "log", line: `demo log line ${index}`, ts: index };
  }
  // `metric` and any other open-shape channel: a simple deterministic metric.
  return { name: `metric-${index}`, value: Math.floor(rng() * 1000), ts: index };
}

/**
 * The scripted, deterministic message sequence for `channel` under `seed`
 * (Req 1.2, 1.3). For a fixed seed this returns a byte-identical array with the
 * same message order on every invocation: the seed is the only entropy source,
 * counts and payloads are seed-derived, and `seq`/`offsetMs` are monotonic.
 */
export function scriptStream(channel: StreamChannel, seed: number): readonly StreamMessage[] {
  const count = messageCount(seed, channel);
  const messages: StreamMessage[] = [];
  for (let index = 0; index < count; index += 1) {
    messages.push({
      channel,
      seq: BASE_SEQ + index,
      payload: scriptPayload(channel, seed, index),
      offsetMs: index * OFFSET_STEP_MS,
    });
  }
  return messages;
}

// ─────────────────────────────────────────────────────────────────────────
// Frame construction — wrap a StreamMessage in its transport envelope
// ─────────────────────────────────────────────────────────────────────────

/**
 * The raw firehose WebSocket envelope frame `{topic, seq, ts, payload}` that
 * `ws-multiplex`/`firehose` parse. Byte-identical for a fixed `(channel, seed)`
 * because every field is derived deterministically.
 */
export function buildWsFrame(message: StreamMessage): string {
  return JSON.stringify({
    topic: message.channel,
    seq: message.seq,
    ts: tsForOffset(message.offsetMs),
    payload: message.payload,
  });
}

/** The SSE event name a demo payload maps to (`log`/`segment`/`done`). */
function sseEventName(payload: unknown): string {
  if (typeof payload === "object" && payload !== null && "type" in payload) {
    const type = (payload as { type?: unknown }).type;
    if (typeof type === "string") return type;
  }
  return "log";
}

// ─────────────────────────────────────────────────────────────────────────
// StreamDriver — deliver scripted sequences into the live surfaces
// ─────────────────────────────────────────────────────────────────────────

/** Thrown when the driver is asked to act on a channel it cannot serve. */
export class StreamDriverError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StreamDriverError";
  }
}

/**
 * The scripted stream driver (design "B"). `drive` delivers a channel's scripted
 * sequence, `injectSchemaViolation` delivers a single schema-violating payload
 * on demand (Req 2.5 / 8.2), and `flap` cycles a connection down/up (Req 8.4).
 */
export interface StreamDriver {
  drive(channel: StreamChannel): void;
  injectSchemaViolation(channel: StreamChannel): void;
  flap(channel: StreamChannel, cycles: number): void;
}

/** A {@link StreamDriver} with installed transport doubles and lifecycle. */
export interface InstalledStreamDriver extends StreamDriver {
  /** The single entropy source for every scripted message. */
  readonly seed: number;
  /** The scripted sequence for a channel (pure; equals {@link scriptStream}). */
  scriptFor(channel: StreamChannel): readonly StreamMessage[];
  /** The controller owning the installed `WebSocket`/`EventSource` doubles. */
  readonly transport: StreamTransportController;
  /** Reinstate the original globals. Always call in teardown/`finally`. */
  restore(): void;
}

const FIREHOSE_URL_MARKERS = ["/ws/firehose", "/ws/escalation"];

function isFirehoseWsUrl(url: string): boolean {
  return FIREHOSE_URL_MARKERS.some((marker) => url.includes(marker));
}

function isDemoSseUrl(url: string): boolean {
  return url.includes("/demo/") && url.includes("/stream");
}

/**
 * Create a scripted stream driver keyed by `seed`, installing the controllable
 * `WebSocket`/`EventSource` doubles. Every channel is served from the same
 * deterministic script, so a fixed seed yields an identical message order on
 * every run (Req 1.3).
 */
export function createStreamDriver(opts: { readonly seed: number }): InstalledStreamDriver {
  const { seed } = opts;
  const transport = new StreamTransportController();
  transport.install();

  /** The open firehose WebSocket, opening a registered-but-idle one on demand. */
  function ensureOpenSocket(channel: StreamChannel): ScriptedWebSocket {
    const socket = transport.latestSocket(isFirehoseWsUrl);
    if (socket === undefined) {
      throw new StreamDriverError(
        `No firehose WebSocket has connected yet for channel "${channel}"; ` +
          "mount the subscribing surface before driving the stream.",
      );
    }
    if (socket.readyState !== ScriptedWebSocket.OPEN) socket.driverOpen();
    return socket;
  }

  /** The open demo EventSource, opening a registered-but-idle one on demand. */
  function ensureOpenSource(channel: StreamChannel): ScriptedEventSource {
    const source = transport.latestSource(isDemoSseUrl);
    if (source === undefined) {
      throw new StreamDriverError(
        `No demo EventSource has connected yet for channel "${channel}"; ` +
          "start the demo run before driving the stream.",
      );
    }
    if (source.readyState !== ScriptedEventSource.OPEN) source.driverOpen();
    return source;
  }

  function driveWs(channel: StreamChannel): void {
    const socket = ensureOpenSocket(channel);
    for (const message of scriptStream(channel, seed)) {
      socket.driverEmit(buildWsFrame(message));
    }
  }

  function driveSse(channel: StreamChannel): void {
    const source = ensureOpenSource(channel);
    for (const message of scriptStream(channel, seed)) {
      source.driverEmit(sseEventName(message.payload), JSON.stringify(message.payload));
    }
  }

  return {
    seed,

    drive(channel: StreamChannel): void {
      if (!isKnownChannel(channel)) {
        throw new StreamDriverError(`Unknown stream channel "${channel}".`);
      }
      if (channelTransport(channel) === "ws") driveWs(channel);
      else driveSse(channel);
    },

    injectSchemaViolation(channel: StreamChannel): void {
      if (!isKnownChannel(channel)) {
        throw new StreamDriverError(`Unknown stream channel "${channel}".`);
      }
      const schemaId = channelSchemaId(channel);
      if (schemaId === null) {
        throw new StreamDriverError(
          `Channel "${channel}" is open-shape (no Domain_Schema), so it cannot host a ` +
            "deterministic schema violation; choose a schema-bound channel (Req 2.5).",
        );
      }
      // The corrupt payload keeps a valid envelope (topic/seq/ts) so it reaches
      // the per-channel schema-violation path, where `firehose`/`ws-multiplex`
      // reject the unvalidated payload (Req 8.2).
      const violationSeq = BASE_SEQ + scriptStream(channel, seed).length;
      const frame = buildWsFrame({
        channel,
        seq: violationSeq,
        payload: buildSchemaViolatingFixture(schemaId, seed),
        offsetMs: violationSeq * OFFSET_STEP_MS,
      });
      ensureOpenSocket(channel).driverEmit(frame);
    },

    flap(channel: StreamChannel, cycles: number): void {
      if (!isKnownChannel(channel)) {
        throw new StreamDriverError(`Unknown stream channel "${channel}".`);
      }
      if (channelTransport(channel) !== "ws") {
        throw new StreamDriverError(
          `flap is only defined for WebSocket channels; "${channel}" is an SSE channel.`,
        );
      }
      for (let cycle = 0; cycle < cycles; cycle += 1) {
        const socket = transport.latestSocket(isFirehoseWsUrl);
        if (socket === undefined) break;
        // Bring the connection up (so a live→not-live transition is observable),
        // then drop it server-side to trigger the multiplex reconnect path.
        if (socket.readyState !== ScriptedWebSocket.OPEN) socket.driverOpen();
        socket.driverServerClose();
      }
    },

    scriptFor(channel: StreamChannel): readonly StreamMessage[] {
      return scriptStream(channel, seed);
    },

    transport,

    restore(): void {
      transport.restore();
    },
  };
}
