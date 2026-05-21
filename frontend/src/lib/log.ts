// Structured FE logger. Batches up to 20 events or 5s and ships via
// navigator.sendBeacon to the gateway telemetry endpoint. No console.log
// in production (Biome rule), no third-party SaaS (I-1, FE-INV-001).

interface LogEvent {
  readonly kind: "web_vitals" | "error" | "audit_view" | "demo_event";
  readonly [key: string]: unknown;
}

const ENDPOINT = import.meta.env.VITE_TELEMETRY_ENDPOINT ?? "/api/v1/telemetry";
const FLUSH_INTERVAL_MS = 5_000;
const BATCH_MAX = 20;

const buffer: LogEvent[] = [];
let timer: number | null = null;

function flush(): void {
  if (buffer.length === 0) return;
  const events = buffer.splice(0, buffer.length);
  for (const event of events) {
    const body = JSON.stringify(event);
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, body);
    } else {
      void fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => {
        /* swallow */
      });
    }
  }
}

function schedule(): void {
  if (timer !== null) return;
  timer = window.setTimeout(() => {
    timer = null;
    flush();
  }, FLUSH_INTERVAL_MS);
}

export function log(event: LogEvent): void {
  buffer.push({ ...event, ts: new Date().toISOString() });
  if (buffer.length >= BATCH_MAX) {
    flush();
    return;
  }
  schedule();
}

// Flush on page hide (works for tab-close + nav).
if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
}
