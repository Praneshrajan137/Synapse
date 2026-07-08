/**
 * Effectiveness_Harness — scripted real-time transport doubles (Req 1.2).
 *
 * The Console opens two kinds of real-time connections:
 *   • a multiplexed `WebSocket` to `/ws/firehose` (or `/ws/escalation`) that
 *     `transport/ws-multiplex.ts` / `transport/firehose.ts` drive; and
 *   • an `EventSource` (SSE) to `/api/v1/demo/{id}/stream` that the Demo Theater
 *     (`surfaces/demo-theater/useDemoRun.ts`) consumes.
 *
 * To feed *the same surfaces* the app already uses — without patching any app
 * code path (design "Key composition rule") — this module installs controllable
 * doubles for the global `WebSocket` and `EventSource` constructors. Every
 * instance the app constructs registers with the active
 * {@link StreamTransportController}, so the stream driver can open a connection,
 * deliver a scripted frame, or flap it deterministically.
 *
 * The doubles are intentionally *driver-controlled*: they never auto-open and
 * never invent traffic. A connection transitions and a message arrives only
 * when the driver says so, which is what makes a fixed seed yield an identical
 * message order on every run (Req 1.3). This mirrors the existing
 * `MockWebSocket` convention in `src/transport/__tests__/*`.
 */

// ─────────────────────────────────────────────────────────────────────────
// Ready-state constants (shared by both doubles; match the DOM contract)
// ─────────────────────────────────────────────────────────────────────────

export const CONNECTING = 0;
export const OPEN = 1;
export const CLOSING = 2;
export const CLOSED = 3;

/** A minimal `MessageEvent`-shaped value carrying only the `data` payload. */
function messageEventOf(data: string): MessageEvent<string> {
  return { data } as unknown as MessageEvent<string>;
}

// ─────────────────────────────────────────────────────────────────────────
// ScriptedWebSocket — controllable stand-in for the multiplex/firehose socket
// ─────────────────────────────────────────────────────────────────────────

type WsEventListener = (event: MessageEvent<string>) => void;

/**
 * A controllable `WebSocket` double. `ws-multiplex` binds the `on*` handler
 * properties (not `addEventListener`), so those are the primary surface; the
 * `addEventListener` map is provided for completeness. Driver-only control
 * methods are prefixed with `driver`.
 */
export class ScriptedWebSocket {
  static readonly CONNECTING = CONNECTING;
  static readonly OPEN = OPEN;
  static readonly CLOSING = CLOSING;
  static readonly CLOSED = CLOSED;

  readonly CONNECTING = CONNECTING;
  readonly OPEN = OPEN;
  readonly CLOSING = CLOSING;
  readonly CLOSED = CLOSED;

  readyState: number = CONNECTING;
  onopen: ((event?: unknown) => void) | null = null;
  onmessage: WsEventListener | null = null;
  onclose: ((event?: unknown) => void) | null = null;
  onerror: ((event?: unknown) => void) | null = null;

  /** Every frame the app sent outbound (subscribe/ping/etc.), for assertions. */
  readonly sent: string[] = [];

  private readonly listeners = new Map<string, Set<(event: unknown) => void>>();

