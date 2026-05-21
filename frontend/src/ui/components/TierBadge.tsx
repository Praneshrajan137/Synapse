import { cn } from "@/ui/lib/cn";
import { type TierKey, tierColor } from "@/ui/tokens";

/**
 * TierBadge — the decision tier as a compact, color-coded token.
 *
 * Tenet T-2: the four tiers have wildly different latency profiles, and
 * the badge surfaces that. Tier accent escalates cool to warm as the
 * latency budget grows.
 */

const TIER_META: Record<TierKey, { short: string; latency: string; full: string }> = {
  tier_1: { short: "T1", latency: "<100ms", full: "Tier 1 — RL-only, sub-100ms" },
  tier_2: { short: "T2", latency: "500ms", full: "Tier 2 — light LLM reasoning" },
  tier_3: { short: "T3", latency: "15s", full: "Tier 3 — multi-agent debate" },
  tier_4: { short: "T4", latency: "120s", full: "Tier 4 — Monte Carlo deliberation" },
};

export interface TierBadgeProps {
  tier: TierKey;
  /** Append the latency budget, e.g. "T3 · 15s". */
  showLatency?: boolean;
  className?: string;
}

export function TierBadge({ tier, showLatency = false, className }: TierBadgeProps) {
  const meta = TIER_META[tier];
  const color = tierColor[tier];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 py-0.5",
        "font-mono text-2xs font-semibold uppercase tracking-wide",
        className,
      )}
      style={{
        color,
        borderColor: `color-mix(in oklab, ${color} 40%, transparent)`,
        backgroundColor: `color-mix(in oklab, ${color} 12%, transparent)`,
      }}
      title={meta.full}
    >
      <span
        aria-hidden="true"
        className="size-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {meta.short}
      {showLatency && <span className="text-ink-hint">· {meta.latency}</span>}
    </span>
  );
}

export { TIER_META };
