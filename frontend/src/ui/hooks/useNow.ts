import { useEffect, useState } from "react";

/**
 * A ticking clock — re-renders on an interval so countdowns and
 * relative timestamps stay live. Default cadence is 1s.
 */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
