import { afterEach, describe, expect, it, vi } from "vitest";
import { createWsMultiplex } from "../ws-multiplex";

class MockWebSocket {
  static readonly OPEN = 1;

  readonly sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;

  constructor(readonly url: string) {
    sockets.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  open(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  message(data: unknown): void {
    this.onmessage?.({
      data: typeof data === "string" ? data : JSON.stringify(data),
    } as MessageEvent<string>);
  }

  serverClose(): void {
    this.readyState = 3;
    this.onclose?.();
  }
}

const sockets: MockWebSocket[] = [];

function installWebSocket(): void {
  sockets.length = 0;
  vi.stubGlobal("WebSocket", MockWebSocket);
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sockets.length = 0;
});

// FE-INV-008: one multiplexed socket validates envelopes, dedupes sequence
// numbers, and reconnects with jitter without dropping queued outbound data.
describe("createWsMultiplex", () => {
  it("opens one socket, flushes queued sends, emits state, and sends heartbeats", () => {
    vi.useFakeTimers();
    installWebSocket();
    const states: string[] = [];
    const mux = createWsMultiplex({
      url: () => "ws://synapse.test/ws/firehose",
      heartbeatMs: 10,
    });
    mux.onState((state) => states.push(state));

    mux.send({ type: "subscribe", topic: "decision" });
    expect(mux.state()).toBe("connecting");
    expect(sockets).toHaveLength(1);

    const socket = sockets[0];
    expect(socket?.url).toBe("ws://synapse.test/ws/firehose");
    socket?.open();

    expect(mux.state()).toBe("open");
    expect(states).toEqual(["open"]);
    expect(socket?.sent).toContain('{"type":"subscribe","topic":"decision"}');

    vi.advanceTimersByTime(10);
    expect(socket?.sent).toContain('{"type":"ping"}');

    mux.close();
    expect(mux.state()).toBe("closed");
    expect(states).toEqual(["open", "closing", "closed"]);
  });

  it("routes valid envelopes to channel and wildcard listeners while deduping seq", () => {
    installWebSocket();
    const mux = createWsMultiplex({ url: () => "ws://synapse.test/ws/firehose" });
    const decision = vi.fn();
    const wildcard = vi.fn();
    const unsubscribe = mux.on("decision", decision);
    mux.on("*", wildcard);
    sockets[0]?.open();

    const first = {
      topic: "decision",
      seq: 7,
      ts: "2026-06-06T00:00:00.000Z",
      payload: { ok: true },
    };
    sockets[0]?.message(first);
    sockets[0]?.message(first);
    sockets[0]?.message({ ...first, seq: 8 });

    expect(decision).toHaveBeenCalledTimes(2);
    expect(wildcard).toHaveBeenCalledTimes(2);
    expect(decision.mock.calls[0]?.[0]).toMatchObject({
      kind: "envelope",
      topic: "decision",
      seq: 7,
      payload: { ok: true },
    });
    expect(decision.mock.calls[0]?.[1]).toEqual(first);

    unsubscribe();
    sockets[0]?.message({ ...first, seq: 9 });
    expect(decision).toHaveBeenCalledTimes(2);
    expect(wildcard).toHaveBeenCalledTimes(3);
  });

  it("drops malformed, heartbeat, and schema-invalid frames before fanout", () => {
    installWebSocket();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const mux = createWsMultiplex({ url: () => "ws://synapse.test/ws/firehose" });
    const wildcard = vi.fn();
    mux.on("*", wildcard);
    sockets[0]?.open();

    sockets[0]?.message("not-json");
    sockets[0]?.message({ type: "pong" });
    sockets[0]?.message({ nope: true });
    sockets[0]?.message({ topic: "decision", seq: -1, payload: {} });

    expect(wildcard).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledTimes(2);
  });

  it("routes legacy typed messages by type", () => {
    installWebSocket();
    const mux = createWsMultiplex({ url: () => "ws://synapse.test/ws/escalation" });
    const escalation = vi.fn();
    const wildcard = vi.fn();
    mux.on("decision_escalation", escalation);
    mux.on("*", wildcard);
    sockets[0]?.open();

    sockets[0]?.message({ type: "decision_escalation", payload: { decision_id: "d-1" } });

    expect(escalation).toHaveBeenCalledTimes(1);
    expect(wildcard).toHaveBeenCalledTimes(1);
    expect(escalation.mock.calls[0]?.[0]).toMatchObject({
      kind: "typed",
      type: "decision_escalation",
      payload: { decision_id: "d-1" },
    });
  });

  it("schedules a jittered reconnect after an unexpected close", async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0);
    installWebSocket();
    const mux = createWsMultiplex({ url: () => `ws://synapse.test/ws/${sockets.length}` });
    sockets[0]?.open();

    sockets[0]?.serverClose();
    expect(mux.state()).toBe("closed");
    expect(sockets).toHaveLength(1);

    await vi.runOnlyPendingTimersAsync();
    expect(sockets).toHaveLength(2);
    expect(sockets[1]?.url).toBe("ws://synapse.test/ws/1");
    expect(mux.state()).toBe("connecting");
  });
});
