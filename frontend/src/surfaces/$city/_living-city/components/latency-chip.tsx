/**
 * SYNAPSE Atlas Console — I-10 latency chip.
 *
 * Renders the gateway's p99 against the 2-second SLA budget. Reads
 * `latency_p99_ms` if any inbound metrics frame attaches it; otherwise
 * shows `—` and a muted variant. AAA contrast on the breach state.
 */
import { memo } from "react";

import { Badge } from "@shared/ui/badge";

const SLA_MS = 2_000;

export interface LatencyChipProps {
  readonly p99Ms: number | null;
}

export const LatencyChip = memo(function LatencyChip({ p99Ms }: LatencyChipProps) {
  if (p99Ms === null || !Number.isFinite(p99Ms)) {
    return (
      <Badge variant="muted" aria-label="API p99 — no data yet">
        p99 · — / {SLA_MS / 1000}s
      </Badge>
    );
  }
  const variant = p99Ms < SLA_MS ? "ok" : "critical";
  const label = `${(p99Ms / 1000).toFixed(2)}s`;
  return (
    <Badge variant={variant} aria-live="polite">
      p99 · {label} / {SLA_MS / 1000}s
    </Badge>
  );
});
