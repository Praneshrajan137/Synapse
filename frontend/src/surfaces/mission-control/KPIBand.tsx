import { useMemo } from "react";
import { KPITile } from "@ds/compounds";
import { useFirehoseStore } from "@state/firehose.store";
import { fmt } from "@lib/formatters";

/**
 * KPI band derived from the firehose store. Tiles update as decisions /
 * routes / demand arrive. P2 ships the seed metrics; P4 wires the rest
 * via the BE `metric` channel.
 */
export function KPIBand() {
  const decisions = useFirehoseStore((s) => s.decisions.items);
  const routes = useFirehoseStore((s) => s.routes.items);
  const disruptions = useFirehoseStore((s) => s.disruptions.items);

  const tiles = useMemo(() => {
    const recentDecisions = decisions.slice(-60);
    const recentRoutes = routes.slice(-60);
    const ordersPerMin = recentDecisions.length;
    const avgDeliveryMin =
      recentRoutes.length === 0
        ? null
        : recentRoutes.reduce((acc, r) => acc + r.total_time_min, 0) / recentRoutes.length;
    const confidenceAvg =
      recentDecisions.length === 0
        ? null
        : recentDecisions.reduce((acc, d) => acc + d.confidence, 0) / recentDecisions.length;
    const escalations = recentDecisions.filter((d) => d.escalated_to_human).length;
    const activeDisruptions = disruptions.length;

    return [
      {
        key: "orders_min",
        label: "Decisions / min",
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
        label: "Avg confidence",
        value: confidenceAvg !== null ? `${(confidenceAvg * 100).toFixed(0)}%` : "—",
        tone:
          confidenceAvg !== null
            ? confidenceAvg >= 0.9
              ? ("ok" as const)
              : confidenceAvg >= 0.7
                ? ("warn" as const)
                : ("risk" as const)
            : ("neutral" as const),
      },
      {
        key: "escalations",
        label: "Escalations",
        value: fmt.compact(escalations),
        tone: escalations === 0 ? ("ok" as const) : ("warn" as const),
      },
      {
        key: "disruptions",
        label: "Active disruptions",
        value: fmt.compact(activeDisruptions),
        tone: activeDisruptions === 0 ? ("ok" as const) : ("risk" as const),
      },
      {
        key: "routes",
        label: "Routes / window",
        value: fmt.compact(routes.length),
        tone: "neutral" as const,
      },
    ];
  }, [decisions, routes, disruptions]);

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {tiles.map((t) => (
        <KPITile key={t.key} label={t.label} value={t.value} tone={t.tone} />
      ))}
    </div>
  );
}
