import React from "react";
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function ParetoChart({ front = [], kneeIndex = 0, xKey = "demand_accuracy", yKey = "route_efficiency" }) {
  const data = front.map((pt, i) => ({ ...pt, isKnee: i === kneeIndex }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
        <XAxis dataKey={xKey} name={xKey} type="number" stroke="#64748b" />
        <YAxis dataKey={yKey} name={yKey} type="number" stroke="#64748b" />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
        <Scatter name="Pareto Front" data={data.filter((d) => !d.isKnee)} fill="#38bdf8" />
        <Scatter name="Knee Point" data={data.filter((d) => d.isKnee)} fill="#f97316" shape="star" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
