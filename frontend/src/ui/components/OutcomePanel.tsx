import type { DecisionOutcome } from "@/domain/decision";
import { cn } from "@/ui/lib/cn";
import { signed } from "@/ui/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/ui/primitives";
import { signal } from "@/ui/tokens";

/**
 * OutcomePanel — the decision's measured outcome, 24h later.
 *
 * This is where prediction meets reality — the source of trust
 * calibration (tenet T-8). When no outcome is in yet, the panel says so
 * plainly rather than implying success.
 */

interface OutcomeMetric {
  label: string;
  value: number;
  unit: string;
  goodWhenPositive: boolean;
}

export interface OutcomePanelProps {
  outcome: DecisionOutcome | null;
  className?: string;
}

export function OutcomePanel({ outcome, className }: OutcomePanelProps) {
  if (!outcome) {
    return (
      <Card tone="elevated" className={className}>
        <CardHeader>
          <CardTitle>Outcome</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-2xs text-ink-hint">
            No outcome measured yet — KPIs are joined 24 hours after execution.
          </p>
        </CardBody>
      </Card>
    );
  }

  const metrics: OutcomeMetric[] = [
    {
      label: "Fill rate",
      value: outcome.fillRateDelta,
      unit: "pp",
      goodWhenPositive: true,
    },
    {
      label: "Waste rate",
      value: outcome.wasteRateDelta,
      unit: "pp",
      goodWhenPositive: false,
    },
    { label: "On-time", value: outcome.onTimeDelta, unit: "pp", goodWhenPositive: true },
    { label: "Margin", value: outcome.marginDelta, unit: "₹", goodWhenPositive: true },
  ];

  return (
    <Card tone="elevated" className={className}>
      <CardHeader>
        <CardTitle>Measured outcome</CardTitle>
        <span className="text-2xs text-ink-hint">+24h</span>
      </CardHeader>
      <CardBody>
        <ul className="flex flex-col gap-1.5">
          {metrics.map((metric) => {
            const favorable = metric.goodWhenPositive
              ? metric.value > 0
              : metric.value < 0;
            const color =
              metric.value === 0 ? signal.live : favorable ? signal.ok : signal.stop;
            return (
              <li
                key={metric.label}
                className={cn(
                  "flex items-center justify-between border-b border-line-faint/60 pb-1.5 last:border-0",
                )}
              >
                <span className="text-2xs text-ink-secondary">{metric.label}</span>
                <span className="tnum font-mono text-xs" style={{ color }}>
                  {metric.unit === "₹" ? "₹" : ""}
                  {signed(metric.value, metric.unit === "₹" ? 0 : 1)}
                  {metric.unit !== "₹" ? ` ${metric.unit}` : ""}
                </span>
              </li>
            );
          })}
        </ul>
      </CardBody>
    </Card>
  );
}
