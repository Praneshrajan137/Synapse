import { cn } from "@lib/cn";
import { type VariantProps, cva } from "class-variance-authority";
import { type HTMLAttributes, forwardRef } from "react";

/**
 * Each tone: a tint of its token under text drawn in an ink token.
 *
 * The tone's colour lives in the tint and its meaning in the words. No tone colour is legible
 * as text on its own tint in every theme and on every surface (finding 134), so each tinted
 * tone draws `text-ink`, and the neutral tone keeps `text-ink-muted` on the raised surface.
 * The tier tones keep the tier in the tint's lightness, ADR-025's orthogonal encoding.
 * `__tests__/Badge.contrast.test.tsx` computes every pairing from tokens.css.
 */
export const BADGE_TONE_CLASSES = {
  neutral: "bg-surface-raised text-ink-muted",
  info: "bg-signal-info/15 text-ink",
  success: "bg-signal-success/15 text-ink",
  warning: "bg-signal-warning/20 text-ink",
  danger: "bg-signal-danger/15 text-ink",
  tier1: "bg-tier-1/15 text-ink",
  tier2: "bg-tier-2/15 text-ink",
  tier3: "bg-tier-3/15 text-ink",
  tier4: "bg-tier-4/15 text-ink",
} as const;

const badge = cva(
  "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-2xs font-medium uppercase tracking-wide",
  {
    variants: { tone: BADGE_TONE_CLASSES },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badge> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, tone, ...props }, ref) => (
    <span ref={ref} className={cn(badge({ tone }), className)} {...props} />
  ),
);
Badge.displayName = "Badge";
