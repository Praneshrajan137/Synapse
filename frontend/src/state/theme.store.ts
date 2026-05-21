import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type Theme = "dark" | "light" | "hc";

interface ThemeState {
  readonly theme: Theme;
  setTheme(theme: Theme): void;
}

export const useThemeStore = create<ThemeState>()(
  persist<ThemeState>(
    (set) => ({
      theme: "dark",
      setTheme(theme) {
        set({ theme });
      },
    }),
    {
      name: "synapse.theme",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);

/** Applies the theme to <html data-theme="..."> on the next tick. */
export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
}
