import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { __resetDemoModeForTests, isDemoMode, now } from ".";

const ORIGINAL_LOCATION = window.location;

function setSearch(query: string): void {
  vi.stubGlobal("location", { ...ORIGINAL_LOCATION, search: query });
}

describe("demo-mode", () => {
  beforeEach(() => __resetDemoModeForTests());
  afterEach(() => {
    vi.unstubAllGlobals();
    __resetDemoModeForTests();
  });

  it("is off by default", () => {
    setSearch("");
    expect(isDemoMode()).toBe(false);
  });

  it("activates with ?demo=1", () => {
    setSearch("?demo=1");
    expect(isDemoMode()).toBe(true);
  });

  it("now() advances monotonically in demo mode (no two equal ticks)", () => {
    setSearch("?demo=1");
    const samples = Array.from({ length: 10 }, () => now());
    const unique = new Set(samples);
    expect(unique.size).toBe(samples.length);
    expect(samples[0]).toBeLessThan(samples[samples.length - 1]!);
  });

  it("now() falls through to wall clock when demo is off", () => {
    setSearch("");
    const before = Date.now();
    const t = now();
    const after = Date.now();
    expect(t).toBeGreaterThanOrEqual(before);
    expect(t).toBeLessThanOrEqual(after);
  });
});
