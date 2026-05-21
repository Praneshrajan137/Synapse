import { useUIStore } from "@/app/store/uiStore";
import { useCallback } from "react";
import { type MessageKey, translate } from "./catalog";

/**
 * `useT` — the translation hook. Reads the active locale from the UI
 * store and returns a `t(key)` function bound to it.
 */
export function useT(): (key: MessageKey) => string {
  const locale = useUIStore((s) => s.locale);
  return useCallback((key: MessageKey) => translate(locale, key), [locale]);
}
