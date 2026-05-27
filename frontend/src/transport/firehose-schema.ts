import { z } from "zod";

/**
 * Schema for the WebSocket firehose envelope (WS-4 §4b).
 *
 * The backend `/ws/firehose` (api/routers/firehose.py) emits one JSON object
 * per Kafka record with the shape `{topic, seq, ts, payload}`. Until this
 * file landed, `ws-multiplex.ts` parsed those envelopes with `JSON.parse`
 * and forwarded them to listeners unchecked — a poison message (e.g. a
 * malformed payload from a misbehaving producer) would crash whichever
 * surface bound to the affected channel.
 *
 * The schema is intentionally loose on `payload` (`unknown`) because the
 * envelope is the contract; per-topic payload validation belongs in each
 * subscriber. Heartbeats (`{type: "pong"}`) and the legacy escalation
 * channel (`{type: "decision_escalation", ...}`) are accepted via a tagged
 * union so the existing escalation surface keeps working.
 */

export const FirehoseEnvelopeSchema = z.discriminatedUnion("kind", [
  // Heartbeat reply from the server, sent in response to client pings.
  z.object({
    kind: z.literal("heartbeat"),
    type: z.literal("pong"),
  }),
  // Standard fan-out envelope (synapse.* topic, seq, timestamp, payload).
  z.object({
    kind: z.literal("envelope"),
    topic: z.string().min(1).max(128),
    seq: z.number().int().nonnegative(),
    ts: z.union([z.string(), z.number()]).optional(),
    payload: z.unknown(),
  }),
  // Legacy escalation message (kept until /ws/escalation is sunset).
  z.object({
    kind: z.literal("typed"),
    type: z.string().min(1).max(64),
    payload: z.unknown().optional(),
  }),
]);

export type FirehoseEnvelope = z.infer<typeof FirehoseEnvelopeSchema>;

/**
 * Normalise a raw JSON value into the discriminated-union shape we validate.
 * Server envelopes don't actually carry a `kind` field — we add it here so
 * Zod's discriminator has something to switch on. Returns `null` on bytes
 * that don't look like anything we expect (the WS pipeline drops the
 * frame and logs).
 */
export function shapeRawEnvelope(raw: unknown): unknown {
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (r.type === "pong") return { kind: "heartbeat", type: "pong" };
  if (typeof r.topic === "string" && typeof r.seq === "number") {
    return {
      kind: "envelope",
      topic: r.topic,
      seq: r.seq,
      ts: r.ts as string | number | undefined,
      payload: r.payload,
    };
  }
  if (typeof r.type === "string") {
    return { kind: "typed", type: r.type, payload: r.payload };
  }
  return null;
}
