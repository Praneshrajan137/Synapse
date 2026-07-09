import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { reconnectDelayMs } from "../reconcile";

// Feature: atlas-console-effectiveness
// Property 9: Reconnect delay is Full-Jitter bounded by the exponential cap for
// every attempt.
//
// `reconnectDelayMs(attempt, opts?)` delegates to `fullJitterDelay` and returns
// a uniform Full-Jitter draw from `[0, min(base · 2^attempt, cap)]` (Req 7.3),
// with default `base = 500ms` and `cap = 30000ms`. It accepts an injectable
// `random` in `opts` for deterministic testing. For every attempt ≥ 0 the delay
// must land within `[0, min(base · 2^attempt, cap)]` — it never goes negative,
// never exceeds the exponentially-growing bound, and never exceeds the cap.
//
// **Validates: Requirements 7.3**

// Defaults, mirroring `ws-multiplex` reconnect policy.
const DEFAULT_BASE_MS = 500;
const DEFAULT_CAP_MS = 30_000;

// Attempts span the range where the exponential bound grows and where it has
// long since saturated the cap (2^40 · 500 ≫ 30000).
const arbAttempt = fc.integer({ min: 0, max: 40 });
// A draw in [0, 1) as a real RNG would produce.
const arbRandom = fc.double({ min: 0, max: 0.999999, noNaN: true });
// Custom base/cap values a caller could inject.
const arbBaseMs = fc.integer({ min: 1, max: 5_000 });
const arbCapMs = fc.integer({ min: 1, max: 120_000 });

/** The Full-Jitter upper bound for an attempt: `min(base · 2^attempt, cap)`. */
function exponentialBound(attempt: number, baseMs: number, capMs: number): number {
  return Math.min(capMs, baseMs * 2 ** attempt);
}

describe("Property 9: reconnect delay is Full-Jitter bounded by the exponential cap", () => {
  it("lands within [0, min(base·2^attempt, cap)] using the defaults for every attempt", () => {
    fc.assert(
      fc.property(arbAttempt, arbRandom, (attempt, r) => {
        const delay = reconnectDelayMs(attempt, { random: () => r });
        const bound = exponentialBound(attempt, DEFAULT_BASE_MS, DEFAULT_CAP_MS);
        expect(delay).toBeGreaterThanOrEqual(0);
        expect(delay).toBeLessThanOrEqual(bound);
        // The exponential bound is itself always clamped by the cap.
        expect(delay).toBeLessThanOrEqual(DEFAULT_CAP_MS);
      }),
      { numRuns: 100 },
    );
  });

  it("lands within [0, min(base·2^attempt, cap)] for injected base/cap for every attempt", () => {
    fc.assert(
      fc.property(arbAttempt, arbBaseMs, arbCapMs, arbRandom, (attempt, baseMs, capMs, r) => {
        const delay = reconnectDelayMs(attempt, { baseMs, capMs, random: () => r });
        const bound = exponentialBound(attempt, baseMs, capMs);
        expect(delay).toBeGreaterThanOrEqual(0);
        expect(delay).toBeLessThanOrEqual(bound);
        expect(delay).toBeLessThanOrEqual(capMs);
      }),
      { numRuns: 100 },
    );
  });

  it("saturates at the cap once the exponential bound exceeds it (never overshoots)", () => {
    // For attempts where base·2^attempt ≥ cap the bound is exactly the cap, so a
    // maximal draw yields at most cap - 1 (Full-Jitter is a floor of r·bound).
    const arbSaturatedAttempt = fc.integer({ min: 20, max: 40 });
    fc.assert(
      fc.property(arbSaturatedAttempt, arbRandom, (attempt, r) => {
        const delay = reconnectDelayMs(attempt, { random: () => r });
        expect(exponentialBound(attempt, DEFAULT_BASE_MS, DEFAULT_CAP_MS)).toBe(DEFAULT_CAP_MS);
        expect(delay).toBeGreaterThanOrEqual(0);
        expect(delay).toBeLessThanOrEqual(DEFAULT_CAP_MS);
      }),
      { numRuns: 100 },
    );
  });

  it("draws the full jitter width — r→1 approaches the bound, r=0 yields 0", () => {
    fc.assert(
      fc.property(arbAttempt, (attempt) => {
        const bound = exponentialBound(attempt, DEFAULT_BASE_MS, DEFAULT_CAP_MS);
        // Lower extreme: a zero draw yields exactly 0.
        expect(reconnectDelayMs(attempt, { random: () => 0 })).toBe(0);
        // Upper extreme: a near-1 draw yields at most the bound and, for a
        // positive bound, strictly below it (floor of r·bound with r < 1).
        const high = reconnectDelayMs(attempt, { random: () => 0.999999 });
        expect(high).toBeGreaterThanOrEqual(0);
        expect(high).toBeLessThanOrEqual(bound);
      }),
      { numRuns: 100 },
    );
  });
});
