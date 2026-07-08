import {
  AttentionBeacon,
  BuildSHAChip,
  CatchUpBanner,
  CitySwitcher,
  DegradedBanner,
  OperatorIdentity,
  ThemeToggle,
} from "@ds/compounds";
import { BrandMark } from "@ds/primitives";
import { cn } from "@lib/cn";
import { useEscalationStore } from "@state/escalation.store";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router-dom";
import { CommandPalette } from "./CommandPalette";
import { PRIMARY_SURFACES } from "./primary-surfaces";

// Nav grouped by the operator's loop (Sprint 18) — Monitor → Intervene →
// Investigate → Configure — so the structure mirrors how the work actually
// flows, not the order features were built. The nav is DERIVED from the
// `PRIMARY_SURFACES` route registry (`primary-surfaces.ts`) so the nav, the
// command palette, and the coverage property test share one source of truth.

/**
 * App shell. Top bar (brand + nav + city + operator), main outlet.
 * Replaces App.jsx:20-48. Real-time pills (WS status, tier latency) are
 * mounted by surfaces that need them — keeping the shell stable across
 * routes so KV-cache-like client-side render stays inexpensive.
 */
export function Shell() {
  const { t } = useTranslation("common");
  // Live count of decisions awaiting a human (I-5). Drives the Cockpit nav
  // badge so the human-in-the-loop backlog is visible from every surface.
  const pendingEscalations = useEscalationStore(
    (s) => s.entries.filter((e) => e.status === "pending").length,
  );
  return (
    <div className="flex h-screen flex-col bg-canvas text-ink">
      {/* Obsidian chrome (ADR-045): panel-step bar with an inset bottom
          hairline instead of a border; the BrandMark pulse-ring glyph;
          nav active = brand underline rail. */}
      <header
        className="flex items-center gap-6 bg-surface px-6 py-2"
        style={{ boxShadow: "inset 0 -1px 0 rgb(var(--syn-border) / 0.6)" }}
      >
        <div className="flex items-center gap-2.5">
          <BrandMark />
          <span className="font-display text-sm font-semibold tracking-[0.08em] text-ink">
            SYNAPSE
          </span>
          <span className="hidden text-2xs uppercase tracking-[0.2em] text-ink-subtle md:inline">
            Console
          </span>
        </div>
        <nav aria-label="Primary" className="flex flex-1 items-center gap-0.5 overflow-x-auto">
          {PRIMARY_SURFACES.map((item, i) => (
            <div key={item.path} className="flex items-center">
              {/* thin divider between operator-loop groups */}
              {i > 0 && PRIMARY_SURFACES[i - 1]?.group !== item.group && (
                <span aria-hidden className="mx-1.5 h-4 w-px bg-border" />
              )}
              <NavLink
                to={item.path}
                {...(item.end ? { end: item.end } : {})}
                title={`${t(`nav.group.${item.group}`)} · ${t(item.labelKey)}`}
                className={({ isActive }) =>
                  cn(
                    "relative whitespace-nowrap rounded px-3 py-2 text-xs font-medium transition-colors duration-fast ease-standard",
                    "focus-visible:outline-none focus-visible:shadow-focus",
                    "after:absolute after:inset-x-3 after:-bottom-px after:h-0.5 after:rounded-full after:transition-colors after:duration-fast",
                    isActive
                      ? "text-ink after:bg-brand"
                      : "text-ink-muted after:bg-transparent hover:bg-surface-raised/60 hover:text-ink",
                  )
                }
              >
                {t(item.labelKey)}
                {item.path === "/cockpit" && pendingEscalations > 0 && (
                  <span
                    className="ml-1.5 inline-flex min-w-4 items-center justify-center rounded-full bg-signal-danger/20 px-1 text-2xs font-semibold tabular-nums text-signal-danger"
                    aria-label={`${pendingEscalations} awaiting decision`}
                  >
                    {pendingEscalations}
                  </span>
                )}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <AttentionBeacon />
          <CitySwitcher />
          <ThemeToggle />
          <OperatorIdentity />
          <BuildSHAChip />
        </div>
      </header>
      {/* ADR-044: system-level honesty — brownout/breaker degradation is
          visible on EVERY surface, not buried in Prometheus (FE-INV-035). */}
      <DegradedBanner />
      <CatchUpBanner />
      <main className="flex-1 overflow-auto bg-canvas p-6">
        <Outlet />
      </main>
      <CommandPalette />
    </div>
  );
}
