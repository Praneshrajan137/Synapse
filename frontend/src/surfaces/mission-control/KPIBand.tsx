import { KPITile } from "@ds/compounds";
import { useAutonomy } from "@hooks/use-autonomy";
import { deriveAutonomyView } from "@lib/autonomy";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

/**
 * KPI band with an HONEST split between two data classes (ADR-044/053):
 *
 *  - AUTHORITATIVE server counters, from `GET /api/v1/system/autonomy`: the
 *    SensorLoop's cumulative self-initiated decisions and perceptions. These
 *    are real server-side totals, not a client sample.
 *  - LIVE-WINDOW proxies, from this client's firehose ring buffers: counts and
 *    means over the last N events actually received on THIS socket. Labelled
 *    explicitly so they never imply a server-aggregated rate.
 *
 * Mixing the two without saying which is which is the exact over-claim the
 * honesty channel forbids — so the caption names each class.
 */
const WINDOW = 60;

export function KPIBand() {
  const { t } = useTranslation("common");
  const decisions = useFirehoseStore((s) => s.decisions.items);
  const routes = useFirehoseStore((s) => s.routes.items);
  const disruptions = useFirehoseStore((s) => s.disruptions.items);

  const autonomyQuery = useAutonomy();
  const autonomy = deriveAutonomyView({
    data: autonomyQuery.data,
    isError: autonomyQuery.isError,
    isPending: autonomyQuery.isPending,
  });
  const selfInitiated = autonomy.kind === "ready" ? autonomy.decisionsTriggered : null;
  const perceptions = autonomy.kind === "ready" ? autonomy.polls : null;

  const tiles = useMemo(() => {
    const recentDecisions = decisions.slice(-WINDOW);
    const recentRoutes = routes.slice(-WINDOW);
    const avgDeliveryMin =
      recentRoutes.length === 0
        ? null
        : recentRoutes.reduce((acc, r) => acc + r.total_time_min, 0) / recentRoutes.length;
    const confidenceAvg =
      recentDecisions.length === 0
        ? null
        : recentDecisions.reduce((acc, d) => acc + d.confidence, 0) / recentDecisions.length;
    const escalations = recentDecisions.filter((d) => d.escalated).length;

    return [
      // ── Authoritative (server counters) ──────────────────────────────────
      {
        key: "self_initiated",
        label: t("autonomy.self_initiated"),
        value: selfInitiated === null ? "—" : fmt.compact(selfInitiated),
        tone: "neutral" as const,
      },
      {
        key: "perceptions",
        label: t("autonomy.polls"),
        value: perceptions === null ? "—" : fmt.compact(perceptions),
        tone: "neutral" as const,
      },
      // ── Live window (this client's firehose) ─────────────────────────────
      {
        key: "orders_min",
        label: "Decisions (live)",
        value: fmt.compact(recentDecisions.length),
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
        value: fmt.compact(disruptions.length),
        tone: disruptions.length === 0 ? ("neutral" as const) : ("risk" as const),
      },
    ];
  }, [decisions, routes, disruptions, selfInitiated, perceptions, t]);

  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {tiles.map((tile) => (
          <KPITile key={tile.key} label={tile.label} value={tile.value} tone={tile.tone} />
        ))}
      </div>
      <p className="text-2xs text-ink-subtle">
        Self-initiated &amp; perceptions are authoritative server counters (cumulative). The rest
        are a live window — counts &amp; means over the last {WINDOW} firehose events on this
        client, not server-aggregated rates.
      </p>
    </div>
  );
}
