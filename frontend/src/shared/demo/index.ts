/**
 * SYNAPSE Atlas Console — demo-mode primitives.
 *
 * Plan §9: when the SPA is opened with `?demo=1`, the Atlas Console
 * runs in a deterministic, regulator-safe mode:
 *
 *   - Clocks are pinned to a seeded epoch so screenshots and PDF
 *     exports are byte-equal across runs.
 *   - RUM beacons + OTel sampling are off (no exfil to /api/v1/rum).
 *   - The DEMO watermark renders bottom-right.
 *   - Locale defaults to en-IN, theme defaults to dark, city locked
 *     to whichever was selected when the link was issued.
 *   - SSE streams resolve from a fixture loop (msw-storybook-addon
 *     handles this in Storybook; production rides the
 *     `scripts/demo/run_demo.sh` recording mode).
 *
 * The `useDemoMode()` hook is what surfaces consume — they should
 * use `now()` from here instead of `Date.now()` for any animation,
 * ranker, or exported timestamp.
 */

const SEED_EPOCH_MS = Date.parse("2026-04-30T10:00:00+05:30");

let cachedActive: boolean | null = null;

function readFlag(): boolean {
  if (typeof window === "undefined") return false;
  if (cachedActive !== null) return cachedActive;
  const params = new URLSearchParams(window.location.search);
  cachedActive = params.get("demo") === "1";
  return cachedActive;
}

/** True iff the SPA is in demo mode. Memoised after first read. */
export function isDemoMode(): boolean {
  return readFlag();
}

/**
 * Frozen clock for demo mode; advances 1 ms per call so any ranker
 * with a "ties broken by issued_at ASC" rule still emits a stable
 * order without re-collisions on a single tick.
 */
let demoTick = 0;
function demoNow(): number {
  return SEED_EPOCH_MS + demoTick++;
}

/** Wall clock that surfaces should consume in lieu of `Date.now()`. */
export function now(): number {
  return isDemoMode() ? demoNow() : Date.now();
}

/** Pinned ISO timestamp for the export footer. */
export function demoTimestampIso(): string {
  return new Date(SEED_EPOCH_MS).toISOString();
}

/** Reset for tests — never call from app code. */
export function __resetDemoModeForTests(): void {
  cachedActive = null;
  demoTick = 0;
}
