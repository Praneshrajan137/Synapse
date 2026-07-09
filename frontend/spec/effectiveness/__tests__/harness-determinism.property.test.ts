/**
 * Feature: atlas-console-effectiveness, Property 3: For a fixed seed the harness
 * yields byte-identical fixture responses and an identical stream message order
 * across runs
 *
 * Validates: Requirements 1.3
 *
 * Property-based verification that the Effectiveness_Harness is deterministic
 * for a fixed seed (design "Property 3: The harness is deterministic for a fixed
 * seed"; Requirement 1.3). The PR gate depends on this: because MSW serves
 * byte-identical fixtures and the stream driver replays an identically-ordered
 * message sequence for a fixed seed, every harness-derived check is
 * reproducible and non-flaky.
 *
 * The seed is the ONLY entropy source in the fixture factory and stream driver,
 * so the determinism claim is a universally-quantified property over the seed.
 * Five facets are exercised over the real registry/channel set with
 * `numRuns: 100`, each comparing two independent invocations via
 * `JSON.stringify` (byte-identical output):
 *
 *   1. `scriptStream(channel, seed)` yields a byte-identical message array on
 *      two invocations, for every real-time channel (Req 1.3, 2.2).
 *   2. The stream MESSAGE ORDER — the `(seq, offsetMs)` sequence — is identical
 *      across two invocations (Req 1.3): a strictly monotonic, seed-independent
 *      ordering.
 *   3. Each scripted message's `buildWsFrame` transport envelope is
 *      byte-identical across two invocations (the bytes actually delivered to
 *      the Console are reproducible).
 *   4. `buildFixture` yields a byte-identical response body on two invocations
 *      for every registered `Domain_Schema` (Req 1.3).
 *   5. The full HTTP handler fixture set (`buildEffectivenessHandlers` inputs
 *      via `buildFixture` + `capabilitySeed`) is byte-identical across two
 *      invocations for every registered capability spec.
 */

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { buildFixture, type FixtureRequest } from "../fixture-factory";
import {
  buildEffectivenessHandlers,
  capabilitySeed,
  EFFECTIVENESS_HANDLER_SPECS,
} from "../handlers";
import { DOMAIN_SCHEMA_REGISTRY, getSchema, type SchemaId } from "../schema-registry";
import {
  buildWsFrame,
  scriptStream,
  STREAM_CHANNELS,
  type StreamChannel,
} from "../stream-driver";

/** Every registered `schemaId` — the schema-bound fixture input space. */
const REGISTERED_SCHEMA_IDS: readonly SchemaId[] = Object.keys(DOMAIN_SCHEMA_REGISTRY);

/** A 32-bit seed — the sole entropy source shared by the factory and driver. */
const seedArb = fc.integer({ min: 0, max: 0xffffffff });

/** An arbitrary drawing one real-time channel the stream driver can script. */
const channelArb = fc.constantFrom<StreamChannel>(...STREAM_CHANNELS);

/** An arbitrary drawing a registered schema id (for schema-bound fixtures). */
const schemaIdArb = fc.constantFrom<SchemaId>(...REGISTERED_SCHEMA_IDS);

