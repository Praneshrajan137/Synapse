import { LineChart, Line, ReferenceLine, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { cn } from "@lib/cn";

interface CalibrationCurveProps {
  readonly points: ReadonlyArray<{ nominal: number; empirical: number }>;
  readonly target?: number; // INV-DP-002: 0.85
  readonly height?: number;
  readonly className?: string;
}

/**
 * Calibration coverage curve. Empirical (y) vs nominal (x); reference
 * lines at y=x (perfect calibration) and y=0.85 (INV-DP-002 floor).
 */
export function CalibrationCurve({
  points,
  target = 0.85,
  height = 180,
  className,
}: CalibrationCurveProps) {
  return (
    <div className={cn("h-[180px] w-full", className)} style={{ height }}>
      <ResponsiveContainer>
        <LineChart data={points as { nominal: number; empirical: number }[]}>
          <XAxis
            dataKey="nominal"
            type="number"
            domain={[0, 1]}
            tick={{ fill: "rgb(148 163 184)", fontSize: 10 }}
          />
          <YAxis
            type="number"
            domain={[0, 1]}
            tick={{ fill: "rgb(148 163 184)", fontSize: 10 }}
          />
          <Tooltip
            contentStyle={{
              background: "rgb(15 23 42)",
              border: "1px solid rgb(51 65 85)",
              fontSize: 11,
            }}
          />
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 1, y: 1 },
            ]}
            stroke="rgb(100 116 139)"
            strokeDasharray="2 2"
          />
          <ReferenceLine y={target} stroke="rgb(34 197 94)" strokeDasharray="4 2" label={{
            value: `${(target * 100).toFixed(0)}% target`,
            position: "right",
            fill: "rgb(34 197 94)",
            fontSize: 10,
          }} />
          <Line
            type="monotone"
            dataKey="empirical"
            stroke="rgb(56 189 248)"
            strokeWidth={2}
            dot={{ r: 2 }}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
