import { describe, expect, it } from "vitest";
import { decideRetry, fullJitterDelay } from "../jitter-retry";

// FE-INV-006 — Full Jitter retry on 5xx + network; honor Retry-After on 429.
describe("fullJitterDelay", () => {
  it("stays within [0, cap] regardless of attempt count", () => {
    for (let attempt = 0; attempt < 20; attempt++) {
      const delay = fullJitterDelay(attempt, { baseMs: 100, capMs: 5_000 });
      expect(delay).toBeGreaterThanOrEqual(0);
      expect(delay).toBeLessThanOrEqual(5_000);
    }
  });

  it("respects a deterministic RNG", () => {
    const delay = fullJitterDelay(3, { baseMs: 100, capMs: 5_000, random: () => 0.5 });
    expect(delay).toBe(400);
  });
});

describe("decideRetry", () => {
  it("retries 5xx for retryable attempts", () => {
    const d = decideRetry({ attempt: 0, status: 502 });
    expect(d.retry).toBe(true);
    expect(d.delayMs).toBeGreaterThanOrEqual(0);
  });

  it("does not retry 4xx other than 429", () => {
    expect(decideRetry({ attempt: 0, status: 400 }).retry).toBe(false);
    expect(decideRetry({ attempt: 0, status: 404 }).retry).toBe(false);
  });

  it("honors numeric Retry-After on 429", () => {
    const d = decideRetry({ attempt: 0, status: 429, retryAfterHeader: "3" });
    expect(d.retry).toBe(true);
    expect(d.delayMs).toBe(3_000);
  });

  it("retries network errors with jitter", () => {
    const d = decideRetry({ attempt: 1, isNetworkError: true });
    expect(d.retry).toBe(true);
  });

  it("stops after maxAttempts - 1", () => {
    const d = decideRetry({ attempt: 4, status: 502, options: { maxAttempts: 5 } });
    expect(d.retry).toBe(false);
  });
});
