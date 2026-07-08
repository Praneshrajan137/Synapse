import { usePosture } from "@hooks/use-posture";
import { derivePostureBanner } from "@lib/posture-banner";
import { useTranslation } from "react-i18next";

/**
 * The Honesty Channel's system-level signal (ADR-044 D4, FE-INV-035): when
 * ANY city is shedding work (brownout) or ANY dependency breaker is open,
 * a non-dismissible banner names the degradation. A posture fetch failure
 * renders "posture unknown" — the banner NEVER fails silently green.
 *
 * Renders nothing only when the orchestrator affirmatively reports a
 * healthy posture. Chroma-drained degraded colour (INV-CLR-016) + icon +
 * text — never colour alone (INV-CLR-011). The posture→banner derivation is
 * the pure `derivePostureBanner` helper (Property 32).
 */
export function DegradedBanner() {
  const { t } = useTranslation("common");
  const posture = usePosture();

  // Still loading the very first poll → nothing to assert yet.
  if (posture.isPending) return null;

  const state = derivePostureBanner({ isError: posture.isError, data: posture.data });
  // Affirmatively healthy → no banner.
  if (state.kind === "healthy") return null;

  const unknown = state.kind === "unknown";
  const detail = unknown
    ? t("posture.unknown_detail")
    : [
        ...state.brownout.map(([city, level]) => t("posture.brownout_item", { city, level })),
        ...state.openBreakers.map(([name, breaker]) =>
          t("posture.breaker_item", { name, state: breaker }),
        ),
      ].join(" · ");

  return (
    <output
      aria-live="polite"
      className="flex items-center gap-2 border-b px-6 py-1.5 text-xs font-medium text-state-degraded"
      style={{
        background: "color-mix(in oklab, var(--syn-state-degraded) 12%, transparent)",
        borderColor: "color-mix(in oklab, var(--syn-state-degraded) 35%, transparent)",
      }}
    >
      <span aria-hidden>▲</span>
      <span className="font-semibold uppercase tracking-wide">
        {unknown ? t("posture.unknown") : t("posture.degraded")}
      </span>
      <span className="text-ink-muted">{detail}</span>
    </output>
  );
}
