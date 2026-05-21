/**
 * SYNAPSE Atlas Console — Badge primitive.
 *
 * Tier badges (1-4) and safety badges (ok / warn / alert / critical).
 * Tier 4 + safety-critical hit AAA contrast — see tokens.css.
 */
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "./cn";

export const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-ops-xs font-medium leading-none",
  {
    variants: {
      variant: {
        muted: "border-border bg-muted text-muted-fg",
        outline: "border-border bg-bg text-fg",
        tier1: "border-tier-1/40 bg-tier-1/10 text-tier-1",
        tier2: "border-tier-2/40 bg-tier-2/10 text-tier-2",
        tier3: "border-tier-3/40 bg-tier-3/10 text-tier-3",
        tier4: "border-tier-4/60 bg-tier-4/15 text-tier-4",
        ok: "border-safety-ok/50 bg-safety-ok/10 text-safety-ok",
        warn: "border-safety-warn/50 bg-safety-warn/10 text-safety-warn",
        alert: "border-safety-alert/50 bg-safety-alert/10 text-safety-alert",
        critical: "border-safety-critical/60 bg-safety-critical/15 text-safety-critical",
      },
    },
    defaultVariants: { variant: "muted" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />
  ),
);
Badge.displayName = "Badge";

const TIER_VARIANT = {
  tier_1: "tier1",
  tier_2: "tier2",
  tier_3: "tier3",
  tier_4: "tier4",
} as const;

export type TierKey = keyof typeof TIER_VARIANT;

/** Helper that maps an I-8 tier string to the right badge variant. */
export function tierBadgeVariant(tier: TierKey): "tier1" | "tier2" | "tier3" | "tier4" {
  return TIER_VARIANT[tier];
}
