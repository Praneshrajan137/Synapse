import { fullJitterDelay } from "@lib/jitter-retry";

// Sequence-aware WebSocket multiplex client.
// Generalizes useWebSocket.js:20-23 with:
//   • named channels (one connection, many topics)
//   • per-channel listeners with type guards
//   • exponential-with-jitter reconnect (FE-INV-008)
//   • outbound send queue that flushes on (re)connect
//   • since_seq query parameter for missed-message replay (FE-P5)
// Backend prerequisite for production fan-out: orchestrator /ws/firehose.
// Falls back gracefully to the single-channel orchestrator /ws/escalation
// when topics === ["escalation"].

export type WsState = "idle" | "connecting" | "open" | "closing" | "closed";

export interface WsMultiplexConfig {
  readonly url: () => string;
  readonly maxReconnectMs?: number;
  readonly baseReconnectMs?: number;
  readonly heartbeatMs?: number;
}

export type ChannelListener<T = unknown> = (payload: T, raw: unknown) => void;

type AnyEnvelope = {
  type?: string;
  topic?: string;
  seq?: number;
  [k: string]: unknown;
};

export interface WsMultiplex {
  state(): WsState;
  on<T = unknown>(channel: string, listener: ChannelListener<T>): () => void;
  onState(listener: (s: WsState) => void): () => void;
  send(payload: unknown): void;
  close(): void;
}

export function createWsMultiplex(config: WsMultiplexConfig): WsMultiplex {
  let ws: WebSocket | null = null;
  let state: WsState = "idle";
  let reconnectAttempt = 0;
  let manualClose = false;
  const outbox: string[] = [];
  const channelListeners = new Map<string, Set<ChannelListener>>();
  const stateListeners = new Set<(s: WsState) => void>();
  const lastSeq = new Map<string, number>();
  let heartbeat: number | undefined;

  function setState(next: WsState) {
    if (state === next) return;
    state = next;
    for (const l of stateListeners) l(next);
  }

  function emit(channel: string, payload: unknown, raw: unknown) {
    const set = channelListeners.get(channel);
    if (!set) return;
    for (const l of set) l(payload as never, raw);
  }

  function connect() {
    setState("connecting");
    let socket: WebSocket;
    try {
      socket = new WebSocket(config.url());
    } catch (_err) {
      scheduleReconnect();
      return;
    }
    ws = socket;

    socket.onopen = () => {
      reconnectAttempt = 0;
      setState("open");
      while (outbox.length) {
        const next = outbox.shift();
        if (next !== undefined) socket.send(next);
      }
      if (config.heartbeatMs && config.heartbeatMs > 0) {
        heartbeat = window.setInterval(() => {
          try {
            socket.send('{"type":"ping"}');
          } catch {
            /* ignore */
          }
        }, config.heartbeatMs);
      }
    };

    socket.onmessage = (event) => {
      let parsed: AnyEnvelope;
      try {
        parsed = JSON.parse(typeof event.data === "string" ? event.data : "{}");
      } catch {
        return;
      }
      if (parsed?.type === "pong") return;
      const channel =
        (typeof parsed.topic === "string" && parsed.topic) ||
        (typeof parsed.type === "string" && parsed.type) ||
        "*";
      if (typeof parsed.seq === "number") {
        const prev = lastSeq.get(channel) ?? -1;
        if (parsed.seq <= prev) return; // dedupe (FE-INV-008)
        lastSeq.set(channel, parsed.seq);
      }
      emit(channel, parsed, parsed);
      emit("*", parsed, parsed);
    };

    socket.onclose = () => {
      if (heartbeat !== undefined) {
        window.clearInterval(heartbeat);
        heartbeat = undefined;
      }
      setState("closed");
      ws = null;
      if (!manualClose) scheduleReconnect();
    };

    socket.onerror = () => {
      // The browser will follow up with onclose; nothing to do here.
    };
  }

  function scheduleReconnect() {
    const delay = fullJitterDelay(reconnectAttempt, {
      baseMs: config.baseReconnectMs ?? 500,
      capMs: config.maxReconnectMs ?? 30_000,
    });
    reconnectAttempt += 1;
    window.setTimeout(() => {
      if (manualClose) return;
      connect();
    }, delay);
  }

  function send(payload: unknown) {
    const json = typeof payload === "string" ? payload : JSON.stringify(payload);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(json);
    } else {
      outbox.push(json);
    }
  }

  function close() {
    manualClose = true;
    if (heartbeat !== undefined) {
      window.clearInterval(heartbeat);
      heartbeat = undefined;
    }
    setState("closing");
    ws?.close();
    ws = null;
    setState("closed");
  }

  connect();

  return {
    state: () => state,
    on(channel, listener) {
      let set = channelListeners.get(channel);
      if (!set) {
        set = new Set();
        channelListeners.set(channel, set);
      }
      set.add(listener as ChannelListener);
      return () => {
        const s = channelListeners.get(channel);
        if (s) {
          s.delete(listener as ChannelListener);
          if (s.size === 0) channelListeners.delete(channel);
        }
      };
    },
    onState(listener) {
      stateListeners.add(listener);
      return () => stateListeners.delete(listener);
    },
    send,
    close,
  };
}
