/**
 * The Effectiveness_Harness keeps the WebSocket edge for its stream driver, so a
 * flapped firehose stays not-live until the driver accepts the reconnect
 * (Req 8.4, the `resilience.fault.ws-flap` Resilience_Scenario).
 *
 * What is real and what is simulated. The multiplex, the stream driver, its
 * ScriptedWebSocket double and the harness's capture/reclaim functions are the
 * shipped code. MSW's `worker.start()` cannot run here (`setupWorker` refuses a
 * Node process), so its effect on the WebSocket global is reproduced in exactly
 * two respects, both read from the installed packages: the global becomes a
 * configurable, non-writable Proxy (`@mswjs/interceptors` 0.41.9,
 * `utils/patchesRegistry.ts`), and the socket that Proxy hands the Console opens
 * itself one microtask later (`WebSocketOverride`, when a connection listener
 * exists, which MSW always registers).
 *
 * Falsifier: drop the `reclaimWebSocketEdge` call and the first assertion that
 * the firehose is still `connecting` fails, because the Console's socket opened
 * with no driver involved.
 */

import { createWsMultiplex } from "@transport/ws-multiplex";
import { afterEach, describe, expect, it, vi } from "vitest";

import { captureWebSocketEdge, HarnessDriveError, reclaimWebSocketEdge } from "../harness";
import { createStreamDriver, type InstalledStreamDriver } from "../stream-driver";
import { ScriptedWebSocket } from "../stream-transport";

const FIREHOSE_URL = "ws://synapse.test/ws/firehose?topics=decision&city=bengaluru";

/** The one behaviour of MSW's client override that matters here: it opens itself. */
class SelfOpeningClient {
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.();
    });
  }

  send(_data: string): void {}

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }
}

/** Wrap `owner.WebSocket` the way `patchesRegistry.applyPatch` does on `worker.start()`. */
function patchLikeMswWorkerStart(owner: object): void {
  const wrapped: unknown = Reflect.get(owner, "WebSocket");
  if (typeof wrapped !== "function") {
    throw new Error("there is no WebSocket constructor to wrap");
  }
  Object.defineProperty(owner, "WebSocket", {
    value: new Proxy(wrapped, {
      construct: (_target, args: unknown[]) => new SelfOpeningClient(String(args[0])),
    }),
    enumerable: true,
    configurable: true,
  });
}

/** Run every microtask already queued (a self-opening client opens on one). */
async function settleMicrotasks(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

const isFirehose = (url: string): boolean => url === FIREHOSE_URL;

let driver: InstalledStreamDriver | null = null;

afterEach(() => {
  driver?.restore();
  driver = null;
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the harness keeps the WebSocket edge for its stream driver", () => {
  it("a firehose opened after the edge is reclaimed stays not-live through a flap until the driver accepts its reconnect", async () => {
    vi.useFakeTimers();
    // Every reconnect delay is then 0 ms, so the flap's reconnects fire on the next timer turn.
    vi.spyOn(Math, "random").mockReturnValue(0);
    const installed = createStreamDriver({ seed: 1 });
    driver = installed;
    const edge = captureWebSocketEdge(globalThis);

    patchLikeMswWorkerStart(globalThis);
    expect(reclaimWebSocketEdge(globalThis, edge)).toBe(true);
    expect(reclaimWebSocketEdge(globalThis, edge)).toBe(false);

    const mux = createWsMultiplex({ url: () => FIREHOSE_URL });
    await settleMicrotasks();
    expect(mux.state()).toBe("connecting");

    const first = installed.transport.latestSocket(isFirehose);
    expect(first).toBeInstanceOf(ScriptedWebSocket);
    first?.driverOpen();
    expect(mux.state()).toBe("open");

    installed.flap("decision", 2);
    expect(mux.state()).toBe("closed");

    await vi.runOnlyPendingTimersAsync();
    await settleMicrotasks();
    // The reconnect was constructed and is still waiting: the not-live state holds.
    expect(installed.transport.sockets().length).toBeGreaterThan(1);
    expect(mux.state()).toBe("connecting");

    installed.transport.latestSocket(isFirehose)?.driverOpen();
    expect(mux.state()).toBe("open");
    mux.close();
  });

  it("a WebSocket global that cannot be taken back is refused, never left wrapped", () => {
    const owner = {};
    Object.defineProperty(owner, "WebSocket", {
      value: ScriptedWebSocket,
      writable: true,
      configurable: true,
    });
    const edge = captureWebSocketEdge(owner);
    Object.defineProperty(owner, "WebSocket", { value: "wrapped elsewhere", configurable: false });

    expect(() => reclaimWebSocketEdge(owner, edge)).toThrow(HarnessDriveError);
  });

  it("an edge the stream driver's double does not hold cannot be captured", () => {
    const owner = {};
    Object.defineProperty(owner, "WebSocket", { value: "not the double", configurable: true });

    expect(() => captureWebSocketEdge(owner)).toThrow(HarnessDriveError);
  });
});
