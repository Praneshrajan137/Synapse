import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { applyOnce, newBounded, type RingBuffer } from "../ring-buffer";

// Feature: atlas-console-effectiveness
// Property 7: A message whose sequence was already applied is dropped, so no
// message applies more than once.
//
// `applyOnce(buf, appliedSeqs, msg)` drops a message whose `seq` is already in
// `appliedSeqs` (returns the buffer unchanged with `applied=false`) and
// otherwise appends it (`applied=true`). The caller owns `appliedSeqs` and adds
// `msg.seq` to it whenever `applied` is `true`. Replaying a firehose stream
// that contains duplicate sequences — a reconnect/replay burst — therefore
// applies each distinct `seq` at most once: no lost, no double-counted item.
//
// **Validates: Requirements 6.3**

interface Msg {
  readonly seq: number;
  readonly tag: number;
}

// A firehose stream keyed by seq, with duplicates injected on purpose: we draw
// a pool of distinct seqs, then build a stream that samples from that pool so
// the same seq recurs (a replay/duplicate). The `tag` distinguishes otherwise
// identical-seq messages so we can prove the FIRST occurrence is the one kept.
const arbStream = fc
  .array(fc.integer({ min: 0, max: 50 }), { minLength: 0, maxLength: 40 })
  .chain((seqPool) => {
    if (seqPool.length === 0) {
      return fc.constant<Msg[]>([]);
    }
    return fc
      .array(fc.nat({ max: seqPool.length - 1 }), { minLength: 0, maxLength: 300 })
      .map((indices) =>
        indices.map((poolIdx, i) => {
          // `poolIdx` is drawn from fc.nat({ max: seqPool.length - 1 }), so it is
          // always in-bounds; the fallback only satisfies noUncheckedIndexedAccess
          // and never changes the generated value.
          const seq = seqPool[poolIdx] ?? 0;
          return { seq, tag: i };
        }),
      );
  });

const arbCap = fc.integer({ min: 1, max: 500 });

// Drives a stream through applyOnce exactly as a caller would: it threads the
// applied-seq set and adds a seq only when the message was applied.
function replay(
  cap: number,
  stream: readonly Msg[],
): {
  buf: RingBuffer<Msg>;
  appliedSeqs: Set<number>;
  appliedCountBySeq: Map<number, number>;
} {
  let buf = newBounded<Msg>(cap);
  const appliedSeqs = new Set<number>();
  const appliedCountBySeq = new Map<number, number>();
  for (const msg of stream) {
    const { buf: nextBuf, applied } = applyOnce(buf, appliedSeqs, msg);
    if (applied) {
      appliedSeqs.add(msg.seq);
      appliedCountBySeq.set(msg.seq, (appliedCountBySeq.get(msg.seq) ?? 0) + 1);
    }
    buf = nextBuf;
  }
  return { buf, appliedSeqs, appliedCountBySeq };
}

describe("Property 7: at-most-once application under a firehose replay", () => {
  it("applies each distinct seq at most once across a duplicate-laden stream", () => {
    fc.assert(
      fc.property(arbCap, arbStream, (cap, stream) => {
        const { appliedCountBySeq } = replay(cap, stream);
        // No seq is applied more than once, regardless of how many duplicates arrived.
        for (const count of appliedCountBySeq.values()) {
          expect(count).toBe(1);
        }
        // The set of applied seqs is exactly the set of distinct seqs in the stream.
        const distinctSeqs = new Set(stream.map((m) => m.seq));
        expect(new Set(appliedCountBySeq.keys())).toEqual(distinctSeqs);
      }),
      { numRuns: 100 },
    );
  });

  it("drops a message whose seq was already applied, leaving the buffer unchanged", () => {
    fc.assert(
      fc.property(
        arbCap,
        fc.integer({ min: 0, max: 1000 }),
        fc.integer(),
        (cap, seq, tag) => {
          const buf = newBounded<Msg>(cap);
          const msg = { seq, tag };
          // First application succeeds and appends.
          const first = applyOnce(buf, new Set<number>(), msg);
          expect(first.applied).toBe(true);
          expect(first.buf.items).toEqual([msg]);
          // A second message with the same seq is dropped: buffer returned unchanged.
          const dup = { seq, tag: tag + 1 };
          const second = applyOnce(first.buf, new Set<number>([seq]), dup);
          expect(second.applied).toBe(false);
          expect(second.buf).toBe(first.buf);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("keeps the first-seen message for each seq (later duplicates never overwrite)", () => {
    fc.assert(
      fc.property(arbCap, arbStream, (cap, stream) => {
        const { buf } = replay(cap, stream);
        // For every seq still retained in the bounded buffer, its tag is the
        // tag of the FIRST stream message carrying that seq — a later duplicate
        // was dropped, never applied to overwrite the original.
        const firstTagBySeq = new Map<number, number>();
        for (const m of stream) {
          if (!firstTagBySeq.has(m.seq)) {
            firstTagBySeq.set(m.seq, m.tag);
          }
        }
        for (const item of buf.items) {
          expect(item.tag).toBe(firstTagBySeq.get(item.seq));
        }
      }),
      { numRuns: 100 },
    );
  });

  it("never retains duplicate seqs in the buffer", () => {
    fc.assert(
      fc.property(arbCap, arbStream, (cap, stream) => {
        const { buf } = replay(cap, stream);
        const seqs = buf.items.map((m) => m.seq);
        expect(new Set(seqs).size).toBe(seqs.length);
      }),
      { numRuns: 100 },
    );
  });
});
