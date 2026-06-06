import { describe, expect, it } from "vitest";
import { OBJECTIVE_AGENT, PARETO_OBJECTIVES, axisExtents, kneePointIndex } from "../pareto";

const obj = PARETO_OBJECTIVES;

function row(values: number[]): Record<string, number> {
  const r: Record<string, number> = {};
  obj.forEach((o, i) => {
    r[o] = values[i] ?? 0;
  });
  return r;
}

describe("PARETO_OBJECTIVES + mapping", () => {
  it("has the eight objectives mapped 1:1 to the eight agents", () => {
    expect(obj).toHaveLength(8);
    const agents = new Set(Object.values(OBJECTIVE_AGENT));
    expect(agents.size).toBe(8);
  });
});

describe("axisExtents", () => {
  it("computes per-objective min/max across the front", () => {
    const front = [row([0.2, 0, 0, 0, 0, 0, 0, 0]), row([0.8, 0, 0, 0, 0, 0, 0, 0])];
    const ext = axisExtents(front);
    expect(ext.demand_accuracy).toEqual({ min: 0.2, max: 0.8 });
  });

  it("defaults to [0,1] for an objective with no finite values", () => {
    const ext = axisExtents([]);
    expect(ext.route_efficiency).toEqual({ min: 0, max: 1 });
  });
});

describe("kneePointIndex — mirrors pareto.py weighted distance-to-ideal", () => {
  it("returns null for an empty front and 0 for a singleton", () => {
    expect(kneePointIndex([], {})).toBeNull();
    expect(kneePointIndex([row([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])], {})).toBe(0);
  });

  it("picks the solution nearest the per-objective ideal under equal weights", () => {
    // Three solutions; the middle dominates on the balance of objectives.
    const front = [
      row([0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]), // great at demand only
      row([0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8]), // balanced & high
      row([0.1, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]), // great at route only
    ];
    const knee = kneePointIndex(front, {});
    expect(knee).toBe(1);
  });

  it("shifts the knee when an objective is weighted up (the Steering lever)", () => {
    const front = [
      row([0.95, 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]), // strong demand
      row([0.2, 0.95, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]), // strong route
    ];
    // Heavily weight route_efficiency → the route-strong solution wins.
    const knee = kneePointIndex(front, { route_efficiency: 5 });
    expect(knee).toBe(1);
    // Heavily weight demand_accuracy → the demand-strong solution wins.
    const knee2 = kneePointIndex(front, { demand_accuracy: 5 });
    expect(knee2).toBe(0);
  });

  it("tolerates missing objective keys in a row (treats as the axis min)", () => {
    const front = [{ demand_accuracy: 0.9 }, { demand_accuracy: 0.1 }];
    expect(kneePointIndex(front, {})).toBe(0);
  });
});
