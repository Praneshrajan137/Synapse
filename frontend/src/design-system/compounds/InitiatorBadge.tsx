import type { DecisionInitiator } from "@domain/primitives";
import { cn } from "@lib/cn";
import { useTranslation } from "react-i18next";

interface InitiatorBadgeProps {
  readonly initiator: DecisionInitiator;
  readonly className?: string;
}

/**
 * The three-way decision origin (ADR-053): `autonomous` (the SensorLoop
 * convened it itself — the real product story), `synthetic` (demo traffic), or
 * `operator` (human-injected). This is the honest replacement for regexing an
 * `order_id` the UI never cleanly sees.
 *
 * Each variant carries a NON-colour signal (INV-CLR-011) so it reads under CVD
 * / grayscale: a distinct glyph, border style, and text label. Autonomous uses
 * the brand/accent (the system acting on its own = the signature capability);
 * synthetic reuses the violet synthetic state with a dashed ring; operator is
 * quiet neutral. Autonomous is NEVER styled like synthetic — conflating "the
 * system decided" with "a demo pulse" is the exact lie this badge prevents.
 */
export function InitiatorBadge({ initiator, className }: InitiatorBadgeProps) {
  const { t } = useTranslation("common");

  const variant = {
    autonomous: {
      glyph: "⟳",
      colorVar: "var(--syn-accent)",
      border: "border-solid",
      text: "text-accent",
      animate: "",
    },
    synthetic: {
      glyph: "◌",
      colorVar: "var(--syn-state-synthetic)",
      border: "border-dashed",
      text: "text-state-synthetic",
      // The demo pulse breathes at the ambient cadence (frozen under
      // prefers-reduced-motion; the dashed ring + label still carry the state).
      animate: "animate-demo-pulse",
    },
    operator: {
      glyph: "◇",
      colorVar: "var(--syn-ink-subtle)",
      border: "border-solid",
      text: "text-ink-muted",
      animate: "",
    },
  }[initiator];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5",
        "text-2xs font-medium uppercase tracking-wide",
        variant.border,
        variant.text,
        variant.animate,
        className,
      )}
      style={{ borderColor: variant.colorVar }}
      role="img"
      aria-label={t(`initiator.${initiator}.aria`, {
        defaultValue: t("synthetic.aria"),
      })}
      title={t(`initiator.${initiator}.title`, {
        defaultValue: t("synthetic.title"),
      })}
    >
      <span aria-hidden>{variant.glyph}</span>
      {t(`initiator.${initiator}.label`, { defaultValue: t("synthetic.label") })}
    </span>
  );
}