  constructor(readonly url: string) {
    registerWebSocket(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  addEventListener(type: string, listener: (event: unknown) => void): void {
    let set = this.listeners.get(type);
    if (!set) {
      set = new Set();
      this.listeners.set(type, set);
    }
    set.add(listener);
  }

  removeEventListener(type: string, listener: (event: unknown) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  /** App-initiated close. Transitions to CLOSED and notifies close listeners. */
  close(): void {
    if (this.readyState === CLOSED) return;
    this.readyState = CLOSED;
    this.onclose?.();
    this.dispatch("close", {});
  }

  // ── driver-only control ─────────────────────────────────────────────────

  /** Open the connection (fires `onopen`), flushing the app's outbound queue. */
  driverOpen(): void {
    if (this.readyState === OPEN) return;
    this.readyState = OPEN;
    this.onopen?.();
    this.dispatch("open", {});
  }

  /** Deliver a raw envelope frame to the app (`onmessage`). */
  driverEmit(rawFrame: string): void {
    const event = messageEventOf(rawFrame);
    this.onmessage?.(event);
    this.dispatch("message", event);
  }

  /** Server-initiated drop — the signal that triggers a multiplex reconnect. */
  driverServerClose(): void {
    if (this.readyState === CLOSED) return;
    this.readyState = CLOSED;
    this.onerror?.();
    this.onclose?.();
    this.dispatch("close", {});
  }

  private dispatch(type: string, event: unknown): void {
    const set = this.listeners.get(type);
    if (!set) return;
    for (const listener of set) listener(event);
  }
}

// ─────────────────────────────────────────────────────────────────────────
// ScriptedEventSource — controllable stand-in for the demo SSE stream
// ─────────────────────────────────────────────────────────────────────────

/**
 * A controllable `EventSource` double. The demo consumer binds *named* events
 * (`log`, `segment`, `done`, `close`) via `addEventListener` and reads
 * `readyState`/`onerror`, so those are the surface we honor.
 */
export class ScriptedEventSource {
  static readonly CONNECTING = CONNECTING;
  static readonly OPEN = OPEN;
  static readonly CLOSED = CLOSED;

  readonly CONNECTING = CONNECTING;
  readonly OPEN = OPEN;
  readonly CLOSED = CLOSED;

  readyState: number = CONNECTING;
  onopen: ((event?: unknown) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event?: unknown) => void) | null = null;
  withCredentials = false;

  private readonly listeners = new Map<string, Set<(event: unknown) => void>>();

  constructor(
    readonly url: string,
    init?: { readonly withCredentials?: boolean },
  ) {
    if (init?.withCredentials !== undefined) this.withCredentials = init.withCredentials;
    registerEventSource(this);
  }

  addEventListener(type: string, listener: (event: unknown) => void): void {
    let set = this.listeners.get(type);
    if (!set) {
      set = new Set();
      this.listeners.set(type, set);
    }
    set.add(listener);
  }

  removeEventListener(type: string, listener: (event: unknown) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.readyState = CLOSED;
  }

  // ── driver-only control ─────────────────────────────────────────────────

  driverOpen(): void {
    if (this.readyState === CLOSED) return;
    this.readyState = OPEN;
    this.onopen?.();
    this.dispatch("open", {});
  }

  /** Deliver a named SSE event (`log`/`segment`/`done`/…) with a JSON `data`. */
  driverEmit(eventName: string, data: string): void {
    const event = messageEventOf(data);
    if (eventName === "message") this.onmessage?.(event);
    this.dispatch(eventName, event);
  }

  /** Signal a stream error then move to CLOSED (the demo consumer's failure path). */
  driverError(): void {
    this.readyState = CLOSED;
    this.onerror?.();
    this.dispatch("error", {});
  }

  private dispatch(type: string, event: unknown): void {
    const set = this.listeners.get(type);
    if (!set) return;
    for (const listener of set) listener(event);
  }
}

// ─────────────────────────────────────────────────────────────────────────
// StreamTransportController — install/restore the global constructors
// ─────────────────────────────────────────────────────────────────────────

/** The controller that currently owns instance registration (module-scoped). */
let activeController: StreamTransportController | null = null;

function registerWebSocket(socket: ScriptedWebSocket): void {
  activeController?.acceptWebSocket(socket);
}

function registerEventSource(source: ScriptedEventSource): void {
  activeController?.acceptEventSource(source);
}

interface GlobalWithSockets {
  WebSocket?: unknown;
  EventSource?: unknown;
}

/**
 * Installs the scripted `WebSocket`/`EventSource` globals and records every
 * instance the app constructs while active. Call {@link restore} to reinstate
 * the originals — always paired with {@link install} in a `finally`/teardown so
 * the doubles never leak across tests.
 */
export class StreamTransportController {
  private readonly webSockets: ScriptedWebSocket[] = [];
  private readonly eventSources: ScriptedEventSource[] = [];
  private originalWebSocket: unknown;
  private originalEventSource: unknown;
  private installed = false;

  install(): void {
    if (this.installed) return;
    const g = globalThis as unknown as GlobalWithSockets;
    this.originalWebSocket = g.WebSocket;
    this.originalEventSource = g.EventSource;
    g.WebSocket = ScriptedWebSocket as unknown;
    g.EventSource = ScriptedEventSource as unknown;
    activeController = this;
    this.installed = true;
  }

  restore(): void {
    if (!this.installed) return;
    const g = globalThis as unknown as GlobalWithSockets;
    g.WebSocket = this.originalWebSocket;
    g.EventSource = this.originalEventSource;
    if (activeController === this) activeController = null;
    this.webSockets.length = 0;
    this.eventSources.length = 0;
    this.installed = false;
  }

  acceptWebSocket(socket: ScriptedWebSocket): void {
    this.webSockets.push(socket);
  }

  acceptEventSource(source: ScriptedEventSource): void {
    this.eventSources.push(source);
  }

  /** Every WebSocket the app has constructed while this controller is active. */
  sockets(): readonly ScriptedWebSocket[] {
    return this.webSockets;
  }

  /** Every EventSource the app has constructed while this controller is active. */
  sources(): readonly ScriptedEventSource[] {
    return this.eventSources;
  }

  /** The most recently constructed WebSocket whose URL matches `predicate`. */
  latestSocket(predicate: (url: string) => boolean): ScriptedWebSocket | undefined {
    for (let i = this.webSockets.length - 1; i >= 0; i -= 1) {
      const socket = this.webSockets[i];
      if (socket !== undefined && predicate(socket.url)) return socket;
    }
    return undefined;
  }

  /** The most recently constructed EventSource whose URL matches `predicate`. */
  latestSource(predicate: (url: string) => boolean): ScriptedEventSource | undefined {
    for (let i = this.eventSources.length - 1; i >= 0; i -= 1) {
      const source = this.eventSources[i];
      if (source !== undefined && predicate(source.url)) return source;
    }
    return undefined;
  }
}
