import { useFirehose } from "@hooks/use-firehose";
import { useFirehoseStore } from "@state/firehose.store";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Only the socket is doubled: the hook, the typed firehose client and the real
// ws-multiplex all run, so each assertion is about what a subscribing surface
// receives, not about the plumbing in between.
class MockWebSocket {
  static readonly OPEN = 1;

  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;

  constructor(readonly url: string) {
    sockets.push(this);
  }

  send(_data: string): void {}

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  open(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  message(data: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data) }));
  }
}

const sockets: MockWebSocket[] = [];

const TS = "2026-06-06T00:00:00.000Z";

const DECISION = {
  decision_id: "11111111-1111-4111-8111-111111111111",
  tier: "tier_2",
  confidence: 0.9,
};

const DEMAND = {
  sku_id: "sku-1",
  store_id: "store-1",
  forecast_timestamp: TS,
  horizons: { "15min": 12 },
  lower_90: { "15min": 9 },
  upper_90: { "15min": 15 },
  confidence: 0.87,
  drift_detected: false,
};

function frame(topic: string, seq: number, payload: unknown) {
  return { topic, seq, ts: TS, payload };
}

beforeEach(() => {
  sockets.length = 0;
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
  useFirehoseStore.getState().flushAll();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// Req 8.2: a schema-violating payload must surface as the error state, which a
// surface can only render if the hook reports the rejection instead of the
// transport dropping it with a console line.
describe("useFirehose", () => {
  it("surfaces a schema-rejected payload instead of dropping it silently", () => {
    const { result } = renderHook(() => useFirehose({ topics: ["decision"] }));
    act(() => sockets[0]?.open());
    expect(result.current.connected).toBe(true);
    expect(result.current.rejections).toEqual([]);

    const poison = frame("decision", 1, { ...DECISION, decision_id: "not-a-uuid" });
    act(() => sockets[0]?.message(poison));

    expect(result.current.rejections).toEqual([
      { channel: "decision", seq: 1, reason: expect.stringContaining("decision_id") },
    ]);
    // The unvalidated payload never reached the store the live tail renders from.
    expect(useFirehoseStore.getState().decisions.items).toHaveLength(0);
  });

  it("clears a rejection only when a valid frame on the same channel is accepted", () => {
    const { result } = renderHook(() => useFirehose({ topics: ["decision", "demand"] }));
    act(() => sockets[0]?.open());
    act(() => sockets[0]?.message(frame("decision", 1, { tier: "tier_2" })));
    expect(result.current.rejections.map((rejection) => rejection.channel)).toEqual(["decision"]);

    // A valid frame on ANOTHER channel is not evidence the decision feed recovered.
    act(() => sockets[0]?.message(frame("demand", 1, DEMAND)));
    expect(result.current.rejections.map((rejection) => rejection.channel)).toEqual(["decision"]);

    act(() => sockets[0]?.message(frame("decision", 2, DECISION)));
    expect(result.current.rejections).toEqual([]);
    expect(useFirehoseStore.getState().decisions.items).toHaveLength(1);
  });
});
