import { cn } from "@lib/cn";
import type { ReactNode } from "react";

interface KPITileProps {
  readonly label: string;
  readonly value: ReactNode;
  readonly delta?: { readonly value: number; readonly label?: string };
  readonly sparkline?: ReactNode;
  readonly threshold?: { readonly ok: number; readonly warn: number };
  readonly raw?: number;
  readonly className?: string;
  readonly href?: string;
  readonly tone?: "neutral" | "ok" | "warn" | "risk";
}

// Obsidian (ADR-045): the accent rail is EARNED — only an alerting tile
// carries one; a healthy tile is a quiet borderless card.
const TONE_RAIL = {
  neutral: "",
  ok: "border-l-2 border-confidence-ok/60",
  warn: "border-l-2 border-confidence-warn/70",
  risk: "border-l-2 border-confidence-risk/80",
} as const;

/**
 * Mission Control KPI tile. Tracked micro-label, display numeral
 * (Space Grotesk, tabular), signal-coloured delta with a direction glyph.
 */
export function KPITile({
  label,
  value,
  delta,
  sparkline,
  className,
  tone = "neutral",
}: KPITileProps) {
  return (
    <div
      className={cn(
        "syn-card px-4 py-3 transition-colors duration-fast ease-standard",
        TONE_RAIL[tone],
        className,
      )}
    >
      <div className="text-2xs uppercase tracking-[0.14em] text-ink-subtle">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="font-display text-display-lg font-medium tabular-nums text-ink">
          {value}
        </div>
        {delta && (
          <span
            className={cn(
              "text-xs font-medium tabular-nums",
              delta.value >= 0 ? "text-signal-success" : "text-signal-danger",
            )}
          >
            <span aria-hidden>{delta.value >= 0 ? "▲" : "▼"} </span>
            {delta.value >= 0 ? "+" : ""}
            {delta.value.toFixed(1)}
            {delta.label ?? "%"}
          </span>
        )}
      </div>
      {sparkline && <div className="mt-2 h-8">{sparkline}</div>}
    </div>
  );
}
