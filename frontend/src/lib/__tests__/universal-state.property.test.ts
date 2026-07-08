import { describe, expect, it } from "vitest";
import fc from "fast-check";
import {
  resolveUniversalState,
  type UniversalState,
  type UniversalStateInput,
} from "../universal-state";

// Feature: atlas-console-elevation
// Property 30: Universal-state resolution is total and distinct
//
// `resolveUniversalState` returns exactly one of six states under the fixed
// priority offline > error > degraded > loading > empty > populated, and
// empty/error/offline are mutually distinct render conditions.
//
// **Validates: Requirements 10.1**

const ALL_STATES: ReadonlySet<UniversalState> = new Set([
  "loading",
  "empty",
  "error",
  "degraded",
  "offline",
  "populated",
]);

// Independent reference implementation of the fixed priority order. If the
// resolver ever drifts from this ordering the property fails.
function expectedState(i: UniversalStateInput): UniversalState {
  if (i.isOffline) return "offline";
  if (i.isError) return "error";
  if (i.isDegraded) return "degraded";
  if (i.isLoading) return "loading";
  if (i.itemCount === 0) return "empty";
  return "populated";
}

const arbInput: fc.Arbitrary<UniversalStateInput> = fc.record({
  isLoading: fc.boolean(),
  isError: fc.boolean(),
  isOffline: fc.boolean(),
  isDegraded: fc.boolean(),
  // include negatives to prove only 0 is "empty" and any other count populates
  itemCount: fc.integer({ min: -5, max: 10_000 }),
});

describe("Property 30: universal-state resolution is total and distinct", () => {
  it("is total: every input maps to exactly one of the six canonical states", () => {
    fc.assert(
      fc.property(arbInput, (i) => {
        const state = resolveUniversalState(i);
        expect(ALL_STATES.has(state)).toBe(true);
      }),
      { numRuns: 300 },
    );
  });

  it("honors the fixed priority offline > error > degraded > loading > empty > populated", () => {
    fc.assert(
      fc.property(arbInput, (i) => {
        expect(resolveUniversalState(i)).toBe(expectedState(i));
      }),
      { numRuns: 300 },
    );
  });

  it("keeps empty / error / offline mutually distinct render conditions", () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 10_000 }), (count) => {
        // An offline-only input, an error-only (online) input, and a quiet
        // empty input must resolve to three different states — a dropped
        // connection and a failed load are never confused with "no data yet".
        const offline = resolveUniversalState({
          isLoading: false,
          isError: false,
          isOffline: true,
          isDegraded: false,
          itemCount: count,
        });
        const error = resolveUniversalState({
          isLoading: false,
          isError: true,
          isOffline: false,
          isDegraded: false,
          itemCount: count,
        });
        const empty = resolveUniversalState({
          isLoading: false,
          isError: false,
          isOffline: false,
          isDegraded: false,
          itemCount: 0,
        });
        expect(offline).toBe("offline");
        expect(error).toBe("error");
        expect(empty).toBe("empty");
        expect(new Set([offline, error, empty]).size).toBe(3);
      }),
      { numRuns: 100 },
    );
  });
});
