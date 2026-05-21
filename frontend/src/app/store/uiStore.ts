import type { City } from "@/domain/city";
import type { Locale } from "@/i18n/catalog";
import type { DensityMode } from "@/ui/tokens";
import { densityModes } from "@/ui/tokens";
import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Global UI state for the app shell.
 *
 * Operator preferences (sound, density, city, chrome layout) persist to
 * localStorage; transient state (command palette open) does not.
 */
export interface UIState {
  /** Sidebar collapsed to icon-only rail. */
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  /** Right-edge Synaptic Feed visibility. */
  feedOpen: boolean;
  toggleFeed: () => void;

  /** Command palette (⌘K) — transient, never persisted. */
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;

  /** Synthesized sound cues. Off by default (plan section 3.5). */
  soundEnabled: boolean;
  setSoundEnabled: (enabled: boolean) => void;

  /** Information density. Cycled with ⌘. */
  density: DensityMode;
  cycleDensity: () => void;

  /** Active city scope. */
  city: City;
  setCity: (city: City) => void;

  /** UI language. */
  locale: Locale;
  setLocale: (locale: Locale) => void;

  /** Cinematic Demo Mode active. */
  demoMode: boolean;
  setDemoMode: (active: boolean) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

      feedOpen: true,
      toggleFeed: () => set((s) => ({ feedOpen: !s.feedOpen })),

      commandOpen: false,
      setCommandOpen: (commandOpen) => set({ commandOpen }),

      soundEnabled: false,
      setSoundEnabled: (soundEnabled) => set({ soundEnabled }),

      density: "comfortable",
      cycleDensity: () =>
        set((s) => {
          const index = densityModes.indexOf(s.density);
          const next = densityModes[(index + 1) % densityModes.length];
          return { density: next ?? "comfortable" };
        }),

      city: "bengaluru",
      setCity: (city) => set({ city }),

      locale: "en",
      setLocale: (locale) => set({ locale }),

      demoMode: false,
      setDemoMode: (demoMode) => set({ demoMode }),
    }),
    {
      name: "synapse.ui",
      // Transient state is never restored from storage.
      partialize: ({ commandOpen: _commandOpen, demoMode: _demoMode, ...rest }) => rest,
    },
  ),
);
