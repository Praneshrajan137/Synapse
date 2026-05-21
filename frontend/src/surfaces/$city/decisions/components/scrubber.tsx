/**
 * SYNAPSE Atlas Console — Decision Trace replay scrubber.
 *
 * S3 ships the controls bound to `?scrub=` and a 1×/5×/30× speed
 * selector. Hooking up the actual replay engine (which advances the
 * scrub position based on speed and the `since`/`until` window) lands
 * with the orchestrator's deterministic-replay endpoint in S5.
 *
 * Plan §5.3 acceptance: scrub-replay never drops a decision. We
 * therefore avoid skipping rows on every scroll — the parent surface
 * filters by timestamp, not by index, so a position change always
 * produces a stable subset of the buffered window.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@shared/ui/cn";

export type ReplaySpeed = 1 | 5 | 30;

export interface ScrubberProps {
  readonly position: number;
  readonly min: number;
  readonly max: number;
  readonly speed: ReplaySpeed;
  readonly onPosition: (next: number) => void;
  readonly onSpeed: (next: ReplaySpeed) => void;
  readonly className?: string;
}

const SPEEDS: readonly ReplaySpeed[] = [1, 5, 30];

export const Scrubber = memo(function Scrubber({
  position,
  min,
  max,
  speed,
  onPosition,
  onSpeed,
  className,
}: ScrubberProps) {
  const { t } = useTranslation();
  const safeMax = Math.max(min, max);
  const labelId = "atlas-scrubber-label";

  return (
    <div
      role="region"
      aria-labelledby={labelId}
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-md border border-border bg-card px-3 py-2",
        className,
      )}
    >
      <span id={labelId} className="text-ops-xs uppercase tracking-wide text-muted-fg">
        {t("decisionTrace.scrubber.speed")}
      </span>
      <div role="radiogroup" aria-label={t("decisionTrace.scrubber.speed")} className="flex gap-1">
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            role="radio"
            aria-checked={speed === s}
            onClick={() => onSpeed(s)}
            className={cn(
              "rounded-md px-2 py-1 text-ops-xs font-medium tabular-nums",
              speed === s
                ? "bg-primary text-primary-fg"
                : "border border-border bg-bg text-fg hover:bg-muted",
            )}
          >
            {t(`decisionTrace.scrubber.speed${s}x`)}
          </button>
        ))}
      </div>
      <input
        type="range"
        aria-label={t("decisionTrace.scrubber.speed")}
        min={min}
        max={safeMax}
        step={1_000}
        value={position}
        onChange={(e) => onPosition(Number(e.target.value))}
        className="ml-3 flex-1 accent-primary"
      />
      <time
        dateTime={new Date(position).toISOString()}
        className="ml-2 text-ops-xs tabular-nums text-muted-fg"
      >
        {new Date(position).toLocaleString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour12: false,
        })}
      </time>
    </div>
  );
});
