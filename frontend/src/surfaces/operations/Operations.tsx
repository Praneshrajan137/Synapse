import { PageHeader } from "@ds/compounds";
import { useSlo } from "@hooks/use-slo";
import { useCityStore } from "@state/city.store";
import { CalibrationPanel } from "./CalibrationPanel";
import { ConfidenceDistribution } from "./ConfidenceDistribution";
import { EscalationPressure } from "./EscalationPressure";
import { SloBurnBoard } from "./SloBurnBoard";
import { SystemTrustStrip } from "./SystemTrustStrip";

/**
 * Operations — Standing Watch (ADR-046).
 *
 * Mission Control is the present tense ("what is happening now"); this is the
 * trend-and-trust tense. It answers the three questions that define supervising
 * an autonomous system: Is it trustworthy right now? Are its confidences
 * calibrated to what actually happened? Where must I intervene? Every panel is
 * honest about absent evidence — "unknown" is a first-class state, never a
 * healthy-looking default.
 */
export function Operations() {
  const slo = useSlo();
  const city = useCityStore((s) => s.city);

  return (
    <section className="space-y-5">
      <PageHeader
        title="Operations"
        subtitle="Standing watch — system trust, SLO burn, confidence calibration, and intervention pressure over time."
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <SystemTrustStrip />
        <EscalationPressure city={city} />
      </div>

      <SloBurnBoard data={slo.data} isError={slo.isError} />

      <div className="grid gap-4 lg:grid-cols-2">
        <CalibrationPanel city={city} />
        <ConfidenceDistribution city={city} />
      </div>
    </section>
  );
}
