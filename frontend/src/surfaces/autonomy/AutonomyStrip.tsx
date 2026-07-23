import { useAutonomy } from "@hooks/use-autonomy";
import { deriveAutonomyView } from "@lib/autonomy";
import { cn } from "@lib/cn";
import { fmt } from "@lib/formatters";
import { useTranslation } from "react-i18next";

/**
 * Compact autonomy status for the Mission Control hero (ADR-053): is the
 * perceive→decide loop alive, and how many decisions has the system convened on
 * its own? The self-initiated count is the honest headline of the autonomy
 * story. Renders "autonomy unknown" on a failed read — never a healthy lie.
 */
export function AutonomyStrip({ className }: { readonly className?: string }) {
  const { t } = useTranslation("common");
  const query = useAutonomy();
  const view = deriveAutonomyView({
    data: query.data,
    isError: query.isError,
    isPending: query.isPending,
  });

  if (view.kind === "loading") {
    return <div className={cn("h-6 w-40 animate-pulse rounded bg-surface-raised", className)} />;
  }

  if (view.kind === "unknown") {
    return (
      <p
        className={cn("flex items-center gap-1.5 text-xs font-medium", className)}
        style={{ color: "var(--syn-state-degraded)" }}
      >
        <span aria-hidden>▲</span>
        {t("autonomy.unknown")}
      </p>
    );
  }

  const running = view.sensorRunning && view.sensorReachable;
  return (
    <div className={cn("flex items-center gap-3 text-xs", className)}>
      <span
        className="flex items-center gap-1.5 font-medium"
        style={{ color: running ? "var(--syn-accent)" : "var(--syn-state-degraded)" }}
      >
        <span aria-hidden className={running ? "animate-breathe" : ""}>
          {running ? "⟳" : "▲"}
        </span>
        {running ? t("autonomy.sensor.running") : t("autonomy.sensor.stopped")}
      </span>
      <span className="text-ink-muted">
        <span className="font-display font-medium tabular-nums text-ink">
          {view.decisionsTriggered === null ? "—" : fmt.compact(view.decisionsTriggered)}
        </span>{" "}
        {t("autonomy.self_initiated").toLowerCase()}
      </span>
      {view.degraded && (
        <span style={{ color: "var(--syn-state-degraded)" }} title={t("autonomy.unknown_detail")}>
          {t("posture.degraded").toLowerCase()}
        </span>
      )}
    </div>
  );
}
