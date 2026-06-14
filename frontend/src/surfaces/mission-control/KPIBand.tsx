import { KPITile } from "@ds/compounds";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useMemo } from "react";

/**
 * KPI band derived from the firehose store. These are an HONEST live-window
 * view — counts/means over the last N events actually received on this client's
 * socket, NOT server-aggregated rates. (Real rate/SLO metrics await a typed BE
 * `metric` channel; until then we label the window explicitly rather than imply
 * authority — ADR-044 honesty.)
 */
const WINDOW = 60;

export function KPIBand() {
  const decisions = useFirehoseStore((s) => s.decisions.items);
  const routes = useFirehoseStore((s) => s.routes.items);
  const disruptions = useFirehoseStore((s) => s.disruptions.items);

  const tiles = useMemo(() => {
    const recentDecisions = decisions.slice(-WINDOW);
    const recentRoutes = routes.slice(-WINDOW);
    const ordersPerMin = recentDecisions.length;
    const avgDeliveryMin =
      recentRoutes.length === 0
        ? null
        : recentRoutes.reduce((acc, r) => acc + r.total_time_min, 0) / recentRoutes.length;
    const confidenceAvg =
      recentDecisions.length === 0
        ? null
        : recentDecisions.reduce((acc, d) => acc + d.confidence, 0) / recentDecisions.length;
    const escalations = recentDecisions.filter((d) => d.escalated).length;
    const activeDisruptions = disruptions.length;

    return [
      {
        key: "orders_min",
        label: "Decisions (live)",
        value: fmt.compact(ordersPerMin),
        tone: "neutral" as const,
      },
      {
        key: "avg_delivery_min",
        label: "Avg route time",
        value: avgDeliveryMin !== null ? `${fmt.decimal(avgDeliveryMin, 1)}m` : "—",
        tone: avgDeliveryMin && avgDeliveryMin > 15 ? ("warn" as const) : ("neutral" as const),
      },
      {
        key: "confidence",
        label: "Avg confidence (live)",
        value: confidenceAvg !== null ? `${(confidenceAvg * 100).toFixed(0)}%` : "—",
        // Quiet by default (P3): healthy = neutral; colour only when the gate
        // is at risk. The Pulse above already carries the live confidence temp.
        tone:
          confidenceAvg !== null
            ? confidenceAvg >= 0.9
              ? ("neutral" as const)
              : confidenceAvg >= 0.7
                ? ("warn" as const)
                : ("risk" as const)
            : ("neutral" as const),
      },
      {
        key: "escalations",
        label: "Escalations",
        value: fmt.compact(escalations),
        tone: escalations === 0 ? ("neutral" as const) : ("warn" as const),
      },
      {
        key: "disruptions",
        label: "Recent disruptions",
        value: fmt.compact(activeDisruptions),
        tone: activeDisruptions === 0 ? ("neutral" as const) : ("risk" as const),
      },
      {
        key: "routes",
        label: "Routes (live)",
        value: fmt.compact(routes.length),
        tone: "neutral" as const,
      },
    ];
  }, [decisions, routes, disruptions]);

  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {tiles.map((t) => (
          <KPITile key={t.key} label={t.label} value={t.value} tone={t.tone} />
        ))}
      </div>
      <p className="text-2xs text-ink-subtle">
        Live window — counts &amp; means over the last {WINDOW} firehose events on this client, not
        server-aggregated rates.
      </p>
    </div>
  );
}
