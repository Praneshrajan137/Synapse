/**
 * SYNAPSE Atlas Console — web-vitals beacon.
 *
 * Reports LCP / TBT / INP / FCP / CLS / TTFB to the gateway's
 * `POST /api/v1/rum` (B4). Uses `navigator.sendBeacon` so the request
 * survives an unload event without blocking the navigation.
 *
 * Sampling: 100% for now (the bucket count is small and beacons are
 * cheap). When traffic grows, gate behind a sampler in the OTel layer
 * — keep this path lossless because per-route LCP is the gate that
 * proves I-10 (<2s p99) from the user's machine.
 *
 * Why not OTel browser SDK?
 *   - 80 KB gz baseline cost.
 *   - This needs to ship before the SPA hydrates so a slow shell still
 *     reports LCP. A 2 KB beacon is the right tool.
 *
 * Privacy: no PII. Session id is a fresh, opaque, non-persistent UUID.
 * No URLs with query strings (we strip them server-side too).
 */
import type { Metric } from "web-vitals";

const RUM_PATH = "/api/v1/rum";

/** Crypto-strong fresh id; not persisted. */
function newSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for jsdom / very old browsers.
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

const SESSION_ID = newSessionId();

interface BeaconSample {
  readonly name: string;
  readonly value: number;
  readonly rating: Metric["rating"] | null;
  readonly route: string;
  readonly nav_type: string | null;
}

const buffer: BeaconSample[] = [];
const MAX_BUFFER = 32;
let flushScheduled = false;

function currentRoute(): string {
  if (typeof window === "undefined") return "/";
  return window.location.pathname.split("?", 1)[0] ?? "/";
}

function flush(transport: "beacon" | "fetch" = "beacon"): void {
  if (buffer.length === 0) return;
  const batch = {
    session_id: SESSION_ID,
    user_agent: typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 512) : null,
    samples: buffer.splice(0, buffer.length),
  };
  const body = JSON.stringify(batch);

  if (transport === "beacon" && typeof navigator !== "undefined" && navigator.sendBeacon) {
    const blob = new Blob([body], { type: "application/json" });
    const ok = navigator.sendBeacon(RUM_PATH, blob);
    if (ok) return;
    // Fall through to fetch on quota-exceeded.
  }

  void fetch(RUM_PATH, {
    method: "POST",
    body,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
  }).catch(() => {
    // Best-effort. Failure to ship a beacon is never user-facing.
  });
}

function scheduleFlush(): void {
  if (flushScheduled) return;
  flushScheduled = true;
  // Coalesce multiple rapid samples into one beacon. 1500 ms aligns with
  // how web-vitals batches its reports — long enough to capture the LCP +
  // FCP pair without holding metrics through a navigation.
  setTimeout(() => {
    flushScheduled = false;
    flush("beacon");
  }, 1500);
}

function recordMetric(metric: Metric): void {
  buffer.push({
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    route: currentRoute(),
    nav_type: metric.navigationType ?? null,
  });
  if (buffer.length >= MAX_BUFFER) flush("beacon");
  else scheduleFlush();
}

let started = false;

/**
 * Wire web-vitals subscriptions. Idempotent — safe to call from React
 * StrictMode (effects run twice in dev). Attach `pagehide` and
 * `visibilitychange` so a backgrounded tab still ships its samples.
 */
export async function startWebVitals(): Promise<void> {
  if (started) return;
  started = true;
  if (typeof window === "undefined") return;

  // Lazy-load web-vitals so the beacon path itself is tiny.
  const wv = await import("web-vitals");
  wv.onLCP(recordMetric);
  wv.onCLS(recordMetric);
  wv.onINP(recordMetric);
  wv.onFCP(recordMetric);
  wv.onTTFB(recordMetric);

  const flushOnLeave = (): void => flush("beacon");
  window.addEventListener("pagehide", flushOnLeave);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushOnLeave();
  });
}
