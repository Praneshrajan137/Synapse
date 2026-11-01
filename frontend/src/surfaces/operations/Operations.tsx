import { PageHeader } from "@ds/compounds";
import { useSlo } from "@hooks/use-slo";
import { useCityStore } from "@state/city.store";
import { useTranslation } from "react-i18next";
import { ABSENT_DATA_PATH_IDS, SURFACE_DATA_PATHS } from "../data-paths";
import { CalibrationPanel } from "./CalibrationPanel";
import { ConfidenceDistribution } from "./ConfidenceDistribution";
import { EscalationPressure } from "./EscalationPressure";
import { SloBurnBoard } from "./SloBurnBoard";
import { SystemTrustStrip } from "./SystemTrustStrip";
import { TrustTrackRecord } from "./TrustTrackRecord";
import { UpliftSlot } from "./UpliftSlot";

/**
 * Operations — Standing Watch (ADR-047).
 *
 * Mission Control is the present tense ("what is happening now"); this is the
 * trend-and-trust tense. It answers the three questions that define supervising
 * an autonomous system: Is it trustworthy right now? Are its confidences
 * calibrated to what actually happened? Where must I intervene? Every panel is
 * honest about absent evidence — "unknown" is a first-class state, never a
 * healthy-looking default.
 *
 * R13.6 lives on this surface. Two panels below (`TrustTrackRecord`,
 * `UpliftSlot`) have NO data endpoint at all, and each renders its own declared
 * empty state. R13.6's second clause is the surface's obligation, not the
 * component's: the surface itself must state that no data path exists, so an
 * operator reading the page - not the component - learns that the absence is
 * structural rather than a quiet day. The statement is generated from the
 * registry (`ABSENT_DATA_PATH_IDS`), so a panel added to the registry with
 * `endpoint: null` appears here without an edit, and one whose endpoint lands
 * disappears from here for the same reason.
 */
export function Operations() {
  const { t } = useTranslation("common");
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

      <div className="grid gap-4 lg:grid-cols-2">
        <TrustTrackRecord />
        <UpliftSlot />
      </div>

      {/* R13.6, surface clause: an explicit statement, not a zero and not a
          blank. Enumerated from the registry so it cannot drift from the panels
          it describes. */}
      {ABSENT_DATA_PATH_IDS.length > 0 && (
        <section
          data-absent-data-paths={ABSENT_DATA_PATH_IDS.length}
          aria-label="Panels with no data path"
          className="syn-card space-y-1.5 p-4"
        >
          <h2 className="text-2xs font-medium uppercase tracking-wide text-state-degraded">
            <span aria-hidden>∅ </span>
            {t("datapath.surface_absent_title", { n: ABSENT_DATA_PATH_IDS.length })}
          </h2>
          <p className="text-2xs text-ink-subtle">{t("datapath.surface_absent_detail")}</p>
          <ul className="space-y-0.5">
            {ABSENT_DATA_PATH_IDS.map((id) => {
              const spec = SURFACE_DATA_PATHS[id];
              return (
                <li key={id} className="text-2xs text-ink-muted">
                  <span className="font-mono text-ink-subtle">{id}</span>{" "}
                  {spec.endpoint === null ? t(spec.absentDetailKey) : null}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </section>
  );
}
