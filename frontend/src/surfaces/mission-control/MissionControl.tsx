import { ConnectionPill } from "@ds/compounds";
import { useFirehose } from "@hooks/use-firehose";
import { DecisionFirehoseTail } from "./DecisionFirehoseTail";
import { DisruptionBanner } from "./DisruptionBanner";
import { KPIBand } from "./KPIBand";
import { LivingMap } from "./LivingMap";
import { useCityStores } from "./useCityStores";

/**
 * Mission Control — P2 elevation. KPIs + map + decision firehose + alerts.
 * Every panel updates from the same WS multiplex; no polling.
 */
export function MissionControl() {
  const firehose = useFirehose({
    topics: ["decision", "disruption", "routing", "demand", "metric"],
  });
  const stores = useCityStores();

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-semibold text-ink">Mission Control</h1>
          <p className="text-sm text-ink-muted">
            Live KPI band, decision firehose, and the city's living map.
          </p>
        </div>
        <ConnectionPill
          state={firehose.state}
          label={firehose.connected ? "Firehose live" : "Firehose"}
        />
      </header>

      <DisruptionBanner />

      <KPIBand />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <LivingMap stores={stores.data ?? []} />
        <DecisionFirehoseTail />
      </div>
    </section>
  );
}