describe("Property 3: harness determinism for a fixed seed", () => {
  it("guards the channel and schema input spaces are non-empty", () => {
    expect(STREAM_CHANNELS.length).toBeGreaterThan(0);
    expect(REGISTERED_SCHEMA_IDS.length).toBeGreaterThan(0);
  });

  // Req 1.3 / 2.2: scriptStream is byte-identical across two invocations for a
  // fixed (channel, seed) — the scripted stream is fully reproducible.
  it("scriptStream yields a byte-identical message sequence across two invocations", () => {
    fc.assert(
      fc.property(channelArb, seedArb, (channel, seed) => {
        const first = scriptStream(channel, seed);
        const second = scriptStream(channel, seed);
        expect(JSON.stringify(second)).toBe(JSON.stringify(first));
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.3: the stream MESSAGE ORDER — the (seq, offsetMs) sequence — is
  // identical across runs and strictly monotonic (identical ordering claim).
  it("scriptStream yields an identical, strictly monotonic message order across runs", () => {
    fc.assert(
      fc.property(channelArb, seedArb, (channel, seed) => {
        const order = (msgs: readonly { seq: number; offsetMs: number }[]) =>
          msgs.map((m) => `${m.seq}@${m.offsetMs}`);

        const first = order(scriptStream(channel, seed));
        const second = order(scriptStream(channel, seed));

        // Identical order across two independent invocations (Req 1.3).
        expect(second).toEqual(first);

        // The order is a strictly increasing (seq, offsetMs) sequence, so
        // "identical order" is a well-defined, deterministic claim.
        const seqs = scriptStream(channel, seed).map((m) => m.seq);
        const offsets = scriptStream(channel, seed).map((m) => m.offsetMs);
        for (let i = 1; i < seqs.length; i += 1) {
          expect(seqs[i]).toBeGreaterThan(seqs[i - 1] as number);
          expect(offsets[i]).toBeGreaterThan(offsets[i - 1] as number);
        }
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.3: the transport bytes actually delivered to the Console (the WS
  // envelope frames) are byte-identical across two invocations.
  it("buildWsFrame yields byte-identical transport frames across two invocations", () => {
    fc.assert(
      fc.property(channelArb, seedArb, (channel, seed) => {
        const framesOf = () => scriptStream(channel, seed).map((m) => buildWsFrame(m));
        expect(framesOf()).toEqual(framesOf());
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.3: buildFixture is byte-identical across two invocations for a fixed
  // (schemaId, seed) — the HTTP fixture body the Console receives is reproducible.
  it("buildFixture yields a byte-identical response body across two invocations", () => {
    fc.assert(
      fc.property(schemaIdArb, seedArb, (schemaId, seed) => {
        const req: FixtureRequest = { capabilityId: `cap.${schemaId}`, schemaId, seed };

        const first = buildFixture(req);
        const second = buildFixture(req);

        // Byte-identical bodies, and the body still validates its bound schema
        // so determinism is not achieved by emitting a degenerate value.
        expect(JSON.stringify(second)).toBe(JSON.stringify(first));
        if (first.kind === "schema-bound") {
          expect(getSchema(schemaId)?.safeParse(first.body).success).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.3: the full HTTP handler fixture set is byte-identical across two
  // invocations for a fixed base seed — every Surface's populated fixture is
  // reproducible, so the deterministic PR gate holds end-to-end.
  it("the full handler fixture set is byte-identical across two invocations for a fixed seed", () => {
    fc.assert(
      fc.property(seedArb, (seed) => {
        const bodiesOf = () =>
          EFFECTIVENESS_HANDLER_SPECS.filter((spec) => spec.schemaId !== null).map((spec) =>
            buildFixture({
              capabilityId: spec.capabilityId,
              schemaId: spec.schemaId,
              seed: capabilitySeed(seed, spec.capabilityId),
            }),
          );

        expect(JSON.stringify(bodiesOf())).toBe(JSON.stringify(bodiesOf()));
      }),
      { numRuns: 100 },
    );
  });

  // Req 1.3: constructing the handler set twice for a fixed seed does not throw
  // (fixtures re-validate their schemas deterministically) and yields the same
  // handler count — the worker registration is reproducible.
  it("buildEffectivenessHandlers is reproducible for a fixed seed", () => {
    fc.assert(
      fc.property(seedArb, (seed) => {
        const first = buildEffectivenessHandlers(seed);
        const second = buildEffectivenessHandlers(seed);
        expect(second.length).toBe(first.length);
        expect(first.length).toBe(EFFECTIVENESS_HANDLER_SPECS.length);
      }),
      { numRuns: 100 },
    );
  });
});
