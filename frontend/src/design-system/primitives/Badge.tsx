import { cn } from "@lib/cn";
import { type VariantProps, cva } from "class-variance-authority";
import { type HTMLAttributes, forwardRef } from "react";

const badge = cva(
  "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-2xs font-medium uppercase tracking-wide",
  {
    variants: {
      tone: {
        neutral: "bg-surface-raised text-ink-muted",
        info: "bg-signal-info/15 text-signal-info",
        success: "bg-signal-success/15 text-signal-success",
        warning: "bg-signal-warning/20 text-signal-warning",
        danger: "bg-signal-danger/15 text-signal-danger",
        tier1: "bg-tier-1/15 text-tier-1",
        tier2: "bg-tier-2/15 text-tier-2",
        tier3: "bg-tier-3/15 text-tier-3",
        tier4: "bg-tier-4/15 text-tier-4",
      },
    },
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
