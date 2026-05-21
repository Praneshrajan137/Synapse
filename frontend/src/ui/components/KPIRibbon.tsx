import { useKpis } from "@/application/system";
import type { Kpi } from "@/domain/kpi";
import { isFavorable } from "@/domain/kpi";
import { KPISpark } from "@/ui/charts/KPISpark";
import { cn } from "@/ui/lib/cn";
import { Skeleton } from "@/ui/primitives";
import { signal } from "@/ui/tokens";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";

/**
 * KPIRibbon — the Bridge's at-a-glance metric strip.
 *
 * Each cell shows the value, a 24h sparkline, and a trend marker whose
 * color reflects whether the movement is *good*, not merely "up"
 * (tenet T-8 — trust is calibrated).
 */

function trendColor(kpi: Kpi): string {
  const favorable = isFavorable(kpi.trend, kpi.polarity);
  if (favorable === null) return "var(--color-ink-hint)";
  return favorable ? signal.ok : signal.stop;
}

function TrendIcon({ kpi }: { kpi: Kpi }) {
  const color = trendColor(kpi);
  const props = { size: 13, style: { color }, "aria-hidden": true } as const;
  if (kpi.trend === "up") return <TrendingUp {...props} />;
  if (kpi.trend === "down") return <TrendingDown {...props} />;
  return <Minus {...props} />;
}

function KpiCell({ kpi }: { kpi: Kpi }) {
  return (
    <div className="flex min-w-44 flex-1 flex-col gap-1.5 border-r border-line-faint px-4 py-3 last:border-r-0">
      <div className="flex items-center justify-between">
        <span className="font-display text-2xs font-semibold uppercase tracking-[0.12em] text-ink-hint">
          {kpi.label}
        </span>
        <TrendIcon kpi={kpi} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className="tnum font-display text-2xl font-semibold text-ink-primary">
          {kpi.value.toFixed(kpi.precision)}
        </span>
        {kpi.unit && <span className="text-xs text-ink-hint">{kpi.unit}</span>}
      </div>
      <KPISpark
        data={kpi.series}
        {...(kpi.band ? { band: kpi.band } : {})}
        width={168}
        height={26}
        color={trendColor(kpi)}
        label={`${kpi.label} trend, last 24 hours`}
      />
      {kpi.trackRecord !== undefined && (
        <span className="text-2xs text-ink-disabled">
          {(kpi.trackRecord * 100).toFixed(0)}% in-band · 7d
        </span>
      )}
    </div>
  );
}

export function KPIRibbon({ className }: { className?: string }) {
  const { data, isLoading } = useKpis();

  return (
    <section
      aria-label="Key performance indicators"
      className={cn(
        "flex items-stretch overflow-x-auto border-b border-line-faint bg-paper",
        className,
      )}
    >
      {isLoading || !data
        ? Array.from({ length: 6 }, (_, i) => (
            <div
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length skeleton
              key={i}
              className="flex min-w-44 flex-1 flex-col gap-2 border-r border-line-faint px-4 py-3"
            >
              <Skeleton shape="line" className="w-20" />
              <Skeleton shape="line" className="h-6 w-16" />
              <Skeleton shape="line" className="h-6 w-full" />
            </div>
          ))
        : data.map((kpi) => <KpiCell key={kpi.id} kpi={kpi} />)}
    </section>
  );
}
