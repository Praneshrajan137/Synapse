// SYNAPSE HITL Console — theme state.
// The DOM <html data-theme> attribute is the source of truth (set pre-paint
// by the no-flash script in index.html); this hook mirrors and toggles it.
import { useCallback, useState } from "react";

const STORAGE_KEY = "synapse-theme";

function currentTheme() {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState(currentTheme);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch (err) {
        void err; // localStorage unavailable — in-memory toggle still works
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
