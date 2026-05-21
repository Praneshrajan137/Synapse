import { useEffect, useRef, useState } from "react";
import { createWsMultiplex, type WsMultiplex, type WsState } from "@transport/ws-multiplex";

// React adapter around the WS multiplex. One multiplex per URL per mount tree.
// Component callers subscribe via the returned `on` helper, which returns
// a teardown closure for useEffect.

export interface UseWsResult {
  readonly state: WsState;
  readonly connected: boolean;
  readonly send: WsMultiplex["send"];
  readonly on: WsMultiplex["on"];
}

export function useWs(url: string): UseWsResult {
  const [state, setState] = useState<WsState>("idle");
  const ref = useRef<WsMultiplex | null>(null);

  if (ref.current === null) {
    ref.current = createWsMultiplex({ url: () => url, heartbeatMs: 25_000 });
  }

  useEffect(() => {
    const mux = ref.current!;
    const off = mux.onState(setState);
    setState(mux.state());
    return () => {
      off();
      mux.close();
      ref.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  const mux = ref.current!;
  return {
    state,
    connected: state === "open",
    send: mux.send,
    on: mux.on,
  };
}
