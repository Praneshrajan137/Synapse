import { useEffect } from "react";

interface ShortcutMap {
  readonly approve: () => void;
  readonly reject: () => void;
  readonly modify: () => void;
  readonly next: () => void;
  readonly prev: () => void;
  readonly escape: () => void;
}

/**
 * Cockpit keyboard handler. FE-INV-022.
 *
 * Bindings:
 *   A — approve         R — reject         M — modify
 *   J — next            K — previous       Esc — close active modal
 *
 * No bindings fire when focus is in an input/textarea/select or when a
 * Radix dialog has the focus trap engaged (`data-radix-focus-guard`).
 */
export function useCockpitShortcuts(map: ShortcutMap, enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    function onKey(ev: KeyboardEvent) {
      if (isTypingTarget(ev.target)) return;
      switch (ev.key.toLowerCase()) {
        case "a":
          ev.preventDefault();
          map.approve();
          break;
        case "r":
          ev.preventDefault();
          map.reject();
          break;
        case "m":
          ev.preventDefault();
          map.modify();
          break;
        case "j":
          ev.preventDefault();
          map.next();
          break;
        case "k":
          ev.preventDefault();
          map.prev();
          break;
        case "escape":
          map.escape();
          break;
        default:
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled, map]);
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  if (target.closest("[data-radix-focus-guard]")) return true;
  return false;
}
