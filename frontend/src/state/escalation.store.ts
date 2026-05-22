import type { EscalationMessage } from "@domain/escalation";
import { create } from "zustand";

// Append-only escalation feed (mirror of I-14).
// We never mutate or remove items; "dismissed" or "acted upon" status is
// stored as additional flags. This is enforced by exposing only `append`
// and `markActed` — there is no `clear` / `pop`.

export interface EscalationEntry {
  readonly id: string;
  readonly received_at: number;
  readonly message: EscalationMessage;
  readonly status: "pending" | "acted" | "expired";
  readonly acted_action?: "approved" | "rejected" | "modified";
}

interface EscalationState {
  readonly entries: ReadonlyArray<EscalationEntry>;
  readonly connected: boolean;
  append(message: EscalationMessage): void;
  markActed(id: string, action: "approved" | "rejected" | "modified"): void;
  setConnected(connected: boolean): void;
}

export const useEscalationStore = create<EscalationState>((set) => ({
  entries: [],
  connected: false,
  append(message) {
    const entry: EscalationEntry = {
      id: message.decision_id,
      received_at: Date.now(),
      message,
      status: "pending",
    };
    set((s) => ({ entries: [...s.entries, entry] }));
  },
  markActed(id, action) {
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, status: "acted", acted_action: action } : e,
      ),
    }));
  },
  setConnected(connected) {
    set({ connected });
  },
}));
