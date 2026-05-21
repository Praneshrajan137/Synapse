import { useTierDistribution } from "@/application/system";
import { TIER_META } from "@/ui/components/TierBadge";
import { cn } from "@/ui/lib/cn";
import type { TierKey } from "@/ui/tokens";
import { tierColor } from "@/ui/tokens";

/**
 * TierHistogram — the decision-tier mix over the last hour.
 *
 * Invariant I-10 requires Tier 1 to be at least 80% of decisions. When
 * it drops below that, the T1 bar glows amber — the interface itself
 * polices the invariant.
 */

const TIERS: readonly TierKey[] = ["tier_1", "tier_2", "tier_3", "tier_4"];
const T1_FLOOR = 0.8;

export function TierHistogram({ className }: { className?: string }) {
  const { data } = useTierDistribution();
  const t1Breached = data ? data.tier_1 < T1_FLOOR : false;

  return (
    <section aria-label="Tier distribution" className={cn("bg-paper p-3", className)}>
      <header className="mb-2.5 flex items-center justify-between">
        <h2 className="font-display text-2xs font-semibold uppercase tracking-[0.14em] text-ink-secondary">
          Tier Mix · 1h
        </h2>
        {t1Breached && <span className="text-2xs text-sig-warn">T1 below 80% floor</span>}
      </header>
      <div className="flex flex-col gap-2">
        {TIERS.map((tier) => {
          const fraction = data?.[tier] ?? 0;
          const color = tierColor[tier];
          const breached = tier === "tier_1" && t1Breached;
          return (
            <div key={tier} className="flex items-center gap-2">
              <span
                className="w-6 shrink-0 font-mono text-2xs font-semibold"
                style={{ color }}
              >
                {TIER_META[tier].short}
              </span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-membrane">
                <div
                  className={cn("h-full rounded-full", breached && "animate-breathe")}
                  style={{
                    width: `${Math.max(fraction * 100, 1.5)}%`,
                    backgroundColor: breached ? "var(--color-sig-warn)" : color,
                  }}
                />
              </div>
              <span className="tnum w-9 shrink-0 text-right font-mono text-2xs text-ink-secondary">
                {(fraction * 100).toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
