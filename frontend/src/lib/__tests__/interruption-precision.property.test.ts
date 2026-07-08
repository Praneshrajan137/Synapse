import { describe, expect, it } from "vitest";
import fc from "fast-check";
import {
  interruptionPrecision,
  seededInterruptionPrecision,
  SEEDED_INTERRUPTIONS,
  type Interruption,
} from "../interruption-precision";

// Feature: atlas-console-effectiveness
// Property 18: Interruption_Precision equals warranted ÷ total interruptions
// over the window and is bounded within [0, 1].
//
// `interruptionPrecision(interruptions)` is pure and total. Over a window of
// interruptions it returns warranted ÷ total, which always lies in [0, 1]. When
// the window is empty (total === 0) the ratio is undefined, so it returns null
// rather than fabricating a value (0/0). This is the North-Star effectiveness
// metric (Req 13.1).
//
// **Validates: Requirements 13.1**

// ── Generators ──────────────────────────────────────────────────────────────

const arbInterruption: fc.Arbitrary<Interruption> = fc.record({
  warranted: fc.boolean(),
});

/** A possibly-empty window of interruptions (empty ⇒ the null case). */
const arbInterruptions: fc.Arbitrary<Interruption[]> = fc.array(arbInterruption, {
  maxLength: 200,
});

/** A guaranteed non-empty window so the ratio is always a defined number. */
const arbNonEmptyInterruptions: fc.Arbitrary<Interruption[]> = fc.array(arbInterruption, {
  minLength: 1,
  maxLength: 200,
});

// ── Reference oracle (independent of the implementation) ─────────────────────

function oracle(interruptions: readonly Interruption[]): number | null {
  const total = interruptions.length;
  if (total === 0) return null;
  const warranted = interruptions.filter((i) => i.warranted).length;
  return warranted / total;
}

describe("Property 18: Interruption_Precision is the warranted fraction, bounded in [0, 1]", () => {
  it("equals warranted ÷ total for any non-empty window", () => {
    fc.assert(
      fc.property(arbNonEmptyInterruptions, (interruptions) => {
        const total = interruptions.length;
        const warranted = interruptions.filter((i) => i.warranted).length;
        expect(interruptionPrecision(interruptions)).toBe(warranted / total);
      }),
      { numRuns: 100 },
    );
  });

  it("matches an independent oracle across empty and non-empty windows", () => {
    fc.assert(
      fc.property(arbInterruptions, (interruptions) => {
        expect(interruptionPrecision(interruptions)).toBe(oracle(interruptions));
      }),
      { numRuns: 100 },
    );
  });

  it("returns a value within [0, 1] whenever the window is non-empty", () => {
    fc.assert(
      fc.property(arbNonEmptyInterruptions, (interruptions) => {
        const result = interruptionPrecision(interruptions);
        expect(result).not.toBeNull();
        expect(result).toBeGreaterThanOrEqual(0);
        expect(result).toBeLessThanOrEqual(1);
      }),
      { numRuns: 100 },
    );
  });

  it("returns null exactly when the window is empty (total === 0)", () => {
    // The empty window is the only null case; any non-empty window is a number.
    expect(interruptionPrecision([])).toBeNull();
    fc.assert(
      fc.property(arbInterruptions, (interruptions) => {
        const result = interruptionPrecision(interruptions);
        expect(result === null).toBe(interruptions.length === 0);
      }),
      { numRuns: 100 },
    );
  });

  it("hits the boundaries: all-warranted ⇒ 1, none-warranted ⇒ 0", () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 200 }), (n) => {
        const allWarranted: Interruption[] = Array.from({ length: n }, () => ({ warranted: true }));
        const noneWarranted: Interruption[] = Array.from({ length: n }, () => ({ warranted: false }));
        expect(interruptionPrecision(allWarranted)).toBe(1);
        expect(interruptionPrecision(noneWarranted)).toBe(0);
      }),
      { numRuns: 100 },
    );
  });

  it("the seeded scripted-proxy value is the warranted fraction of SEEDED_INTERRUPTIONS and lies in [0, 1]", () => {
    const value = seededInterruptionPrecision();
    expect(value).toBe(oracle(SEEDED_INTERRUPTIONS));
    expect(value).not.toBeNull();
    expect(value).toBeGreaterThanOrEqual(0);
    expect(value).toBeLessThanOrEqual(1);
  });
});
