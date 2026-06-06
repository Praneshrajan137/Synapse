import { useFocusStore } from "@state/focus.store";
import { beforeEach, describe, expect, it } from "vitest";

describe("focus.store — lens-pivot focus", () => {
  beforeEach(() => {
    useFocusStore.getState().clearFocus();
  });

  it("starts with no focus", () => {
    expect(useFocusStore.getState().focus).toBeNull();
  });

  it("sets and clears a focus target", () => {
    useFocusStore.getState().setFocus({ kind: "decision", id: "d-1", label: "Decision 1" });
    expect(useFocusStore.getState().focus).toEqual({
      kind: "decision",
      id: "d-1",
      label: "Decision 1",
    });
    useFocusStore.getState().clearFocus();
    expect(useFocusStore.getState().focus).toBeNull();
  });

  it("replaces the focus on a new set (single focus, not a stack)", () => {
    useFocusStore.getState().setFocus({ kind: "agent", id: "demand_prophet" });
    useFocusStore.getState().setFocus({ kind: "sku", id: "SKU-42" });
    expect(useFocusStore.getState().focus?.kind).toBe("sku");
    expect(useFocusStore.getState().focus?.id).toBe("SKU-42");
  });
});
