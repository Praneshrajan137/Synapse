import { create } from "zustand";

/**
 * Focus store — the lens-pivot substrate (SENSORIUM P4: "one ontology, many
 * lenses").
 *
 * Every surface is a projection of the same supply-graph ontology. When the
 * operator selects an object (a decision, an agent, a SKU, a store) it stays
 * in focus as they pivot between the map, the graph, the Tribunal, and the
 * council — so attention is never lost on a context switch.
 *
 * Deliberately tiny and transport-free: surfaces read `focus` and write via
 * `setFocus`. Append-only in spirit — there is no history mutation, only the
 * current focus and an explicit clear.
 */

export type FocusKind = "decision" | "agent" | "sku" | "store" | "supplier";

export interface FocusTarget {
  readonly kind: FocusKind;
  readonly id: string;
  readonly label?: string;
}

interface FocusState {
  readonly focus: FocusTarget | null;
  setFocus(target: FocusTarget): void;
  clearFocus(): void;
}

export const useFocusStore = create<FocusState>((set) => ({
  focus: null,
  setFocus(target) {
    set({ focus: target });
  },
  clearFocus() {
    set({ focus: null });
  },
}));
