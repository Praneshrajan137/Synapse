import type { CognitionEvent } from "@domain/cognition-event";
import { deriveLiveCognition, phaseLabel } from "@lib/cognition";
import { describe, expect, it } from "vitest";

const NOW = Date.parse("2026-06-16T10:00:10.000Z");

function ev(overrides: Partial<CognitionEvent> = {}): CognitionEvent {
  return {
    decision_id: "11111111-1111-4111-8111-111111111111",
    phase: "collecting",
    ts: "2026-06-16T10:00:09.000Z",
    ...overrides,
  } as CognitionEvent;
}

describe("deriveLiveCognition", () => {
  it("returns null for an empty buffer", () => {
    expect(deriveLiveCognition([], NOW)).toBeNull();
  });

  it("returns null when the latest event is stale — never paints a dead council live", () => {
    expect(deriveLiveCognition([ev({ ts: "2026-06-16T09:00:00.000Z" })], NOW)).toBeNull();
  });

  it("during collecting: proposed agents act, the rest think (derived from real events)", () => {
    const live = deriveLiveCognition(
      [
        ev({ phase: "collecting" }),
        ev({ phase: "collecting", agent_name: "demand_prophet", event: "proposed" }),
      ],
      NOW,
    );
    expect(live?.phase).toBe("collecting");
    expect(live?.agentStates.demand_prophet).toBe("acting");
    expect(live?.agentStates.pricing_oracle).toBe("thinking");
  });

  it("during debating: the whole council is debating", () => {
    const live = deriveLiveCognition([ev({ phase: "debating", round: 1 })], NOW);
    expect(live?.phase).toBe("debating");
    expect(live?.agentStates.demand_prophet).toBe("debating");
  });

  it("during executing: the council is acting", () => {
    const live = deriveLiveCognition([ev({ phase: "executing" })], NOW);
    expect(live?.agentStates.routing_navigator).toBe("acting");
  });

  it("arbitrating/learning invent no per-agent cognition (health fallback, I-7)", () => {
    const live = deriveLiveCognition([ev({ phase: "arbitrating" })], NOW);
    expect(live?.phase).toBe("arbitrating");
    expect(Object.keys(live?.agentStates ?? {})).toHaveLength(0);
  });

  it("treats an event with no parseable ts as live (recent by buffer nature)", () => {
    expect(deriveLiveCognition([ev({ ts: undefined })], NOW)).not.toBeNull();
  });

  it("scopes per-agent state to the latest decision id", () => {
    const live = deriveLiveCognition(
      [
        ev({
          decision_id: "22222222-2222-4222-8222-222222222222",
          phase: "collecting",
          agent_name: "demand_prophet",
          event: "proposed",
        }),
        ev({ decision_id: "11111111-1111-4111-8111-111111111111", phase: "collecting" }),
      ],
      NOW,
    );
    // The latest event is decision 1111 — the 2222 "proposed" must not leak in.
    expect(live?.decisionId).toBe("11111111-1111-4111-8111-111111111111");
    expect(live?.agentStates.demand_prophet).toBe("thinking");
  });
});

describe("phaseLabel", () => {
  it("maps every phase to a human label", () => {
    expect(phaseLabel("collecting")).toMatch(/collecting/);
    expect(phaseLabel("debating")).toBe("debating");
    expect(phaseLabel("arbitrating")).toBe("arbitrating");
    expect(phaseLabel("executing")).toBe("executing");
    expect(phaseLabel("learning")).toBe("learning");
  });
});
