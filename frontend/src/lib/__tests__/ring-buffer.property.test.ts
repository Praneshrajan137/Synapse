import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { appendBounded, newBounded } from "../ring-buffer";

// Feature: atlas-console-effectiveness
// Property 6: The ring buffer never retains more than its cap regardless of
// how many messages arrive.
//
// `newBounded(cap)` clamps a non-positive/non-finite cap to 1, and
// `appendBounded` evicts the oldest entry once the buffer is at capacity, so
// for any cap ≥ 1 and any number of appends `buf.items.length` is always
// ≤ cap. The eviction is FIFO (oldest first) and the source array is never
// mutated.
//
// **Validates: Requirements 6.2**

// Any cap the runtime firehose could construct — plus values that must be
// clamped to 1 so the invariant still holds for degenerate inputs.
const arbCap = fc.integer({ min: 1, max: 500 });
// A sequence of arbitrary items to append; length independent of cap so we
// exercise "far more appends than cap" as well as "fewer than cap".
const arbItems = fc.array(fc.integer(), { minLength: 0, maxLength: 2000 });

describe("Property 6: the ring buffer never retains more than its cap", () => {
  it("length never exceeds cap after any number of appends", () => {
    fc.assert(
      fc.property(arbCap, arbItems, (cap, items) => {
        let buf = newBounded<number>(cap);
        for (const item of items) {
          buf = appendBounded(buf, item);
          expect(buf.items.length).toBeLessThanOrEqual(cap);
        }
        // Final length is bounded by both cap and the number appended.
        expect(buf.items.length).toBeLessThanOrEqual(cap);
        expect(buf.items.length).toBe(Math.min(items.length, cap));
      }),
      { numRuns: 100 },
    );
  });

  it("clamps a non-positive or non-finite cap to 1 and still bounds length", () => {
    const arbBadCap = fc.oneof(
      fc.integer({ min: -1000, max: 0 }),
      fc.constant(Number.NaN),
      fc.constant(Number.POSITIVE_INFINITY),
      fc.constant(Number.NEGATIVE_INFINITY),
    );
    fc.assert(
      fc.property(arbBadCap, arbItems, (badCap, items) => {
        let buf = newBounded<number>(badCap);
        expect(buf.cap).toBe(1);
        for (const item of items) {
          buf = appendBounded(buf, item);
          expect(buf.items.length).toBeLessThanOrEqual(1);
        }
        expect(buf.items.length).toBe(items.length === 0 ? 0 : 1);
      }),
      { numRuns: 100 },
    );
  });

  it("evicts oldest-first (FIFO) so the retained window is the last `cap` items", () => {
    fc.assert(
      fc.property(arbCap, arbItems, (cap, items) => {
        let buf = newBounded<number>(cap);
        for (const item of items) {
          buf = appendBounded(buf, item);
        }
        // The retained items are exactly the most-recent `cap` appended, in order.
        const expected = items.slice(Math.max(0, items.length - cap));
        expect(buf.items).toEqual(expected);
      }),
      { numRuns: 100 },
    );
  });

  it("never mutates the source buffer's items array on append", () => {
    fc.assert(
      fc.property(arbCap, fc.integer(), (cap, item) => {
        const buf = newBounded<number>(cap);
        const before = buf.items;
        appendBounded(buf, item);
        // The original buffer is an immutable value: its array is unchanged.
        expect(buf.items).toBe(before);
        expect(before.length).toBe(0);
      }),
      { numRuns: 100 },
    );
  });
});
