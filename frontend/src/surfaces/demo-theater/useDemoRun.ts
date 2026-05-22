import { log } from "@lib/log";
import { useCityStore } from "@state/city.store";
import { useSessionStore } from "@state/session.store";
import { useEffect, useRef, useState } from "react";

export type DemoSegmentId =
  | "01_living_map"
  | "02_ipl_signal"
  | "03_disruption"
  | "04_debate"
  | "05_evidence";

export interface DemoEvent {
  readonly type: "log" | "segment" | "done" | "error";
  readonly line?: string;
  readonly segment?: DemoSegmentId;
  readonly exit_code?: number;
  readonly message?: string;
  readonly ts?: number;
}

export interface UseDemoRunResult {
  readonly jobId: string | null;
  readonly running: boolean;
  readonly currentSegment: DemoSegmentId | null;
  readonly logs: ReadonlyArray<string>;
  readonly events: ReadonlyArray<DemoEvent>;
  readonly start: (params?: { kind?: string; speed?: number }) => Promise<void>;
  readonly cancel: () => Promise<void>;
  readonly error: string | null;
}

const SEGMENTS: ReadonlyArray<DemoSegmentId> = [
  "01_living_map",
  "02_ipl_signal",
  "03_disruption",
  "04_debate",
  "05_evidence",
];

export function useDemoRun(): UseDemoRunResult {
  const city = useCityStore((s) => s.city);
  const accessToken = useSessionStore((s) => s.accessToken);
  const [jobId, setJobId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [currentSegment, setCurrentSegment] = useState<DemoSegmentId | null>(null);
  const [logs, setLogs] = useState<ReadonlyArray<string>>([]);
  const [events, setEvents] = useState<ReadonlyArray<DemoEvent>>([]);
  const [error, setError] = useState<string | null>(null);
  const evtSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      evtSourceRef.current?.close();
    };
  }, []);

  async function start(params?: { kind?: string; speed?: number }): Promise<void> {
    setError(null);
    setLogs([]);
    setEvents([]);
    setCurrentSegment(null);
    setRunning(true);
    try {
      const q = new URLSearchParams({
        city,
        speed: String(params?.speed ?? 1.0),
        kind: params?.kind ?? "warehouse_offline",
      });
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
      const resp = await fetch(`/api/v1/demo/run?${q.toString()}`, {
        method: "POST",
        headers,
        credentials: "include",
      });
      if (!resp.ok) {
        setError(`HTTP ${resp.status}: ${await resp.text()}`);
        setRunning(false);
        return;
      }
      const body = (await resp.json()) as { job_id: string };
      setJobId(body.job_id);
      log({ kind: "demo_event", name: "start", trace_id: body.job_id });

      // Subscribe to SSE stream. EventSource doesn't support headers, so
      // the gateway routes /api/v1/demo/{id}/stream as JWT-cookie-based
      // (refresh cookie path scoped to /demo). For dev we accept without
      // auth on the stream endpoint.
      const evtSource = new EventSource(`/api/v1/demo/${body.job_id}/stream`);
      evtSourceRef.current = evtSource;
      evtSource.addEventListener("log", (e: MessageEvent) => {
        const parsed = JSON.parse(e.data) as DemoEvent;
        setLogs((prev) => [...prev.slice(-200), parsed.line ?? ""]);
        setEvents((prev) => [...prev, parsed]);
      });
      evtSource.addEventListener("segment", (e: MessageEvent) => {
        const parsed = JSON.parse(e.data) as DemoEvent;
        if (parsed.segment) setCurrentSegment(parsed.segment);
        setEvents((prev) => [...prev, parsed]);
      });
      evtSource.addEventListener("done", (e: MessageEvent) => {
        const parsed = JSON.parse(e.data) as DemoEvent;
        setEvents((prev) => [...prev, parsed]);
        setRunning(false);
        evtSource.close();
        log({
          kind: "demo_event",
          name: "done",
          trace_id: body.job_id,
          value: parsed.exit_code,
        });
      });
      evtSource.addEventListener("close", () => {
        evtSource.close();
        setRunning(false);
      });
      evtSource.onerror = () => {
        if (evtSource.readyState === EventSource.CLOSED) {
          setRunning(false);
        }
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setRunning(false);
    }
  }

  async function cancel(): Promise<void> {
    if (!jobId) return;
    const headers: Record<string, string> = {};
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    try {
      await fetch(`/api/v1/demo/${jobId}/cancel`, {
        method: "POST",
        headers,
        credentials: "include",
      });
    } catch {
      /* swallow */
    }
    evtSourceRef.current?.close();
    setRunning(false);
  }

  return {
    jobId,
    running,
    currentSegment,
    logs,
    events,
    start,
    cancel,
    error,
  };
}

export { SEGMENTS };
