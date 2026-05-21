/**
 * SYNAPSE Atlas Console — tier-distribution histogram.
 *
 * Plan §5.1 footer: rolling 5-minute distribution of decisions by tier.
 * Visx-driven so the colour stays in lock-step with the design tokens.
 *
 * Source signal is the `synapse.orchestrator.decision` SSE topic; the
 * surface counts decisions by tier within a 5-minute window.
 */
import { memo, useMemo } from "react";
import { Group } from "@visx/group";
import { Bar } from "@visx/shape";
import { scaleBand, scaleLinear } from "@visx/scale";
import { useTranslation } from "react-i18next";

import { cn } from "@shared/ui/cn";

import type { TailEvent } from "../model/event";

const TIERS = ["tier_1", "tier_2", "tier_3", "tier_4"] as const;
type Tier = (typeof TIERS)[number];

const TIER_FILL: Record<Tier, string> = {
  tier_1: "rgb(var(--color-tier-1))",
  tier_2: "rgb(var(--color-tier-2))",
  tier_3: "rgb(var(--color-tier-3))",
  tier_4: "rgb(var(--color-tier-4))",
};

const WINDOW_MS = 5 * 60 * 1000;

export interface TierHistogramProps {
  readonly events: readonly TailEvent[];
  readonly width?: number;
  readonly height?: number;
  readonly className?: string;
}

export const TierHistogram = memo(function TierHistogram({
  events,
  width = 360,
  height = 120,
  className,
}: TierHistogramProps) {
  const { t } = useTranslation();

  const counts = useMemo<Record<Tier, number>>(() => {
    const out: Record<Tier, number> = { tier_1: 0, tier_2: 0, tier_3: 0, tier_4: 0 };
    const cutoff = Date.now() - WINDOW_MS;
    for (const e of events) {
      if (e.topic !== "synapse.orchestrator.decision") continue;
      if (e.receivedAt < cutoff) continue;
      const body = e.body as { tier?: string };
      if (body.tier && (TIERS as readonly string[]).includes(body.tier)) {
        out[body.tier as Tier] += 1;
      }
    }
    return out;
  }, [events]);

  const maxCount = Math.max(1, ...TIERS.map((tier) => counts[tier]));

  const xScale = scaleBand<Tier>({
    domain: TIERS,
    range: [40, width - 8],
    padding: 0.25,
  });
  const yScale = scaleLinear<number>({
    domain: [0, maxCount],
    range: [height - 24, 8],
    nice: true,
  });

  return (
    <figure
      className={cn(
        "flex flex-col gap-1 rounded-md border border-border bg-card p-3",
        className,
      )}
    >
      <figcaption className="text-ops-xs uppercase tracking-wide text-muted-fg">
        Tier distribution · 5 min
      </figcaption>
      <svg width={width} height={height} role="img" aria-label="Tier distribution last 5 minutes">
        <Group>
          {TIERS.map((tier) => {
            const count = counts[tier];
            const x = xScale(tier) ?? 0;
            const y = yScale(count);
            const w = xScale.bandwidth();
            const h = height - 24 - y;
            return (
              <Group key={tier}>
                <Bar
                  x={x}
                  y={y}
                  width={w}
                  height={Math.max(0, h)}
                  fill={TIER_FILL[tier]}
                  rx={3}
                />
                <text
                  x={x + w / 2}
                  y={height - 8}
                  textAnchor="middle"
                  fontSize={10}
                  fill="rgb(var(--color-muted-fg))"
                >
                  {t(`tier.${tier}`).replace(/^Tier \d+ — /, "")}
                </text>
                <text
                  x={x + w / 2}
                  y={y - 4}
                  textAnchor="middle"
                  fontSize={11}
                  fill="rgb(var(--color-fg))"
                >
                  {count}
                </text>
              </Group>
            );
          })}
        </Group>
      </svg>
    </figure>
  );
});
