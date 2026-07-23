import type { AutonomyResponse } from "@domain/autonomy";
import { deriveAutonomyView } from "@lib/autonomy";
import { describe, expect, it } from "vitest";

// ADR-053 — the Autonomy Spine's honest display derivation. These pin the
// invariants that keep the loop from ever *looking* healthier than it is.

function world(over: Record<string, unknown> = {}) {
  return {
    city: "bengaluru",
    sim_time_min: 120,
    inventory: { "SKU-1": 55, "SKU-2": 3 },
    pending_orders: 2,
    fill_rate: 0.97,
    spoilage_rate: 0.01,
    avg_delivery_min: 9,
    restocks_triggered: 4,
    demand_rate: 1.2,
    clock_advancing: true,
    is_synthetic: true,
    as_of: "2026-07-20T00:00:00Z",
    ...over,
  };
}

function response(over: Partial<AutonomyResponse> = {}): AutonomyResponse {
  return {
    sensor: { running: true, cities: ["bengaluru"], polls: 40, decisions_triggered: 5 },
    worlds: { bengaluru: world() },
    degraded: false,
    as_of: "2026-07-20T00:00:00Z",
    ...over,
  } as AutonomyResponse;
}

describe("deriveAutonomyView", () => {
  it("is loading before the first read", () => {
    expect(deriveAutonomyView({ data: undefined, isError: false, isPending: true }).kind).toBe(
      "loading",
    );
  });

  it("is 'unknown' on a fetch error / 503 — never a healthy autonomous system", () => {
    const view = deriveAutonomyView({ data: undefined, isError: true, isPending: false });
    expect(view.kind).toBe("unknown");
  });

  it("exposes the authoritative self-initiation counters on a healthy read", () => {
    const view = deriveAutonomyView({ data: response(), isError: false, isPending: false });
    if (view.kind !== "ready") throw new Error("expected ready");
    expect(view.sensorRunning).toBe(true);
    expect(view.decisionsTriggered).toBe(5);
    expect(view.polls).toBe(40);
    expect(view.stalledCities).toEqual([]);
  });

  it("marks a world with a stalled clock as stalled (degraded), never live", () => {
    const view = deriveAutonomyView({
      data: response({ worlds: { bengaluru: world({ clock_advancing: false }) } }),
      isError: false,
      isPending: false,
    });
    if (view.kind !== "ready") throw new Error("expected ready");
    expect(view.worlds[0]?.kind).toBe("stalled");
    expect(view.stalledCities).toContain("bengaluru");
  });

  it("marks a null world as unreachable, never a fabricated snapshot", () => {
    const view = deriveAutonomyView({
      data: response({ worlds: { mumbai: null } }),
      isError: false,
      isPending: false,
    });
    if (view.kind !== "ready") throw new Error("expected ready");
    expect(view.worlds[0]?.kind).toBe("unreachable");
    expect(view.worlds[0]?.fillRate).toBeNull();
    expect(view.stalledCities).toContain("mumbai");
  });

  it("always flags a live world as synthetic (it is a simulation)", () => {
    const view = deriveAutonomyView({ data: response(), isError: false, isPending: false });
    if (view.kind !== "ready") throw new Error("expected ready");
    expect(view.worlds[0]?.synthetic).toBe(true);
    expect(view.worlds[0]?.skuCount).toBe(2);
  });

  it("reports a null sensor as not-running without crashing", () => {
    const view = deriveAutonomyView({
      data: response({ sensor: null }),
      isError: false,
      isPending: false,
    });
    if (view.kind !== "ready") throw new Error("expected ready");
    expect(view.sensorRunning).toBe(false);
    expect(view.sensorReachable).toBe(false);
    expect(view.decisionsTriggered).toBeNull();
  });
});
