import { useState, useEffect, useRef, useCallback } from "react";

export function useWebSocket(url) {
  const [messages, setMessages] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectAttempt = useRef(0);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempt.current = 0;
    };

    ws.onclose = () => {
      setConnected(false);
      const jitter =
        Math.random() * Math.min(30000, 1000 * Math.pow(2, reconnectAttempt.current));
      reconnectAttempt.current += 1;
      setTimeout(() => connect(), jitter);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages((prev) => [...prev, data]);
    };

    return ws;
  }, [url]);

  useEffect(() => {
    const ws = connect();
    return () => ws.close();
  }, [connect]);

  const send = useCallback(
    (data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(data));
      }
    },
    [],
  );

  return { messages, connected, send };
}
