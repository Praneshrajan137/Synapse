import { useUIStore } from "@/app/store/uiStore";
import { DemoOverlay } from "@/aux-ui/demo-mode";
import { useGlobalKeyboard } from "@/aux-ui/keyboard";
import { TooltipProvider } from "@/ui/primitives";
import type { ReactNode } from "react";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";
import { SynapticFeed } from "./SynapticFeed";

/**
 * AppShell — the persistent chrome of Synaptic Calm.
 *
 *   ┌───────────────────────────────────────────┐
 *   │ StatusBar                                  │
 *   ├──────────┬───────────────────┬─────────────┤
 *   │ Sidebar  │ surface (children)│ SynapticFeed │
 *   └──────────┴───────────────────┴─────────────┘
 *
 * The Command Palette and global keyboard map live here so they are
 * available from every surface. Must render inside a Router.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const feedOpen = useUIStore((s) => s.feedOpen);
  useGlobalKeyboard();

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen flex-col bg-void text-ink-primary">
        <StatusBar />
        <div className="flex min-h-0 flex-1">
          <Sidebar />
          <main
            id="surface"
            aria-label="Active surface"
            className="min-w-0 flex-1 overflow-auto"
          >
            {children}
          </main>
          {feedOpen && <SynapticFeed />}
        </div>
      </div>
      <CommandPalette />
      <DemoOverlay />
    </TooltipProvider>
  );
}
