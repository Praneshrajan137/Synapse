import { DIVERGENCE_RESYNC_THRESHOLD } from "@ds/compounds/DivergenceTrace";
import { useFirehoseStore } from "@state/firehose.store";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

/**
 * Trust calibration (ADR-044 Phase 4): when the digital twin is diverging
 * from live state (KL > re-sync threshold, I-12), the confidence numbers on
 * screen rest on a model of the world that currently disagrees with the
 * world. This caveat renders next to confidence displays in the drained
 * degraded styling — an honesty marker, not an alarm (the alarm is the twin
 * channel itself). Shape + text carry the signal (INV-CLR-011).
 *
 * Reads the firehose `twin` buffer; renders nothing while the twin is
 * faithful or silent (no data is not a caveat — the DegradedBanner owns
 * systemic unknowns).
 */
export function TwinDivergenceCaveat() {
  const { t } = useTranslation("common");
  const twinEvents = useFirehoseStore((s) => s.twin.items);

  const breach = useMemo(() => {
    // Most recent divergence breach in the buffer, newest first.
    for (let i = twinEvents.length - 1; i >= 0; i--) {
      const event = twinEvents[i];
      if (!event) continue;
      const threshold =
        "threshold" in event && typeof event.threshold === "number"
          ? event.threshold
          : DIVERGENCE_RESYNC_THRESHOLD;
      if (event.kl_divergence > threshold) {
        return {
          kl: event.kl_divergence,
          agent: "agent_name" in event ? (event.agent_name as string) : undefined,
        };
      }
      // A newer in-threshold sample means the twin recovered — no caveat.
      return null;
    }
    return null;
  }, [twinEvents]);

  if (!breach) return null;

  return (
    <span
      className="inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-2xs font-medium text-state-degraded"
      style={{ background: "color-mix(in oklab, var(--syn-state-degraded) 15%, transparent)" }}
      role="img"
      aria-label={t("twin.caveat_aria", { kl: breach.kl.toFixed(3) })}
      title={
        breach.agent
          ? t("twin.caveat_title_agent", { agent: breach.agent, kl: breach.kl.toFixed(3) })
          : t("twin.caveat_title", { kl: breach.kl.toFixed(3) })
      }
    >
      <span aria-hidden>≉</span>
      {t("twin.caveat")}
    </span>
  );
}
