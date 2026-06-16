import type { CognitionEvent } from "@domain/cognition-event";
import type { LiveDecision } from "@domain/decision-envelope";
import type { DemandForecast } from "@domain/demand-forecast";
import type { DisruptionAlert } from "@domain/disruption-alert";
import type { FreshnessAlert } from "@domain/freshness-alert";
import type { PricingUpdate } from "@domain/pricing-update";
import type { RoutePlan } from "@domain/route-plan";
import type { TwinDivergenceEvent } from "@domain/twin-state";
import type { WsState } from "@transport/ws-multiplex";
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
  twin: Bounded<TwinDivergenceEvent>;
  pricing: Bounded<PricingUpdate>;
  freshness: Bounded<FreshnessAlert>;
  // ADR-048: live cognition phase events (the council's FSM transitions).
  cognition: Bounded<CognitionEvent>;
  // Live WS state of the currently-mounted firehose, lifted here so the
  // Shell-level attention beacon can alarm on a dropped feed without owning a
  // second socket. Surfaces reset it to "idle" on unmount (no phantom offline).
  connection: WsState;
  setConnection(state: WsState): void;
  lastSeq: Readonly<Record<string, number>>;
  appendDecision(d: LiveDecision, seq: number): void;
  appendDisruption(d: DisruptionAlert, seq: number): void;
  appendRoute(r: RoutePlan, seq: number): void;
  appendDemand(d: DemandForecast, seq: number): void;
  appendTwin(t: TwinDivergenceEvent, seq: number): void;
  appendPricing(p: PricingUpdate, seq: number): void;
  appendFreshness(f: FreshnessAlert, seq: number): void;
  appendCognition(c: CognitionEvent, seq: number): void;
  flushAll(): void;
}

export const useFirehoseStore = create<FirehoseState>((set) => ({
  decisions: newBounded(200),
  disruptions: newBounded(50),
  routes: newBounded(200),
  demand: newBounded(500),
  twin: newBounded(100),
  pricing: newBounded(200),
  freshness: newBounded(200),
  cognition: newBounded(200),
  connection: "idle",
  setConnection(state) {
    set({ connection: state });
  },
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
  appendPricing(p, seq) {
    set((s) => ({ pricing: appendBounded(s.pricing, p), lastSeq: { ...s.lastSeq, pricing: seq } }));
  },
  appendFreshness(f, seq) {
    set((s) => ({
      freshness: appendBounded(s.freshness, f),
      lastSeq: { ...s.lastSeq, freshness: seq },
    }));
  },
  appendCognition(c, seq) {
    set((s) => ({
      cognition: appendBounded(s.cognition, c),
      lastSeq: { ...s.lastSeq, cognition: seq },
    }));
  },
  flushAll() {
    set({
      decisions: newBounded(200),
      disruptions: newBounded(50),
      routes: newBounded(200),
      demand: newBounded(500),
      twin: newBounded(100),
      pricing: newBounded(200),
      freshness: newBounded(200),
      cognition: newBounded(200),
      lastSeq: {},
    });
  },
}));
