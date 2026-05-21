import { useUIStore } from "@/app/store/uiStore";
import { useEffect } from "react";

/**
 * Global keyboard handler — the keyboard is the primary input for
 * Synaptic Calm (plan tenet T-11).
 *
 *   ⌘K / Ctrl+K   command palette
 *   ⌘.            cycle information density
 *   ⌘\            toggle the sidebar
 *   ⌘/            toggle the Synaptic Feed
 *   ?             open the command palette (also lists shortcuts)
 *
 * Modifier shortcuts fire from anywhere; the bare `?` is ignored while
 * an editable element holds focus.
 */

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable
  );
}

export function useGlobalKeyboard(): void {
  const setCommandOpen = useUIStore((s) => s.setCommandOpen);
  const cycleDensity = useUIStore((s) => s.cycleDensity);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const toggleFeed = useUIStore((s) => s.toggleFeed);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      const mod = event.metaKey || event.ctrlKey;

      if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
        return;
      }
      if (mod && event.key === ".") {
        event.preventDefault();
        cycleDensity();
        return;
      }
      if (mod && event.key === "\\") {
        event.preventDefault();
        toggleSidebar();
        return;
      }
      if (mod && event.key === "/") {
        event.preventDefault();
        toggleFeed();
        return;
      }
      if (event.key === "?" && !isEditableTarget(event.target)) {
        event.preventDefault();
        setCommandOpen(true);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setCommandOpen, cycleDensity, toggleSidebar, toggleFeed]);
}
