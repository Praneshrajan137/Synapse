import { cn } from "@lib/cn";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface CalibrationCurveProps {
  readonly points: ReadonlyArray<{ nominal: number; empirical: number }>;
  readonly target?: number; // INV-DP-002: 0.85
  readonly height?: number;
  readonly className?: string;
}

// Chromatic-token migration (ADR-044 Phase 4): recharts forwards these onto
// SVG/inline styles, which accept token-wrapped CSS colour functions and flip
// with [data-theme].
const CHART = {
  axisLabel: "rgb(var(--syn-ink-muted))",
  tooltipBg: "rgb(var(--syn-surface))",
  tooltipBorder: "rgb(var(--syn-border))",
  diagonal: "rgb(var(--syn-ink-subtle))",
  target: "rgb(var(--syn-signal-success))",
  empirical: "rgb(var(--syn-signal-info))",
} as const;

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
            tick={{ fill: CHART.axisLabel, fontSize: 10 }}
          />
          <YAxis type="number" domain={[0, 1]} tick={{ fill: CHART.axisLabel, fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: CHART.tooltipBg,
              border: `1px solid ${CHART.tooltipBorder}`,
              fontSize: 11,
            }}
          />
          <ReferenceLine
            segment={[
              { x: 0, y: 0 },
              { x: 1, y: 1 },
            ]}
            stroke={CHART.diagonal}
            strokeDasharray="2 2"
          />
          <ReferenceLine
            y={target}
            stroke={CHART.target}
            strokeDasharray="4 2"
            label={{
              value: `${(target * 100).toFixed(0)}% target`,
              position: "right",
              fill: CHART.target,
              fontSize: 10,
            }}
          />
          <Line
            type="monotone"
            dataKey="empirical"
            stroke={CHART.empirical}
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
