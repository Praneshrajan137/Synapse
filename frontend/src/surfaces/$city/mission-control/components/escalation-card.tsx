/**
 * SYNAPSE Atlas Console — escalation card.
 *
 * One row in the Mission Control queue. Self-contained so it works in
 * Storybook with fixture data, virtualization wrappers, and live data.
 *
 * Plan §5.2 contract:
 *   - Tier badge (color-coded; AAA on tier 4).
 *   - Confidence gauge.
 *   - Recommended-action summary.
 *   - Guardrail-violation chips.
 *   - Countdown to timeout.
 *   - Approve / Reject / Modify with hotkey hints.
 */
import { memo, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge, tierBadgeVariant } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { ConfidenceGauge } from "@shared/ui/confidence-gauge";
import { cn } from "@shared/ui/cn";

import type { Escalation } from "../model/escalation";
import { timeToTimeoutSeconds } from "../model/ranker";

export interface EscalationCardProps {
  readonly escalation: Escalation;
  readonly focused?: boolean;
  readonly disabled?: boolean;
  readonly onApprove: () => void;
  readonly onReject: () => void;
  readonly onModify: () => void;
  readonly onFocus?: () => void;
}

function severityToVariant(severity: string): "warn" | "alert" | "critical" | "muted" {
  switch (severity) {
    case "critical":
      return "critical";
    case "alert":
      return "alert";
    case "warn":
      return "warn";
    default:
      return "muted";
  }
}

export const EscalationCard = memo(function EscalationCard({
  escalation,
  focused = false,
  disabled = false,
  onApprove,
  onReject,
  onModify,
  onFocus,
}: EscalationCardProps) {
  const { t } = useTranslation();

  // Smooth countdown — re-renders 1× per second only while this card is
  // visible. Mounted-only ticks avoid burning CPU on virtualized rows
  // that are unmounted off-screen.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const remaining = timeToTimeoutSeconds(escalation, now);
  const remainingDisplay = Number.isFinite(remaining)
    ? Math.ceil(remaining)
    : null;

  const tierVariant = tierBadgeVariant(escalation.tier);
  const isCritical = escalation.tier === "tier_4" && remainingDisplay !== null && remainingDisplay <= 30;

  return (
    <article
      role="article"
      aria-current={focused ? "true" : undefined}
      tabIndex={focused ? 0 : -1}
      onFocus={onFocus}
    >
      <Card
        className={cn(
          "border-border transition-shadow",
          focused && "shadow-md ring-2 ring-ring",
          isCritical && "border-safety-critical/60",
        )}
      >
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-3 text-ops-base">
            <ConfidenceGauge
              value={escalation.confidence}
              size={56}
              ariaLabel={t("missionControl.escalation.confidence", {
                value: escalation.confidence,
              })}
            />
            <div className="flex min-w-0 flex-col">
              <span className="font-mono text-ops-sm text-muted-fg">
                {escalation.decision_id.slice(0, 8)}…
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <Badge variant={tierVariant}>{t(`tier.${escalation.tier}`)}</Badge>
                {escalation.violations.map((v, i) => (
                  <Badge key={`${v.code}-${i}`} variant={severityToVariant(v.severity)}>
                    {v.code}
                  </Badge>
                ))}
              </span>
            </div>
            {remainingDisplay !== null && (
              <span
                className={cn(
                  "ml-auto text-ops-sm font-semibold tabular-nums",
                  isCritical ? "text-safety-critical" : "text-muted-fg",
                )}
                aria-label={t("missionControl.escalation.countdown", {
                  seconds: remainingDisplay,
                })}
              >
                {t("missionControl.escalation.countdown", { seconds: remainingDisplay })}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <RecommendedAction action={escalation.recommended_action} />

          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="primary"
              disabled={disabled}
              onClick={onApprove}
              aria-keyshortcuts="Enter"
            >
              {t("missionControl.escalation.approve")}{" "}
              <kbd className="ml-1 text-ops-xs opacity-80">⏎</kbd>
            </Button>
            <Button
              size="sm"
              variant="safety"
              disabled={disabled}
              onClick={onReject}
              aria-keyshortcuts="r"
            >
              {t("missionControl.escalation.reject")}{" "}
              <kbd className="ml-1 text-ops-xs opacity-80">r</kbd>
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={disabled}
              onClick={onModify}
              aria-keyshortcuts="m"
            >
              {t("missionControl.escalation.modify")}{" "}
              <kbd className="ml-1 text-ops-xs opacity-80">m</kbd>
            </Button>
          </div>
        </CardContent>
      </Card>
    </article>
  );
});

function RecommendedAction({ action }: { action: unknown }) {
  if (action === null || action === undefined) {
    return null;
  }
  return (
    <pre
      aria-label="Recommended action"
      className="mt-1 max-h-32 overflow-auto rounded-md bg-muted p-2 text-ops-xs text-muted-fg"
    >
      {JSON.stringify(action, null, 2)}
    </pre>
  );
}
