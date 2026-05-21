import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// FE-INV-030 — telemetry beacons fire and are batched.

describe("log telemetry", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("flushes via sendBeacon on batch threshold", async () => {
    const beacon = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, "sendBeacon", {
      configurable: true,
      writable: true,
      value: beacon,
    });
    const { log } = await import("@lib/log");
    for (let i = 0; i < 20; i++) {
      log({ kind: "web_vitals", metric: "LCP", value: i });
    }
    expect(beacon).toHaveBeenCalled();
    expect(beacon.mock.calls.length).toBe(20);
  });
});
