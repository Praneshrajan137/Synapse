import { DataPathNotice } from "@ds/compounds";
import { useAutonomy } from "@hooks/use-autonomy";
import { deriveAutonomyView } from "@lib/autonomy";
import { useTranslation } from "react-i18next";
import { surfaceDataPath } from "../data-paths";
import { AutonomyLoop } from "./AutonomyLoop";
import { WorldVitals } from "./WorldVitals";

/**
 * The Autonomy Spine panel for Twin Lab (ADR-053) — the world is the twin's, so
 * its live vitals + the closed loop live here. Composes the perceive→decide→act
 * →learn strip with per-city world vitals. Degrades honestly: "autonomy
 * unknown" on a failed read; individual worlds render stalled/unreachable
 * rather than fabricating a healthy snapshot.
 *
 * R4.3: `WorldVitals` labels each world synthetic per city, but `totalRestocks`
 * below is an AGGREGATE across those worlds and was rendered unlabelled inside
 * the loop strip - so the one number on this panel that sums simulated state
 * carried no synthetic marker while the per-city cards did. The panel now states
 * the aggregate's data path, including whether the worlds it sums report
 * `is_synthetic`. That flag is read off the worlds rather than assumed: it is a
 * computed value derived from the active WorldSource, so `false` is a state the
 * console must be able to show.
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
        <DataPathNotice
          className="justify-center"
          state={surfaceDataPath("twin-lab.autonomy-world", { degraded: true, synthetic: null })}
        />
      </div>
    );
  }

  // Only reachable worlds carry a provenance claim. An unreachable world's
  // `synthetic` value is a placeholder, not an observation, so counting it would
  // manufacture provenance the read never supplied.
  const reachableWorlds = view.worlds.filter((w) => w.kind !== "unreachable");
  const totalRestocks = view.worlds.reduce((acc, w) => acc + (w.restocks ?? 0), 0);
  const anyRestockKnown = view.worlds.some((w) => w.restocks !== null);

  const dataPath = surfaceDataPath("twin-lab.autonomy-world", {
    degraded: view.degraded,
    synthetic: reachableWorlds.length === 0 ? null : reachableWorlds.some((w) => w.synthetic),
  });

  return (
    <div className="space-y-3">
      <AutonomyLoop
        sensorRunning={view.sensorRunning && view.sensorReachable}
        polls={view.polls}
        decisionsTriggered={view.decisionsTriggered}
        restocks={anyRestockKnown ? totalRestocks : null}
      />
      <DataPathNotice state={dataPath} />
      <WorldVitals worlds={view.worlds} />
    </div>
  );
}
