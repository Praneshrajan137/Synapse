/**
 * SYNAPSE Atlas Console — Tier latency vs SLA mini chart.
 *
 * 4-row mini bar chart: per-tier observed p99 vs the I-8 budget. AAA
 * contrast on rows that breach budget — that's the operator's primary
 * "this agent is hot" signal at a glance.
 */
import { memo } from "react";

import { Badge } from "@shared/ui/badge";
import { cn } from "@shared/ui/cn";

const SLA_MS: Record<string, number> = {
  tier_1: 100,
  tier_2: 500,
  tier_3: 15_000,
  tier_4: 120_000,
};

export interface TierLatency {
  readonly tier: keyof typeof SLA_MS;
  readonly p99_ms: number | null;
}

export interface LatencyVsSlaProps {
  readonly rows: readonly TierLatency[];
}

export const LatencyVsSla = memo(function LatencyVsSla({ rows }: LatencyVsSlaProps) {
  return (
    <table
      role="table"
      aria-label="p99 latency vs SLA per tier"
      className="w-full border-collapse text-ops-xs"
    >
      <tbody>
        {rows.map((row) => {
          const sla = SLA_MS[row.tier];
          const ratio =
            row.p99_ms !== null && sla !== undefined
              ? Math.min(1, row.p99_ms / sla)
              : 0;
          const breach = row.p99_ms !== null && sla !== undefined && row.p99_ms > sla;
          return (
            <tr key={row.tier} className="border-b border-border/30 last:border-0">
              <td className="w-16 py-1 text-muted-fg">{row.tier.replace("tier_", "T")}</td>
              <td className="py-1">
                <div
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={sla ?? 0}
                  aria-valuenow={row.p99_ms ?? 0}
                  aria-label={`${row.tier} p99`}
                  className="h-2 w-full overflow-hidden rounded-full bg-muted"
                >
                  <div
                    className={cn(
                      "h-full rounded-full",
                      breach ? "bg-safety-critical" : "bg-tier-2",
                    )}
                    style={{ width: `${ratio * 100}%` }}
                  />
                </div>
              </td>
              <td className="w-24 py-1 pl-2 text-right tabular-nums">
                {row.p99_ms === null ? (
                  <span className="text-muted-fg">—</span>
                ) : breach ? (
                  <Badge variant="critical">{(row.p99_ms / 1000).toFixed(2)}s</Badge>
                ) : (
                  <span>{row.p99_ms} ms</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
});
