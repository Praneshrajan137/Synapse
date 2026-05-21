import { useUIStore } from "@/app/store/uiStore";
import { cn } from "@/ui/lib/cn";
import { Tooltip } from "@/ui/primitives";
import { PanelLeftClose, PanelLeftOpen, Sliders } from "lucide-react";
import { NavLink } from "react-router-dom";
import { SURFACES } from "./navigation";

/**
 * Sidebar — primary surface navigation.
 *
 * Collapses to an icon-only rail (⌘\). The command palette (⌘K) is the
 * faster path; the sidebar is the ambient, always-visible map.
 */
export function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  return (
    <nav
      aria-label="Surfaces"
      className={cn(
        "z-sidebar flex h-full flex-col border-r border-line-faint bg-paper",
        "transition-[width] duration-200",
        collapsed ? "w-14" : "w-56",
      )}
    >
      {/* Brand */}
      <div className="flex h-12 items-center gap-2.5 px-3.5">
        <img src="/synapse-mark.svg" alt="" width={22} height={22} className="shrink-0" />
        {!collapsed && (
          <span className="font-display text-sm font-semibold tracking-[0.16em] text-ink-primary">
            SYNAPSE
          </span>
        )}
      </div>

      {/* Surfaces */}
      <ul className="flex flex-1 flex-col gap-0.5 px-2 py-2">
        {SURFACES.map((surface) => {
          const Icon = surface.icon;
          const link = (
            <NavLink
              to={surface.route}
              end={surface.route === "/"}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-md px-2.5 py-2 text-xs transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
                  isActive
                    ? "bg-elevated text-ink-primary"
                    : "text-ink-secondary hover:bg-elevated/60 hover:text-ink-primary",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    size={17}
                    className={cn(
                      "shrink-0 transition-colors",
                      isActive
                        ? "text-sig-live"
                        : "text-ink-hint group-hover:text-ink-secondary",
                    )}
                    aria-hidden="true"
                  />
                  {!collapsed && (
                    <span className="flex-1 truncate font-medium">{surface.label}</span>
                  )}
                  {!collapsed && surface.status === "construction" && (
                    <span
                      className="size-1.5 rounded-full bg-sig-warn"
                      aria-label={`In construction, phase ${surface.phase}`}
                    />
                  )}
                </>
              )}
            </NavLink>
          );

          return (
            <li key={surface.id}>
              {collapsed ? (
                <Tooltip side="right" content={surface.label}>
                  {link}
                </Tooltip>
              ) : (
                link
              )}
            </li>
          );
        })}
      </ul>

      {/* Steering + collapse control */}
      <div className="border-t border-line-faint p-2">
        <NavLink
          to="/steering"
          className={({ isActive }) =>
            cn(
              "mb-0.5 flex items-center gap-3 rounded-md px-2.5 py-2 text-xs transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
              isActive
                ? "bg-elevated text-ink-primary"
                : "text-ink-secondary hover:bg-elevated/60 hover:text-ink-primary",
            )
          }
        >
          <Sliders size={17} className="shrink-0 text-ink-hint" aria-hidden="true" />
          {!collapsed && <span className="font-medium">Steering</span>}
        </NavLink>
        <button
          type="button"
          onClick={toggleSidebar}
          className={cn(
            "flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-xs",
            "text-ink-hint transition-colors hover:bg-elevated hover:text-ink-secondary",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen size={17} aria-hidden="true" />
          ) : (
            <>
              <PanelLeftClose size={17} aria-hidden="true" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </nav>
  );
}
