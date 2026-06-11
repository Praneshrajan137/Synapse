import type { LiveDecision } from "@domain/decision-envelope";
import type { DemandForecast } from "@domain/demand-forecast";
import type { DisruptionAlert } from "@domain/disruption-alert";
import type { RoutePlan } from "@domain/route-plan";
import type { TwinState } from "@domain/twin-state";
import { create } from "zustand";

// Per-channel bounded ring buffers (append-only — FE-INV-017). Switching
// city flushes the channels (the underlying topics carry city-scoped data,
// so cross-city remnants would be misleading).

interface Bounded<T> {
  readonly cap: number;
  readonly items: ReadonlyArray<T>;
}

const newBounded = <T>(cap: number): Bounded<T> => ({ cap, items: [] });

function appendBounded<T>(b: Bounded<T>, value: T): Bounded<T> {
  const items = b.items.length >= b.cap ? [...b.items.slice(1), value] : [...b.items, value];
  return { cap: b.cap, items };
}

interface FirehoseState {
  decisions: Bounded<LiveDecision>;
  disruptions: Bounded<DisruptionAlert>;
  routes: Bounded<RoutePlan>;
  demand: Bounded<DemandForecast>;
  twin: Bounded<TwinState>;
  lastSeq: Readonly<Record<string, number>>;
  appendDecision(d: LiveDecision, seq: number): void;
  appendDisruption(d: DisruptionAlert, seq: number): void;
  appendRoute(r: RoutePlan, seq: number): void;
  appendDemand(d: DemandForecast, seq: number): void;
  appendTwin(t: TwinState, seq: number): void;
  flushAll(): void;
}

export const useFirehoseStore = create<FirehoseState>((set) => ({
  decisions: newBounded(200),
  disruptions: newBounded(50),
  routes: newBounded(200),
  demand: newBounded(500),
  twin: newBounded(100),
  lastSeq: {},
  appendDecision(d, seq) {
    set((s) => ({
      decisions: appendBounded(s.decisions, d),
      lastSeq: { ...s.lastSeq, decision: seq },
    }));
  },
  appendDisruption(d, seq) {
    set((s) => ({
      disruptions: appendBounded(s.disruptions, d),
      lastSeq: { ...s.lastSeq, disruption: seq },
    }));
  },
  appendRoute(r, seq) {
    set((s) => ({
      routes: appendBounded(s.routes, r),
      lastSeq: { ...s.lastSeq, routing: seq },
    }));
  },
  appendDemand(d, seq) {
    set((s) => ({
      demand: appendBounded(s.demand, d),
      lastSeq: { ...s.lastSeq, demand: seq },
    }));
  },
  appendTwin(t, seq) {
    set((s) => ({ twin: appendBounded(s.twin, t), lastSeq: { ...s.lastSeq, twin: seq } }));
  },
  flushAll() {
    set({
      decisions: newBounded(200),
      disruptions: newBounded(50),
      routes: newBounded(200),
      demand: newBounded(500),
      twin: newBounded(100),
      lastSeq: {},
    });
  },
}));
