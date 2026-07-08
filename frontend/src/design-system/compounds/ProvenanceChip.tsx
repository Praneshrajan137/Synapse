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
 * The tri-state honesty classification of a proposal's structured provenance
 * (Req 4.7). Extracted as a pure, React-free helper so the classification is
 * unit- and property-testable (Property 16):
 *
 *   "degraded"    → degraded=true (fallback path) — ALWAYS surfaced, even when
 *                   the rest of the provenance is incomplete (Req 4.8 wins).
 *   "present"     → complete structured provenance: model version, feature
 *                   source, AND confidence basis are all present.
 *   "unavailable" → provenance is absent, or present but incomplete — rendered
 *                   as an explicit "provenance unavailable" marker, NEVER
 *                   omitted silently.
 */
export type ProvenanceStatus = "degraded" | "present" | "unavailable";

export function provenanceStatus(p: ProvenanceLike | null | undefined): ProvenanceStatus {
  if (p && p.degraded === true) return "degraded";
  if (!p) return "unavailable";
  const complete = Boolean(p.model_version && p.feature_source && p.confidence_basis);
  return complete ? "present" : "unavailable";
}

/**
 * The Honesty Channel's per-output marker (FE-INV-034, Req 4.7/4.8): every
 * rendered provenance shows model version, feature source, and the confidence
 * basis; a degraded (fallback-path) output is UNMISSABLE — chroma-drained
 * colour (INV-CLR-016) plus an explicit text label, never colour alone
 * (INV-CLR-011). Absent or incomplete provenance renders an explicit
 * "provenance unavailable" marker rather than being silently omitted.
 */
export function ProvenanceChip({ provenance, className }: ProvenanceChipProps) {
  const { t } = useTranslation("common");
  const status = provenanceStatus(provenance);

  // Req 4.7: absent/incomplete provenance is disclosed, never omitted.
  if (status === "unavailable") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-2xs font-medium",
          "text-ink-subtle",
          className,
        )}
        role="img"
        aria-label={t("provenance.unavailable")}
        title={t("provenance.unavailable")}
      >
        <span aria-hidden>—</span>
        {t("provenance.unavailable")}
      </span>
    );
  }

  const p = provenance as ProvenanceLike;
  const degraded = status === "degraded";
  const basis = p.confidence_basis?.replace(/_/g, " ");
  const detail = [
    p.model_version && `${t("provenance.model")}: ${p.model_version}`,
    p.feature_source && `${t("provenance.features")}: ${p.feature_source}`,
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
        <span className="font-mono">{p.model_version ?? t("provenance.real")}</span>
      )}
    </span>
  );
}
