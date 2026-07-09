import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { decideRetry, fullJitterDelay } from "../jitter-retry";

// Feature: atlas-console-elevation
// Property 31: Retry policy is correct across failure classes
//
// `decideRetry` applies Full-Jitter retry to transient failures (5xx /
// network) bounded by the cap, honors `Retry-After` on 429, and short-circuits
// (no retry) on non-429 4xx. All decisions respect the maxAttempts budget.
//
// **Validates: Requirements 10.2, 10.3, 10.4**

const DEFAULT_MAX = 5;

// A retryable attempt is any attempt strictly below maxAttempts - 1.
const arbRetryableAttempt = fc.integer({ min: 0, max: DEFAULT_MAX - 2 });
const arbCapMs = fc.integer({ min: 1, max: 60_000 });
const arbBaseMs = fc.integer({ min: 1, max: 2_000 });
const arbRandom = fc.double({ min: 0, max: 0.999999, noNaN: true });

describe("Property 31: retry policy is correct across failure classes", () => {
  it("retries transient 5xx bounded by the cap on retryable attempts", () => {
    fc.assert(
      fc.property(
        arbRetryableAttempt,
        fc.integer({ min: 500, max: 599 }),
        arbCapMs,
        arbBaseMs,
        arbRandom,
        (attempt, status, capMs, baseMs, r) => {
          const d = decideRetry({
            attempt,
            status,
            options: { capMs, baseMs, maxAttempts: DEFAULT_MAX, random: () => r },
          });
          expect(d.retry).toBe(true);
          expect(d.delayMs).toBeGreaterThanOrEqual(0);
          expect(d.delayMs).toBeLessThanOrEqual(capMs);
        },
      ),
      { numRuns: 300 },
    );
  });

  it("retries transient network errors bounded by the cap on retryable attempts", () => {
    fc.assert(
      fc.property(
        arbRetryableAttempt,
        arbCapMs,
        arbBaseMs,
        arbRandom,
        (attempt, capMs, baseMs, r) => {
          const d = decideRetry({
            attempt,
            isNetworkError: true,
            options: { capMs, baseMs, maxAttempts: DEFAULT_MAX, random: () => r },
          });
          expect(d.retry).toBe(true);
          expect(d.delayMs).toBeGreaterThanOrEqual(0);
          expect(d.delayMs).toBeLessThanOrEqual(capMs);
        },
      ),
      { numRuns: 300 },
    );
  });

  it("honors a numeric Retry-After on 429 exactly (seconds -> ms)", () => {
    fc.assert(
      fc.property(arbRetryableAttempt, fc.integer({ min: 0, max: 3_600 }), (attempt, seconds) => {
        const d = decideRetry({
          attempt,
          status: 429,
          retryAfterHeader: String(seconds),
          options: { maxAttempts: DEFAULT_MAX },
        });
        expect(d.retry).toBe(true);
        expect(d.delayMs).toBe(seconds * 1000);
      }),
      { numRuns: 200 },
    );
  });

  it("short-circuits (no retry) on non-429 4xx regardless of attempt", () => {
    const arb4xxNon429 = fc.integer({ min: 400, max: 499 }).filter((s) => s !== 429);
    fc.assert(
      fc.property(fc.integer({ min: 0, max: DEFAULT_MAX - 2 }), arb4xxNon429, (attempt, status) => {
        const d = decideRetry({ attempt, status, options: { maxAttempts: DEFAULT_MAX } });
        expect(d.retry).toBe(false);
        expect(d.delayMs).toBe(0);
      }),
      { numRuns: 300 },
    );
  });

  it("never retries once the attempt budget is exhausted, even for transient failures", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 12 }),
        fc.oneof(fc.constant<number | undefined>(503), fc.constant<number | undefined>(429)),
        fc.boolean(),
        (max, status, isNetworkError) => {
          const d = decideRetry({
            attempt: max - 1,
            ...(status !== undefined ? { status } : {}),
            isNetworkError,
            retryAfterHeader: "1",
            options: { maxAttempts: max },
          });
          expect(d.retry).toBe(false);
          expect(d.delayMs).toBe(0);
        },
      ),
      { numRuns: 200 },
    );
  });

  it("full-jitter delay always lands within [0, cap]", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 40 }),
        arbCapMs,
        arbBaseMs,
        arbRandom,
        (attempt, capMs, baseMs, r) => {
          const delay = fullJitterDelay(attempt, { capMs, baseMs, random: () => r });
          expect(delay).toBeGreaterThanOrEqual(0);
          expect(delay).toBeLessThanOrEqual(capMs);
        },
      ),
      { numRuns: 300 },
    );
  });
});
