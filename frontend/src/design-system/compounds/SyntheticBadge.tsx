import { cn } from "@lib/cn";
import { useTranslation } from "react-i18next";

/**
 * Which scope of synthetic provenance this badge marks.
 *
 *   "decision"  - ONE traffic-generator decision (`is_synthetic`, ADR-044 D5).
 *                 The original scope: a demo pulse in a live tail.
 *   "aggregate" - a rolled-up value every input of which came from a state
 *                 whose `is_synthetic` is true (R4.3). Distinct copy on
 *                 purpose: "Demo" describes one row, and would understate an
 *                 aggregate whose ENTIRE basis is a seeded simulation.
 */
export type SyntheticBadgeVariant = "decision" | "aggregate";

interface SyntheticBadgeProps {
  readonly variant?: SyntheticBadgeVariant;
  readonly className?: string;
}

const COPY: Record<SyntheticBadgeVariant, { label: string; aria: string; title: string }> = {
  decision: {
    label: "synthetic.label",
    aria: "synthetic.aria",
    title: "synthetic.title",
  },
  aggregate: {
    label: "synthetic.aggregate_label",
    aria: "synthetic.aggregate_aria",
    title: "synthetic.aggregate_title",
  },
};

/**
 * Marks synthetic provenance so simulated data is never mistaken for real
 * commerce (FE-INV-036, R4.3). The violet synthetic state colour is paired
 * with a DASHED border and the text label - the non-colour signals
 * (INV-CLR-011); under CVD or grayscale the dashed ring still reads.
 *
 * `variant="decision"` (default) marks one traffic-generator decision.
 * `variant="aggregate"` marks a value derived from a synthetic world state and
 * reads "synthetic-sourced", which is the claim R4.3 requires on the surface
 * displaying the aggregate. Only the aggregate variant is static: a per-row
 * demo pulse keeps the ambient breathing cadence, while an aggregate label is
 * a standing fact about the data and must not read as an arriving event.
 */
export function SyntheticBadge({ variant = "decision", className }: SyntheticBadgeProps) {
  const { t } = useTranslation("common");
  const copy = COPY[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border border-dashed px-1.5 py-0.5",
        "text-2xs font-medium uppercase tracking-wide text-state-synthetic",
        // The demo pulse: staged traffic breathes at the ambient cadence.
        // Under prefers-reduced-motion the animation freezes; the dashed
        // ring + label still carry the state (FE-INV-040, INV-CLR-011).
        variant === "decision" && "animate-demo-pulse",
        className,
      )}
      style={{ borderColor: "var(--syn-state-synthetic)" }}
      role="img"
      aria-label={t(copy.aria)}
      title={t(copy.title)}
    >
      <span aria-hidden>◌</span>
      {t(copy.label)}
    </span>
  );
}
