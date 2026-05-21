/**
 * SYNAPSE Atlas Console — Living City route (S4 deep work).
 *
 * Plan §5.1 contract:
 *   - KPI band (5 tiles, derived from synapse.metrics.agent).
 *   - Deck.gl + MapLibre map with dark stores, riders, routes,
 *     freshness heatmap toggle, disruption pins.
 *   - Right-rail event tail across 9 user-visible topics.
 *   - Footer: tier-distribution histogram + I-10 p99 chip.
 *
 * Acceptance: 100K markers @ 60 fps via Deck.gl; LCP ≤ 3.0 s for this
 * route per plan §10. Map + 3D vendor chunks are async (vite.config.ts
 * manualChunks) so the shell stays under 120 KB gz.
 */
import { createFileRoute, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/button";
import { KPITicker } from "@shared/ui/kpi-ticker";

import { EventTail } from "./_living-city/components/event-tail";
import { LatencyChip } from "./_living-city/components/latency-chip";
import { LivingMap } from "./_living-city/components/living-map";
import { TierHistogram } from "./_living-city/components/tier-histogram";
import { useKpi } from "./_living-city/hooks/use-kpi";
import { useMultiStream } from "./_living-city/hooks/use-multi-stream";
import { USER_VISIBLE_TOPICS } from "./_living-city/model/event";

export const Route = createFileRoute("/$city/")({
  component: LivingCity,
});

function LivingCity() {
  const { t } = useTranslation();
  const { city } = useParams({ from: "/$city/" });

  const { kpi } = useKpi();
  const { events, connectionsHealthy, connectionsTotal } = useMultiStream({
    topics: USER_VISIBLE_TOPICS,
    maxBuffer: 200,
  });

  const [showFreshness, setShowFreshness] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);

  // p99 placeholder — wired to the Prometheus push via the OTel collector
  // in S6 hardening. Until then we render the muted "no data" chip.
  const p99: number | null = null;

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-3 lg:h-[calc(100vh-5rem)]">
      <header className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-ops-xl font-bold tracking-tight">
          {t("livingCity.title")}
        </h1>
        <span className="text-ops-sm text-muted-fg">{t(`city.${city}`)}</span>
        <span className="ml-auto flex items-center gap-2 text-ops-xs text-muted-fg">
          {connectionsHealthy} / {connectionsTotal} streams live
        </span>
        <LatencyChip p99Ms={p99} />
      </header>

      <KPITicker data={kpi} />

      <div className="grid flex-1 grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex flex-col gap-3 overflow-hidden">
          <LivingMap
            cityId={city}
            events={events}
            showFreshness={showFreshness}
            showRoutes={showRoutes}
            className="flex-1 min-h-[360px]"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              variant={showFreshness ? "primary" : "outline"}
              onClick={() => setShowFreshness((s) => !s)}
              aria-pressed={showFreshness}
            >
              {t("livingCity.layers.freshnessHeatmap")}
            </Button>
            <Button
              size="sm"
              variant={showRoutes ? "primary" : "outline"}
              onClick={() => setShowRoutes((s) => !s)}
              aria-pressed={showRoutes}
            >
              {t("livingCity.layers.routes")}
            </Button>
            <TierHistogram events={events} className="ml-auto" />
          </div>
        </div>
        <EventTail events={events} className="overflow-hidden" />
      </div>
    </div>
  );
}
