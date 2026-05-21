/**
 * SYNAPSE Atlas Console — `prefers-reduced-motion` hook.
 *
 * Plan §12 mandates that the time-scrubber, KL sparkline, and
 * force-graph respect `prefers-reduced-motion`. tokens.css already
 * neuters all CSS transitions globally; this hook lets JS-driven
 * animation (e.g. requestAnimationFrame in Visx) gate too.
 *
 * Returns `true` when the user prefers reduced motion. SSR-safe.
 */
import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function read(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(read);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(QUERY);
    const handler = (): void => setReduced(mql.matches);
    handler();
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", handler);
      return () => mql.removeEventListener("change", handler);
    }
    // Older Safari fallback.
    mql.addListener(handler);
    return () => mql.removeListener(handler);
  }, []);

  return reduced;
}
