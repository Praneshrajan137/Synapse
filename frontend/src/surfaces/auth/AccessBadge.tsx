import { Badge } from "@ds/primitives";
import { useTranslation } from "react-i18next";
import { useAccessStore } from "./access.store";

/**
 * The persistent, honest access marker (ADR-057). While the gateway runs open, every
 * guarded surface carries it, so no visitor mistakes preview access for an operator
 * sign-in, and nobody mistakes a console that can act for one that only reads.
 */
export function AccessBadge() {
  const access = useAccessStore((s) => s.access);
  const { t } = useTranslation("auth");
  if (access.kind !== "open") return null;
  const canAct = access.authority === "act";
  return (
    <output aria-live="polite" className="pointer-events-none fixed right-3 bottom-3 z-40">
      <Badge
        tone={canAct ? "warning" : "info"}
        title={t(canAct ? "preview.badge_title_act" : "preview.badge_title_view")}
        className="pointer-events-auto"
      >
        {t(canAct ? "preview.badge_act" : "preview.badge_view")}
      </Badge>
    </output>
  );
}
