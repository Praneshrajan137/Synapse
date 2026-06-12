import { ConnectionPill, PageHeader } from "@ds/compounds";
import { useFirehose } from "@hooks/use-firehose";
import { CortexBanner } from "./CortexBanner";
import { DecisionFirehoseTail } from "./DecisionFirehoseTail";
import { DisruptionBanner } from "./DisruptionBanner";
import { KPIBand } from "./KPIBand";
import { LivingMap } from "./LivingMap";
import { useCityStores } from "./useCityStores";

/**
 * Mission Control — the flagship surface (ADR-045): hero Cortex band, KPI
 * display numerals, then the asymmetric stage — the living map dominant
 * with the decision firehose as the right rail. Every panel updates from
 * the same WS multiplex; no polling.
 */
export function MissionControl() {
  const firehose = useFirehose({
    // ADR-044: `escalation` rides the same multiplexed socket, so the
    // cockpit queue fills while the operator is still on Mission Control.
    topics: ["decision", "disruption", "routing", "demand", "metric", "escalation"],
  });
  const stores = useCityStores();

  return (
    <section className="space-y-6">
      <PageHeader
        size="hero"
        title="Mission Control"
        subtitle="Live KPI band, decision firehose, and the city's living map."
        actions={
          <ConnectionPill
            state={firehose.state}
            label={firehose.connected ? "Firehose live" : "Firehose"}
          />
        }
      />

      <DisruptionBanner />

      <CortexBanner />

      <KPIBand />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <LivingMap stores={stores.data ?? []} />
        <DecisionFirehoseTail />
      </div>
    </section>
  );
}
