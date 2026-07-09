// Feature: atlas-console-elevation, Property 36: Replay phase parameter is validated, clamped, and falls back
//
// Property 36 (Validates: Requirements 11.2) — `parseReplayPhase` resolves the
// active replay phase from a `?phase=` URL search parameter:
//   • the result is ALWAYS a concrete phase index in [MIN_PHASE, MAX_PHASE],
//   • a usable numeric parameter is clamped (validate/clamp) and an in-range
//     integer is preserved exactly, and
//   • an absent, empty, whitespace-only, or non-numeric parameter falls back to
//     the decision's terminal phase (itself clamped defensively).

import { MAX_PHASE, MIN_PHASE, clampPhase, parseReplayPhase } from "@lib/replay";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const terminalArb = fc.oneof(
  fc.integer({ min: -8, max: 12 }),
  fc.double({ min: -8, max: 12, noNaN: true }),
  fc.constantFrom(Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY),
);

// Values that must be treated as "absent/invalid" → fall back to terminal.
const invalidParamArb = fc.oneof(
  fc.constant(null),
  fc.constant(undefined),
  fc.constant(""),
  fc.stringMatching(/^\s+$/), // whitespace-only
  fc
    .string()
    .filter((s) => s.trim() !== "" && !Number.isFinite(Number(s.trim()))), // non-numeric
);

describe("parseReplayPhase — Property 36: validate, clamp, fall back", () => {
  it("always returns a concrete phase index within [MIN_PHASE, MAX_PHASE]", () => {
    fc.assert(
      fc.property(
        fc.oneof(invalidParamArb, fc.integer({ min: -20, max: 20 }).map(String)),
        terminalArb,
        (param, terminal) => {
          const result = parseReplayPhase(param, terminal);
          expect(result).toBeGreaterThanOrEqual(MIN_PHASE);
          expect(result).toBeLessThanOrEqual(MAX_PHASE);
          expect(Number.isInteger(result)).toBe(true);
        },
      ),
      { numRuns: 200 },
    );
  });

  it("preserves an in-range integer parameter exactly", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: MIN_PHASE, max: MAX_PHASE }),
        terminalArb,
        (phase, terminal) => {
          expect(parseReplayPhase(String(phase), terminal)).toBe(phase);
        },
      ),
      { numRuns: 200 },
    );
  });

  it("clamps an out-of-range numeric parameter to the nearest bound", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.integer({ min: -50, max: 50 }), fc.double({ min: -50, max: 50, noNaN: true })),
        terminalArb,
        (n, terminal) => {
          // A usable number is resolved by clamping, independent of terminal.
          expect(parseReplayPhase(String(n), terminal)).toBe(clampPhase(n));
        },
      ),
      { numRuns: 200 },
    );
  });

  it("falls back to the clamped terminal phase when absent or invalid", () => {
    fc.assert(
      fc.property(invalidParamArb, terminalArb, (param, terminal) => {
        expect(parseReplayPhase(param, terminal)).toBe(clampPhase(terminal));
      }),
      { numRuns: 200 },
    );
  });
});
