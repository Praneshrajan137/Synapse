import { cn } from "@lib/cn";
import { useTranslation } from "react-i18next";

interface SyntheticBadgeProps {
  readonly className?: string;
}

/**
 * Marks a traffic-generator decision (`is_synthetic`, ADR-044 D5) so demo
 * pulses are never mistaken for real commerce (FE-INV-036). The violet
 * synthetic state colour is paired with a DASHED border and the text label —
 * the non-colour signals (INV-CLR-011); under CVD or grayscale the dashed
 * ring still reads.
 */
export function SyntheticBadge({ className }: SyntheticBadgeProps) {
  const { t } = useTranslation("common");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border border-dashed px-1.5 py-0.5",
        "text-2xs font-medium uppercase tracking-wide text-state-synthetic",
        className,
      )}
      style={{ borderColor: "var(--syn-state-synthetic)" }}
      role="img"
      aria-label={t("synthetic.aria")}
      title={t("synthetic.title")}
    >
      <span aria-hidden>◌</span>
      {t("synthetic.label")}
    </span>
  );
}
