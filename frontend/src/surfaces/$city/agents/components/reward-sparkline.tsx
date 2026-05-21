/**
 * SYNAPSE Atlas Console — agent reward sparkline.
 *
 * Visx LinePath over a 24-hour reward series. The series is bounded
 * to the last `MAX_POINTS` so the panel stays rendering-cheap. Tokens
 * drive the stroke + axis colour so dark + light themes inherit.
 */
import { memo, useMemo } from "react";
import { Group } from "@visx/group";
import { LinePath } from "@visx/shape";
import { scaleLinear } from "@visx/scale";

const MAX_POINTS = 144; // 24h at 10-minute granularity

export interface RewardSparklineProps {
  readonly series: readonly number[];
  readonly width?: number;
  readonly height?: number;
}

export const RewardSparkline = memo(function RewardSparkline({
  series,
  width = 200,
  height = 36,
}: RewardSparklineProps) {
  const data = useMemo(() => series.slice(-MAX_POINTS), [series]);

  if (data.length === 0) {
    return (
      <div
        role="img"
        aria-label="Reward sparkline — no data yet"
        style={{ width, height }}
        className="grid place-items-center text-ops-xs text-muted-fg"
      >
        —
      </div>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const xScale = scaleLinear<number>({
    domain: [0, Math.max(1, data.length - 1)],
    range: [0, width],
  });
  const yScale = scaleLinear<number>({
    domain: [min === max ? min - 1 : min, max === min ? max + 1 : max],
    range: [height - 2, 2],
  });

  return (
    <svg width={width} height={height} role="img" aria-label="Reward · last 24h">
      <Group>
        <LinePath
          data={data.map((y, i) => ({ x: i, y }))}
          x={(d) => xScale(d.x)}
          y={(d) => yScale(d.y)}
          stroke="rgb(var(--color-tier-2))"
          strokeWidth={1.4}
          strokeOpacity={0.95}
        />
      </Group>
    </svg>
  );
});
