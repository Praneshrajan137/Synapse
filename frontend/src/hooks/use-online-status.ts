import { useSyncExternalStore } from "react";

/**
 * Browser online/offline status (Req 10.7). Subscribes to the window
 * `online`/`offline` events via `useSyncExternalStore` so every consumer reads
 * the same, concurrent-safe value. Returns `true` when the Console is offline.
 *
 * In non-browser/SSR/test environments where `navigator` is absent we assume
 * online (there is no connection to be "off"), so surfaces render their normal
 * data states rather than a spurious offline view.
 */
function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

function getSnapshot(): boolean {
  if (typeof navigator === "undefined") return false;
  // `navigator.onLine === false` is the only reliable "definitely offline"
  // signal; a truthy/undefined value is treated as online.
  return navigator.onLine === false;
}

function getServerSnapshot(): boolean {
  return false;
}

export function useOnlineStatus(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
