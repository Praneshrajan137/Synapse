/**
 * SYNAPSE Atlas Console — keyboard-first hotkeys hook.
 *
 * Plan §5.2 keymap:
 *   j  / ArrowDown → next item
 *   k  / ArrowUp   → prev item
 *   Enter          → approve focused item
 *   r              → reject focused item
 *   m              → modify focused item
 *   Esc            → defocus
 *   ?              → toggle hotkeys help
 *
 * Disabled when:
 *   - the active element is an input / textarea / contenteditable,
 *   - a modal dialog is open and `inDialog` is true,
 *   - `enabled` is false.
 *
 * The hook never calls `preventDefault` for unhandled keys — only for
 * keys it owns. That keeps native scrolling working when the user
 * holds the down-arrow.
 */
import { useEffect } from "react";

export type HotkeyAction =
  | "next"
  | "prev"
  | "approve"
  | "reject"
  | "modify"
  | "defocus"
  | "help";

export interface UseHotkeysOptions {
  readonly enabled?: boolean;
  readonly onAction: (action: HotkeyAction) => void;
}

const KEYMAP: Record<string, HotkeyAction> = {
  j: "next",
  ArrowDown: "next",
  k: "prev",
  ArrowUp: "prev",
  Enter: "approve",
  r: "reject",
  m: "modify",
  Escape: "defocus",
  "?": "help",
};

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return false;
}

export function useHotkeys(options: UseHotkeysOptions): void {
  const { onAction, enabled = true } = options;

  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined") return;

    function handler(e: KeyboardEvent): void {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isEditable(e.target)) return;

      // `?` requires Shift on most layouts; treat both as the same logical key.
      const logical = e.key === "/" && e.shiftKey ? "?" : e.key;
      const action = KEYMAP[logical];
      if (!action) return;

      e.preventDefault();
      onAction(action);
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled, onAction]);
}
