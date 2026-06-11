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
    // At-most-once per decision (FE-INV-034 family): the same escalation can
    // now arrive via BOTH the legacy /ws/escalation socket and the firehose
    // `escalation` channel (ADR-044), and replays after reconnect re-deliver.
    // A duplicate decision_id is the same escalation — never a second entry.
    set((s) => (s.entries.some((e) => e.id === entry.id) ? s : { entries: [...s.entries, entry] }));
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
