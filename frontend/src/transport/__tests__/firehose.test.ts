import { afterEach, describe, expect, it, vi } from "vitest";
import { createFirehose } from "../firehose";

class MockWebSocket {
  static readonly OPEN = 1;

  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
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
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent<string>);
  }
}

const sockets: MockWebSocket[] = [];

function installWebSocket(): void {
  sockets.length = 0;
  vi.stubGlobal("WebSocket", MockWebSocket);
}

function demandPayload() {
  return {
    sku_id: "sku-1",
    store_id: "store-1",
    forecast_timestamp: "2026-06-06T00:00:00.000Z",
    horizons: { "15min": 12, "1h": 28 },
    lower_90: { "15min": 9, "1h": 22 },
    upper_90: { "15min": 15, "1h": 34 },
    confidence: 0.87,
    drift_detected: false,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sockets.length = 0;
});

// FE-INV-002 + FE-INV-008: firehose subscribers receive only typed payloads
// from validated envelopes. ADR-053 gave the `metric` channel a real producer +
// schema, so it now validates like every other channel (no more open-shape).
describe("createFirehose", () => {
  it("constructs the firehose URL with topics, city, host, and since_seq", () => {
    installWebSocket();

    createFirehose({
      host: "api.synapse.test",
      topics: ["demand", "metric"],
      city: "mumbai",
      sinceSeq: 42,
    });

    expect(sockets[0]?.url).toBe(
      "ws://api.synapse.test/ws/firehose?topics=demand%2Cmetric&city=mumbai&since_seq=42",
    );
  });

  it("validates typed metric payloads (ADR-053) and rejects malformed ones", () => {
    installWebSocket();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const firehose = createFirehose({
      host: "api.synapse.test",
      topics: ["metric"],
      city: "bengaluru",
    });
    const listener = vi.fn();
    firehose.on("metric", listener);
    sockets[0]?.open();

    const metric = {
      agent_name: "demand_prophet",
      decision_id: "11111111-1111-4111-8111-111111111111",
      tier: "tier_2",
      confidence: 0.83,
      degraded: false,
      ts: "2026-06-06T00:00:00.000Z",
    };
    sockets[0]?.message({
      topic: "metric",
      seq: 3,
      ts: "2026-06-06T00:00:00.000Z",
      payload: metric,
    });
    // Old open-shape payload ({name,value}) is no longer valid — rejected.
    sockets[0]?.message({
      topic: "metric",
      seq: 4,
      ts: "2026-06-06T00:00:00.000Z",
      payload: { name: "tier_route_ms", value: 41 },
    });

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(metric, { seq: 3, ts: "2026-06-06T00:00:00.000Z" });
    expect(warn).toHaveBeenCalledOnce();
  });

  it("validates typed demand payloads and rejects malformed ones", () => {
    installWebSocket();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const firehose = createFirehose({
      host: "api.synapse.test",
      topics: ["demand"],
      city: "bengaluru",
    });
    const listener = vi.fn();
    firehose.on("demand", listener);
    sockets[0]?.open();

    const envelope = {
      topic: "demand",
      seq: 11,
      ts: "2026-06-06T00:00:00.000Z",
      payload: demandPayload(),
    };
    sockets[0]?.message(envelope);
    sockets[0]?.message({ ...envelope, seq: 12, payload: { sku_id: "sku-1" } });
    sockets[0]?.message({ topic: "demand", seq: 13, payload: demandPayload() });

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(demandPayload(), {
      seq: 11,
      ts: "2026-06-06T00:00:00.000Z",
    });
    expect(warn).toHaveBeenCalledOnce();
  });

  it("delegates state subscriptions and close to the multiplex client", () => {
    installWebSocket();
    const firehose = createFirehose({
      host: "api.synapse.test",
      topics: ["metric"],
      city: "bengaluru",
    });
    const states: string[] = [];
    firehose.onState((state) => states.push(state));

    sockets[0]?.open();
    firehose.close();

    expect(states).toEqual(["open", "closing", "closed"]);
    expect(firehose.state()).toBe("closed");
  });
});
