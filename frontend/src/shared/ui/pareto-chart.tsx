/**
 * SYNAPSE Atlas Console — Pareto front scatter (TS port).
 *
 * Recharts retained at S2 (legacy compat). New visualisations land on
 * Visx — see ADR-025. The knee point gets a star marker; the rest are
 * dots. Both inherit `fill-tier-*` so the same chart looks correct in
 * light and dark themes.
 */
import { memo } from "react";
import { ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

export interface ParetoPoint {
  readonly [key: string]: number | string | undefined;
}

export interface ParetoChartProps {
  readonly front: readonly ParetoPoint[];
  readonly kneeIndex?: number;
  readonly xKey: string;
  readonly yKey: string;
  readonly height?: number;
}

export const ParetoChart = memo(function ParetoChart({
  front,
  kneeIndex = 0,
  xKey,
  yKey,
  height = 280,
}: ParetoChartProps) {
  const data = front.map((pt, i) => ({ ...pt, isKnee: i === kneeIndex }));
  const knee = data.filter((d) => d.isKnee);
  const rest = data.filter((d) => !d.isKnee);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 16, left: 8 }}>
        <XAxis
          dataKey={xKey}
          name={xKey}
          type="number"
          stroke="rgb(var(--color-muted-fg))"
          tick={{ fill: "rgb(var(--color-muted-fg))" }}
        />
        <YAxis
          dataKey={yKey}
          name={yKey}
          type="number"
          stroke="rgb(var(--color-muted-fg))"
          tick={{ fill: "rgb(var(--color-muted-fg))" }}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          contentStyle={{
            backgroundColor: "rgb(var(--color-card))",
            color: "rgb(var(--color-card-fg))",
            border: "1px solid rgb(var(--color-border))",
            borderRadius: "0.375rem",
          }}
        />
        <Scatter name="Pareto front" data={rest} fill="rgb(var(--color-tier-2))" />
        <Scatter name="Knee point" data={knee} fill="rgb(var(--color-tier-3))" shape="star" />
      </ScatterChart>
    </ResponsiveContainer>
  );
});
