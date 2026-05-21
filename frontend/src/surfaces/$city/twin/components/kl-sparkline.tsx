/**
 * SYNAPSE Atlas Console — KL-divergence sparkline (I-12).
 *
 * Plots `kl_divergence` from the WhatIfResult as a small line. A red
 * AAA-contrast banner fires when the latest reading exceeds 0.1
 * (KL_DIVERGENCE_THRESHOLD) — the operator's signal that the twin has
 * drifted from the live distribution.
 */
import { memo, useMemo } from "react";
import { Group } from "@visx/group";
import { LinePath } from "@visx/shape";
import { scaleLinear } from "@visx/scale";
import { useTranslation } from "react-i18next";

import { Badge } from "@shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";

import { KL_DIVERGENCE_THRESHOLD, type WhatIfResult } from "../model/scenario";

export interface KlSparklineProps {
  readonly result: WhatIfResult;
  readonly width?: number;
  readonly height?: number;
}

export const KlSparkline = memo(function KlSparkline({
  result,
  width = 360,
  height = 80,
}: KlSparklineProps) {
  const { t } = useTranslation();
  const series = useMemo(() => result.kl_divergence.slice().sort((a, b) => a.t - b.t), [result]);
  const latest = series[series.length - 1]?.value ?? 0;
  const overThreshold = latest > KL_DIVERGENCE_THRESHOLD;

  const xScale = scaleLinear<number>({
    domain: [series[0]?.t ?? 0, series[series.length - 1]?.t ?? 1],
    range: [4, width - 4],
  });
  const yMax = Math.max(KL_DIVERGENCE_THRESHOLD * 1.5, ...series.map((d) => d.value));
  const yScale = scaleLinear<number>({ domain: [0, yMax], range: [height - 4, 4] });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-ops-base">
          {t("twinStudio.results.klDivergence")}
          {overThreshold ? (
            <Badge variant="critical" aria-live="assertive">
              {t("twinStudio.results.klOverThreshold")}
            </Badge>
          ) : (
            <Badge variant="ok">{latest.toFixed(3)}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {series.length === 0 ? (
          <div className="text-ops-sm text-muted-fg">No divergence data yet.</div>
        ) : (
          <svg width={width} height={height} role="img" aria-label="KL divergence over scenario duration">
            <Group>
              {/* Threshold reference line. */}
              <line
                x1={4}
                x2={width - 4}
                y1={yScale(KL_DIVERGENCE_THRESHOLD)}
                y2={yScale(KL_DIVERGENCE_THRESHOLD)}
                stroke="rgb(var(--color-safety-critical))"
                strokeWidth={1}
                strokeDasharray="4 3"
                opacity={0.6}
              />
              <LinePath
                data={series}
                x={(d) => xScale(d.t)}
                y={(d) => yScale(d.value)}
                stroke={
                  overThreshold
                    ? "rgb(var(--color-safety-critical))"
                    : "rgb(var(--color-tier-2))"
                }
                strokeWidth={1.6}
              />
            </Group>
          </svg>
        )}
      </CardContent>
    </Card>
  );
});
