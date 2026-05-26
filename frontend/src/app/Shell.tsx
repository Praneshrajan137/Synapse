import { CitySwitcher, LanguagePicker, OperatorIdentity } from "@ds/compounds";
import { cn } from "@lib/cn";
import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/", label: "Mission Control", end: true },
  { path: "/cockpit", label: "Override Cockpit" },
  { path: "/decisions", label: "Decision Theater" },
  { path: "/agents", label: "Agent Council" },
  { path: "/twin", label: "Twin Lab" },
  { path: "/steering", label: "Steering" },
  { path: "/audit", label: "Audit Vault" },
  { path: "/demo", label: "Demo Theater" },
] as const;

/**
 * App shell. Top bar (brand + nav + city + operator), main outlet.
 * Replaces App.jsx:20-48. Real-time pills (WS status, tier latency) are
 * mounted by surfaces that need them — keeping the shell stable across
 * routes so KV-cache-like client-side render stays inexpensive.
 */
export function Shell() {
  return (
    <div className="flex h-screen flex-col bg-canvas text-ink">
      <header className="flex items-center gap-6 border-b border-border bg-surface px-6 py-2.5">
        <div className="flex items-center gap-2">
          <div
            aria-hidden
            className="h-5 w-5 rounded-sm bg-gradient-to-br from-tier-2 via-accent to-tier-3"
          />
          <span className="text-sm font-semibold tracking-wide text-ink">SYNAPSE</span>
          <span className="hidden text-2xs uppercase text-ink-subtle md:inline">Console</span>
        </div>
        <nav aria-label="Primary" className="flex flex-1 items-center gap-1 overflow-x-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              {...("end" in item ? { end: item.end } : {})}
              className={({ isActive }) =>
                cn(
                  "rounded px-3 py-1.5 text-xs font-medium transition-colors duration-fast ease-standard",
                  "focus-visible:outline-none focus-visible:shadow-focus",
                  isActive ? "bg-surface-raised text-ink" : "text-ink-muted hover:text-ink",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <CitySwitcher />
          <LanguagePicker />
          <OperatorIdentity />
        </div>
      </header>
      <main className="flex-1 overflow-auto bg-canvas p-6">
        <Outlet />
      </main>
    </div>
  );
}
