import { cn } from "@lib/cn";
import { useTranslation } from "react-i18next";

/**
 * Structured provenance (ADR-040/ADR-044) — how an agent output was produced.
 * Mirrors `synapse_common.models.Provenance` as it appears inside each
 * proposal dict on the wire.
 */
export interface ProvenanceLike {
  readonly model_version?: string | null;
  readonly feature_source?: string | null;
  readonly degraded?: boolean | null;
  readonly confidence_basis?: string | null;
}

interface ProvenanceChipProps {
  readonly provenance: ProvenanceLike | null | undefined;
  readonly className?: string;
}

/**
 * The Honesty Channel's per-output marker (FE-INV-034): every rendered
 * provenance shows model version, feature source, and the confidence basis;
 * a degraded (fallback-path) output is UNMISSABLE — chroma-drained colour
 * (INV-CLR-016) plus an explicit text label, never colour alone
 * (INV-CLR-011). Renders nothing when the proposal predates ADR-044.
 */
export function ProvenanceChip({ provenance, className }: ProvenanceChipProps) {
  const { t } = useTranslation("common");
  if (!provenance) return null;

  const degraded = provenance.degraded === true;
  const basis = provenance.confidence_basis?.replace(/_/g, " ");
  const detail = [
    provenance.model_version && `${t("provenance.model")}: ${provenance.model_version}`,
    provenance.feature_source && `${t("provenance.features")}: ${provenance.feature_source}`,
    basis && `${t("provenance.basis")}: ${basis}`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-2xs font-medium",
        degraded ? "text-state-degraded" : "text-ink-muted",
        className,
      )}
      style={
        degraded
          ? { background: "color-mix(in oklab, var(--syn-state-degraded) 15%, transparent)" }
          : undefined
      }
      role="img"
      aria-label={
        degraded ? `${t("provenance.degraded")} — ${detail}` : `${t("provenance.real")} — ${detail}`
      }
      title={detail}
    >
      {degraded ? (
        <>
          <span aria-hidden>▲</span>
          {t("provenance.degraded")}
        </>
      ) : (
        <span className="font-mono">{provenance.model_version ?? t("provenance.real")}</span>
      )}
    </span>
  );
}
