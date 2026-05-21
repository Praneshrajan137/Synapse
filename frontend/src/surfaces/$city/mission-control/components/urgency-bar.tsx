/**
 * SYNAPSE Atlas Console — Urgency Bar.
 *
 * Sticky banner at the top of Mission Control. Renders only when at
 * least one tier-4 escalation has ≤30s remaining. Plan §5.2.
 *
 * AAA contrast: `bg-safety-critical` over `text-bg` clears 7:1 on both
 * themes — see tokens.css. The bar is also an `aria-live="assertive"`
 * region so a screen reader announces the change immediately.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@shared/ui/cn";

import type { Escalation } from "../model/escalation";
import { timeToTimeoutSeconds } from "../model/ranker";

export interface UrgencyBarProps {
  readonly criticals: readonly Escalation[];
  readonly now: number;
  readonly className?: string;
}

export const UrgencyBar = memo(function UrgencyBar({
  criticals,
  now,
  className,
}: UrgencyBarProps) {
  const { t } = useTranslation();
  if (criticals.length === 0) return null;

  // Show the most urgent (least remaining) seconds.
  const minRemaining = criticals.reduce((acc, e) => {
    const r = timeToTimeoutSeconds(e, now);
    return Math.min(acc, Number.isFinite(r) ? r : acc);
  }, Number.POSITIVE_INFINITY);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "sticky top-0 z-20 flex items-center gap-3 rounded-md bg-safety-critical px-4 py-2 text-bg shadow-md",
        className,
      )}
    >
      <span className="font-semibold uppercase tracking-wider">
        {t("tier.tier_4")}
      </span>
      <span>
        {t("missionControl.escalation.countdown", {
          seconds: Math.max(0, Math.ceil(minRemaining)),
        })}
      </span>
      <span className="ml-auto text-ops-sm font-medium tabular-nums">
        {criticals.length}
      </span>
    </div>
  );
});
