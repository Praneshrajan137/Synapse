/**
 * SYNAPSE Atlas Console — Twin Studio fan-out viz.
 *
 * Visx Area + LinePath: shaded region between p10 and p90, p50 line on
 * top. Tokens drive every colour.
 */
import { memo, useMemo } from "react";
import { Group } from "@visx/group";
import { Area, LinePath } from "@visx/shape";
import { scaleLinear } from "@visx/scale";

import type { WhatIfResult } from "../model/scenario";

export interface FanOutChartProps {
  readonly result: WhatIfResult;
  readonly width?: number;
  readonly height?: number;
}

export const FanOutChart = memo(function FanOutChart({
  result,
  width = 600,
  height = 240,
}: FanOutChartProps) {
  const { p10 = [], p50 = [], p90 = [] } = useMemo(() => {
    const out: Record<string, { t: number; value: number }[]> = {};
    for (const [k, v] of Object.entries(result.percentiles)) {
      out[k] = v.slice().sort((a, b) => a.t - b.t);
    }
    return { p10: out["p10"] ?? [], p50: out["p50"] ?? [], p90: out["p90"] ?? [] };
  }, [result]);

  const xs = [...p10, ...p50, ...p90].map((d) => d.t);
  const ys = [...p10, ...p50, ...p90].map((d) => d.value);
  if (xs.length === 0) {
    return (
      <div
        role="img"
        aria-label="Scenario fan-out — empty"
        style={{ width, height }}
        className="grid place-items-center text-ops-sm text-muted-fg"
      >
        No simulation data yet — run a scenario to populate.
      </div>
    );
  }
  const xScale = scaleLinear<number>({ domain: [Math.min(...xs), Math.max(...xs)], range: [44, width - 12] });
  const yScale = scaleLinear<number>({ domain: [Math.min(...ys), Math.max(...ys)], range: [height - 24, 12], nice: true });

  // Synthesize the band by zipping p10/p90; the orchestrator should hand us
  // aligned samples but we tolerate ragged inputs by trimming.
  const bandLength = Math.min(p10.length, p90.length);
  const band = Array.from({ length: bandLength }, (_, i) => ({
    t: p10[i]!.t,
    low: p10[i]!.value,
    high: p90[i]!.value,
  }));

  return (
    <svg width={width} height={height} role="img" aria-label="Scenario fan-out (p10 / p50 / p90)">
      <Group>
        <Area<{ t: number; low: number; high: number }>
          data={band}
          x={(d) => xScale(d.t)}
          y0={(d) => yScale(d.low)}
          y1={(d) => yScale(d.high)}
          fill="rgb(var(--color-tier-2) / 0.18)"
        />
        <LinePath
          data={p50}
          x={(d) => xScale(d.t)}
          y={(d) => yScale(d.value)}
          stroke="rgb(var(--color-tier-2))"
          strokeWidth={1.6}
        />
      </Group>
    </svg>
  );
});
