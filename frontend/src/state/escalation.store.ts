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

/**
 * Pure reducer for appending an escalation (Req 10.6, FE-INV-034 family).
 *
 * At-most-once per decision: the same escalation can arrive via BOTH the
 * legacy `/ws/escalation` socket and the firehose `escalation` channel
 * (ADR-044), and replays after reconnect re-deliver it. A duplicate
 * `decision_id` is the same escalation — never a second entry, and crucially
 * a replay of an already-acted decision must NOT reset its status to pending.
 * Returns the same array reference when the decision is already present so a
 * replay is a genuine no-op.
 *
 * Extracted as a standalone pure function so the at-most-once property
 * (Property 33 / task 13.8) can exercise it directly without React state.
 */
export function appendEscalationEntry(
  entries: ReadonlyArray<EscalationEntry>,
  message: EscalationMessage,
  now: number = Date.now(),
): ReadonlyArray<EscalationEntry> {
  if (entries.some((e) => e.id === message.decision_id)) return entries;
  const entry: EscalationEntry = {
    id: message.decision_id,
    received_at: now,
    message,
    status: "pending",
  };
  return [...entries, entry];
}

/** Pure reducer for marking an escalation acted (Req 10.6). */
export function markEscalationActed(
  entries: ReadonlyArray<EscalationEntry>,
  id: string,
  action: "approved" | "rejected" | "modified",
): ReadonlyArray<EscalationEntry> {
  return entries.map((e) => (e.id === id ? { ...e, status: "acted", acted_action: action } : e));
}

export const useEscalationStore = create<EscalationState>((set) => ({
  entries: [],
  connected: false,
  append(message) {
    set((s) => ({ entries: appendEscalationEntry(s.entries, message) }));
  },
  markActed(id, action) {
    set((s) => ({ entries: markEscalationActed(s.entries, id, action) }));
  },
  setConnected(connected) {
    set({ connected });
  },
}));
