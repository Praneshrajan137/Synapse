import React from "react";
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

// Pareto front of the multi-objective consensus. The front is plotted in the
// brand/system hue; the knee point — the recommended trade-off — is lifted
// out in the autonomous-confidence hue and a star shape (colour + shape, so
// the knee reads without colour too).
export default function ParetoChart({
  front = [],
  kneeIndex = 0,
  xKey = "demand_accuracy",
  yKey = "route_efficiency",
}) {
  const data = front.map((pt, i) => ({ ...pt, isKnee: i === kneeIndex }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 12, right: 20, bottom: 24, left: 8 }}>
        <CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" />
        <XAxis
          dataKey={xKey}
          name={xKey}
          type="number"
          stroke="var(--color-text-tertiary)"
          tick={{ fill: "var(--color-text-tertiary)", fontSize: 11 }}
        />
        <YAxis
          dataKey={yKey}
          name={yKey}
          type="number"
          stroke="var(--color-text-tertiary)"
          tick={{ fill: "var(--color-text-tertiary)", fontSize: 11 }}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3", stroke: "var(--color-border-strong)" }}
          contentStyle={{
            background: "var(--color-surface-overlay)",
            border: "1px solid var(--color-border-strong)",
            borderRadius: "8px",
            color: "var(--color-text-primary)",
          }}
        />
        <Scatter
          name="Pareto Front"
          data={data.filter((d) => !d.isKnee)}
          fill="var(--color-brand-base)"
        />
        <Scatter
          name="Knee Point"
          data={data.filter((d) => d.isKnee)}
          fill="var(--color-confidence-autonomous)"
          shape="star"
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
