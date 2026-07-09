// Structured FE logger. Batches up to 20 events or 5s and ships via
// navigator.sendBeacon to the gateway telemetry endpoint. No console.log
// in production (Biome rule), no third-party SaaS (I-1, FE-INV-001).

interface LogEvent {
  readonly kind: "web_vitals" | "error" | "audit_view" | "demo_event";
  readonly [key: string]: unknown;
}

// Read the Vite-injected env defensively: `import.meta.env` is defined under
// Vite/Vitest but undefined when this module graph is loaded by a plain Node
// runtime (e.g. the Contract Fidelity harness run via tsx), where we fall back
// to the default endpoint rather than crashing at import time.
const ENDPOINT =
  (typeof import.meta.env !== "undefined" ? import.meta.env.VITE_TELEMETRY_ENDPOINT : undefined) ??
  "/api/v1/telemetry";
const FLUSH_INTERVAL_MS = 5_000;
const BATCH_MAX = 20;

/**
 * The ONLY telemetry field names permitted to leave the client (FE-INV-030,
 * Req 14.1/14.2). Kept in lock-step with the gateway's `ALLOWED_FIELDS` set
 * (`api/routers/telemetry.py`) so a field never silently vanishes server-side.
 * Anything outside this set — raw payloads, field values, operator PII — is
 * stripped before a beacon fires. This is defense-in-depth: the backend
 * whitelists again, but the sensitive value never even reaches the wire.
 */
export const ALLOWED_TELEMETRY_FIELDS = [
  "kind",
  "metric",
  "value",
  "id",
  "rating",
  "path",
  "ts",
  "name",
  "message",
  "stack",
  "component_stack",
  "trace_id",
  "build_sha",
  "error",
  "schemaId",
  "issueCount",
  "paths",
] as const;

const ALLOWED_TELEMETRY_SET: ReadonlySet<string> = new Set(ALLOWED_TELEMETRY_FIELDS);

/**
 * Pure field whitelist. Returns a NEW record containing only the allow-listed
 * telemetry fields (and only those with a defined value); never mutates its
 * input. This is the single source of truth for what the Console is allowed to
 * forward as telemetry, consumed by `log()` before any beacon is queued.
 */
export function whitelistTelemetryFields(
  event: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(event)) {
    if (ALLOWED_TELEMETRY_SET.has(key) && event[key] !== undefined) {
      out[key] = event[key];
    }
  }
  return out;
}

const buffer: Record<string, unknown>[] = [];
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
  // Whitelist BEFORE the payload ever enters the batch buffer, so a
  // non-allow-listed field cannot leak even if a flush races (Req 14.1/14.2).
  buffer.push(whitelistTelemetryFields({ ...event, ts: new Date().toISOString() }));
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
