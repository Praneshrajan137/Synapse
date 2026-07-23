import { cn } from "@lib/cn";
import { fmt } from "@lib/formatters";
import { useTranslation } from "react-i18next";

interface AutonomyLoopProps {
  readonly sensorRunning: boolean;
  readonly polls: number | null;
  readonly decisionsTriggered: number | null;
  readonly restocks: number | null;
  readonly className?: string;
}

/**
 * The closed loop made legible (ADR-052/053): perceive → decide → act → learn,
 * with LIVE counts where an honest one exists (perceptions = sensor polls,
 * self-initiated = decisions the SensorLoop convened, acts = world restocks).
 * "Learn" carries no fabricated number — the realized-outcome scoring lives on
 * the decision surfaces (ADR-047); here it is the closing edge of the cycle.
 *
 * Motion is a slow directional shimmer at the ambient cadence, frozen under
 * prefers-reduced-motion; the arrows + labels carry the meaning without it.
 */
export function AutonomyLoop({
  sensorRunning,
  polls,
  decisionsTriggered,
  restocks,
  className,
}: AutonomyLoopProps) {
  const { t } = useTranslation("common");

  const phases: ReadonlyArray<{ key: string; label: string; count: string | null }> = [
    {
      key: "perceive",
      label: t("autonomy.phase.perceive"),
      count: polls === null ? null : fmt.compact(polls),
    },
    {
      key: "decide",
      label: t("autonomy.phase.decide"),
      count: decisionsTriggered === null ? null : fmt.compact(decisionsTriggered),
    },
    {
      key: "act",
      label: t("autonomy.phase.act"),
      count: restocks === null ? null : fmt.compact(restocks),
    },
    { key: "learn", label: t("autonomy.phase.learn"), count: null },
  ];

  return (
    <div className={cn("flex items-center gap-1", className)} aria-label={t("autonomy.title")}>
      {phases.map((p, i) => (
        <div key={p.key} className="flex items-center gap-1">
          <div
            className={cn(
              "syn-card flex min-w-[4.5rem] flex-col items-center px-2.5 py-1.5",
              sensorRunning && i === 0 ? "border-l-2 border-accent/60" : "",
            )}
          >
            <span className="text-2xs uppercase tracking-wide text-ink-subtle">{p.label}</span>
            <span className="font-display text-sm font-medium tabular-nums text-ink">
              {p.count ?? "·"}
            </span>
          </div>
          {i < phases.length - 1 && (
            <span
              aria-hidden
              className={cn("text-ink-subtle", sensorRunning ? "animate-breathe" : "")}
            >
              →
            </span>
          )}
        </div>
      ))}
      {/* closing edge: learn feeds back to perceive */}
      <span aria-hidden className="text-ink-subtle">
        ↺
      </span>
    </div>
  );
}
