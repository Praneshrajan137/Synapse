import { useAutonomy } from "@hooks/use-autonomy";
import { deriveAutonomyView } from "@lib/autonomy";
import { useTranslation } from "react-i18next";
import { AutonomyLoop } from "./AutonomyLoop";
import { WorldVitals } from "./WorldVitals";

/**
 * The Autonomy Spine panel for Twin Lab (ADR-053) — the world is the twin's, so
 * its live vitals + the closed loop live here. Composes the perceive→decide→act
 * →learn strip with per-city world vitals. Degrades honestly: "autonomy
 * unknown" on a failed read; individual worlds render stalled/unreachable
 * rather than fabricating a healthy snapshot.
 */
export function AutonomyPanel() {
  const { t } = useTranslation("common");
  const query = useAutonomy();
  const view = deriveAutonomyView({
    data: query.data,
    isError: query.isError,
    isPending: query.isPending,
  });

  if (view.kind === "loading") {
    return <div className="h-40 animate-pulse rounded-lg bg-surface-raised" />;
  }

  if (view.kind === "unknown") {
    return (
      <div className="syn-card px-4 py-6 text-center">
        <p
          className="flex items-center justify-center gap-1.5 text-sm font-medium"
          style={{ color: "var(--syn-state-degraded)" }}
        >
          <span aria-hidden>▲</span>
          {t("autonomy.unknown")}
        </p>
        <p className="mt-1 text-xs text-ink-subtle">{t("autonomy.unknown_detail")}</p>
      </div>
    );
  }

  const totalRestocks = view.worlds.reduce((acc, w) => acc + (w.restocks ?? 0), 0);
  const anyRestockKnown = view.worlds.some((w) => w.restocks !== null);

  return (
    <div className="space-y-3">
      <AutonomyLoop
        sensorRunning={view.sensorRunning && view.sensorReachable}
        polls={view.polls}
        decisionsTriggered={view.decisionsTriggered}
        restocks={anyRestockKnown ? totalRestocks : null}
      />
      <WorldVitals worlds={view.worlds} />
    </div>
  );
}
