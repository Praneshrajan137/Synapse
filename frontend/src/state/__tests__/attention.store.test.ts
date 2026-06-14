import type { DisruptionAlert } from "@domain/disruption-alert";
import type { TwinDivergenceEvent } from "@domain/twin-state";
import type { SystemPosture } from "@transport/synapse-api";
import { describe, expect, it } from "vitest";
import { type AttentionInput, rankAttention } from "../attention.store";
import type { EscalationEntry } from "../escalation.store";

function baseInput(over: Partial<AttentionInput> = {}): AttentionInput {
  return {
    escalations: [],
    posture: undefined,
    postureError: false,
    disruptions: [],
    twin: [],
    connection: "open",
    acknowledged: {},
    ...over,
  };
}

function escalation(id: string, status: EscalationEntry["status"] = "pending"): EscalationEntry {
  return {
    id,
    received_at: Date.now(),
    status,
    message: {
      type: "escalation",
      decision_id: id,
      confidence: 0.6,
      proposals: [],
      violations: [],
    },
  } as EscalationEntry;
}

function disruption(level: number, id = "d1"): DisruptionAlert {
  return {
    alert_id: id,
    alert_level: level,
    anomaly_scores: {
      isolation_forest: 0.5,
      lstm_autoencoder: 0.5,
      gnn_structural: 0.5,
      ensemble_weighted: 0.5,
    },
    affected_nodes: ["n1"],
    playbook_id: "PB",
    reasoning_chain: "x",
    timestamp: "2026-06-14T10:00:00+00:00",
    confidence: 0.8,
  } as DisruptionAlert;
}

describe("rankAttention", () => {
  it("returns nothing when all is well", () => {
    expect(rankAttention(baseInput())).toEqual([]);
  });

  it("raises a pending escalation as an actionable item routed to the cockpit", () => {
    const items = rankAttention(baseInput({ escalations: [escalation("a")] }));
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("escalation");
    expect(items[0]?.actionable).toBe(true);
    expect(items[0]?.route).toBe("/cockpit");
    expect(items[0]?.count).toBe(1);
  });

  it("ignores acted escalations", () => {
    expect(rankAttention(baseInput({ escalations: [escalation("a", "acted")] }))).toEqual([]);
  });

  it("ranks the human-in-the-loop escalation above an equally-severe degradation", () => {
    const posture = { degraded: true, breakers: { demand: "open" }, brownout: {} } as SystemPosture;
    const items = rankAttention(baseInput({ escalations: [escalation("a")], posture }));
    expect(items[0]?.kind).toBe("escalation"); // kind priority breaks the tie
    expect(items[1]?.kind).toBe("degradation");
  });

  it("escalates a critical-level disruption above a high degradation", () => {
    const posture = { degraded: true, breakers: { demand: "open" }, brownout: {} } as SystemPosture;
    const items = rankAttention(baseInput({ disruptions: [disruption(9)], posture }));
    expect(items[0]?.kind).toBe("disruption"); // critical severity outranks high
    expect(items[0]?.severity).toBe("critical");
  });

  it("ignores low-level disruptions and sub-threshold twin divergence", () => {
    const items = rankAttention(
      baseInput({
        disruptions: [disruption(3)],
        twin: [{ kl_divergence: 0.05 } as TwinDivergenceEvent],
      }),
    );
    expect(items).toEqual([]);
  });

  it("raises twin divergence above the I-12 threshold", () => {
    const items = rankAttention(
      baseInput({ twin: [{ kl_divergence: 0.42 } as TwinDivergenceEvent] }),
    );
    expect(items[0]?.kind).toBe("divergence");
    expect(items[0]?.route).toBe("/twin");
  });

  it("alarms on a dropped live feed", () => {
    const items = rankAttention(baseInput({ connection: "closed" }));
    expect(items[0]?.kind).toBe("connection");
  });

  it("suppresses an acknowledged informational item but never an escalation", () => {
    const posture = { degraded: true, breakers: { demand: "open" }, brownout: {} } as SystemPosture;
    const degKey = "deg:demand|";
    const items = rankAttention(
      baseInput({
        escalations: [escalation("a")],
        posture,
        acknowledged: { [degKey]: Date.now() },
      }),
    );
    // degradation acked away; escalation remains (actionable, non-suppressible)
    expect(items).toHaveLength(1);
    expect(items[0]?.kind).toBe("escalation");
  });

  it("treats unreachable posture as degraded (medium), never silently healthy", () => {
    const items = rankAttention(baseInput({ postureError: true }));
    expect(items[0]?.kind).toBe("degradation");
    expect(items[0]?.severity).toBe("medium");
  });
});
