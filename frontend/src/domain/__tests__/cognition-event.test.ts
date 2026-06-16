import { CognitionEventSchema } from "@domain/cognition-event";
import { describe, expect, it } from "vitest";

describe("CognitionEventSchema (ADR-048)", () => {
  it("accepts a well-formed phase event", () => {
    const r = CognitionEventSchema.safeParse({
      type: "cognition_phase",
      decision_id: "11111111-1111-4111-8111-111111111111",
      phase: "debating",
      round: 2,
      ts: "2026-06-16T10:00:00.000Z",
      city: "bengaluru",
    });
    expect(r.success).toBe(true);
  });

  it("accepts a per-agent collect event", () => {
    const r = CognitionEventSchema.safeParse({
      decision_id: "11111111-1111-4111-8111-111111111111",
      phase: "collecting",
      agent_name: "demand_prophet",
      event: "proposed",
    });
    expect(r.success).toBe(true);
  });

  it("rejects an unknown phase (never renders a fabricated cognition state)", () => {
    const r = CognitionEventSchema.safeParse({
      decision_id: "11111111-1111-4111-8111-111111111111",
      phase: "daydreaming",
    });
    expect(r.success).toBe(false);
  });

  it("rejects a non-uuid decision_id", () => {
    const r = CognitionEventSchema.safeParse({ decision_id: "nope", phase: "collecting" });
    expect(r.success).toBe(false);
  });
});
