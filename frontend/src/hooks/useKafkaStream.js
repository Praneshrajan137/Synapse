import { useState, useEffect, useRef } from "react";

export function useKafkaStream(topic) {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef(null);

  useEffect(() => {
    const es = new EventSource(`/api/v1/stream/${topic}`);
    sourceRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev.slice(-500), data]);
    };

    return () => es.close();
  }, [topic]);

  return { events, connected };
}
