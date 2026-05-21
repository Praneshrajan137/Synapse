/**
 * Display formatting helpers — consistent time, number and id rendering
 * across every surface.
 */

/** Compact relative time, e.g. "now", "42s", "7m", "3h", "2d". */
export function relativeTime(epochMs: number, now: number = Date.now()): string {
  const delta = Math.max(0, now - epochMs);
  const sec = Math.floor(delta / 1000);
  if (sec < 5) return "now";
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  return `${Math.floor(hr / 24)}d`;
}

/** Wall-clock time, 24h, e.g. "14:07:33". */
export function clockTime(epochMs: number): string {
  return new Date(epochMs).toLocaleTimeString([], { hour12: false });
}

/** A countdown as "M:SS"; clamps at "0:00". */
export function countdown(msRemaining: number): string {
  const total = Math.max(0, Math.floor(msRemaining / 1000));
  const min = Math.floor(total / 60);
  const sec = total % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

/** A signed number with a fixed sign, e.g. "+2.4", "-0.7". */
export function signed(value: number, precision = 1): string {
  const fixed = value.toFixed(precision);
  return value > 0 ? `+${fixed}` : fixed;
}

/** Shorten a decision/audit id for compact display. */
export function shortId(id: string): string {
  const tail = id.split("-").pop() ?? id;
  return tail.length > 8 ? tail.slice(0, 8) : tail;
}
