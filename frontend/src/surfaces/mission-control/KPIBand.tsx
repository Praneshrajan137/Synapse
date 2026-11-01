import { DataPathNotice, KPITile } from "@ds/compounds";
import { useAutonomy } from "@hooks/use-autonomy";
import { deriveAutonomyView } from "@lib/autonomy";
import { fmt } from "@lib/formatters";
import { useFirehoseStore } from "@state/firehose.store";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { surfaceDataPath } from "../data-paths";

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
 * honesty channel forbids — so each class carries its own data-path notice.
 *
 * R4.3 lands here. Both classes are aggregates over pipeline output, and both
 * can be synthetic-sourced, by two different routes:
 *
 *  - the authoritative counters are totals over the standing WorldRuntime, so
 *    they inherit that world's `is_synthetic` - which since the source-provenance
 *    change is COMPUTED from the active WorldSource rather than pinned true. The
 *    band therefore reads the flag off the perceived worlds instead of assuming
 *    it, and says "synthetic-sourced" only when the worlds actually report it;
 *  - the live-window tiles are means and counts over decisions in the window,
 *    and the window does not filter traffic-generator pulses, so the moment one
 *    lands the aggregate is synthetic-sourced and is labelled as such.
 *
 * Both aggregations previously rendered as plain numerals with no provenance at
 * all: an operator reading "Avg confidence (live) 91%" could not tell whether
 * demo pulses were in it.
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

  const recentDecisions = useMemo(() => decisions.slice(-WINDOW), [decisions]);

  // R4.3, authoritative class. `is_synthetic` is read off the perceived worlds,
  // never assumed: `true` if any reachable world reports it, `false` if every
  // reachable world denies it, and `null` (unknown, never "real") while the
  // autonomy read has not answered or reports no reachable world.
  const reachableWorlds =
    autonomy.kind === "ready" ? autonomy.worlds.filter((w) => w.kind !== "unreachable") : [];
  const counterPath = surfaceDataPath("mission-control.autonomy-counters", {
    degraded:
      autonomy.kind === "unknown" ? true : autonomy.kind === "ready" ? autonomy.degraded : null,
    synthetic: reachableWorlds.length === 0 ? null : reachableWorlds.some((w) => w.synthetic),
  });

  // R4.3, live-window class. The firehose envelope carries `is_synthetic` per
  // decision, so this one is affirmative: an empty window makes no claim.
  const windowPath = surfaceDataPath("mission-control.live-window", {
    degraded: recentDecisions.length === 0 ? null : recentDecisions.some((d) => d.degraded),
    synthetic: recentDecisions.length === 0 ? null : recentDecisions.some((d) => d.is_synthetic),
  });

  const authoritativeTiles = useMemo(
    () => [
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
    ],
    [selfInitiated, perceptions, t],
  );

  const windowTiles = useMemo(() => {
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
  }, [recentDecisions, routes, disruptions]);

  return (
    <div className="space-y-3">
      {/* Authoritative server counters — cumulative totals over the standing
          world. Their data path (and its synthetic provenance) is stated with
          them, not in a shared caption that could be read as covering either
          class. */}
      <div className="space-y-1.5">
        <div className="grid grid-cols-2 gap-3">
          {authoritativeTiles.map((tile) => (
            <KPITile key={tile.key} label={tile.label} value={tile.value} tone={tile.tone} />
          ))}
        </div>
        <DataPathNotice state={counterPath} />
      </div>

      {/* Live window — this client's socket, not a server aggregate. */}
      <div className="space-y-1.5">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          {windowTiles.map((tile) => (
            <KPITile key={tile.key} label={tile.label} value={tile.value} tone={tile.tone} />
          ))}
        </div>
        <DataPathNotice state={windowPath} />
        <p className="text-2xs text-ink-subtle">
          Counts &amp; means over the last {WINDOW} firehose events on this client, not
          server-aggregated rates.
        </p>
      </div>
    </div>
  );
}
