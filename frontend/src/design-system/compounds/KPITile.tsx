import { type ReactNode } from "react";
import { cn } from "@lib/cn";

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

const TONE_CLASS = {
  neutral: "border-border",
  ok: "border-confidence-ok/40",
  warn: "border-confidence-warn/40",
  risk: "border-confidence-risk/50",
} as const;

/**
 * Mission Control KPI tile. Headline number, optional sparkline, optional
 * threshold-driven tone, optional Link to a source page (FE-P1).
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
        "syn-card border-l-4 px-4 py-3 transition-colors duration-fast ease-standard",
        TONE_CLASS[tone],
        className,
      )}
    >
      <div className="text-2xs uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="text-2xl font-semibold tabular-nums text-ink">{value}</div>
        {delta && (
          <span
            className={cn(
              "text-xs font-medium tabular-nums",
              delta.value >= 0 ? "text-signal-success" : "text-signal-danger",
            )}
          >
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
