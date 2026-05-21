import { cn } from "@/ui/lib/cn";
import { type VariantProps, cva } from "class-variance-authority";
import { forwardRef } from "react";

/**
 * Badge — a compact status token.
 *
 * Status is never encoded by color alone (a11y law + plan tenet): every
 * badge pairs its hue with a text label, and consumers that need a
 * shape distinction should pass a leading icon via `children`.
 */
const badgeVariants = cva(
  [
    "inline-flex items-center gap-1.5 whitespace-nowrap",
    "rounded-sm border px-1.5 py-0.5",
    "font-mono text-2xs font-medium uppercase tracking-wide",
  ],
  {
    variants: {
      tone: {
        neutral: "border-line-strong bg-membrane text-ink-secondary",
        live: "border-sig-live/40 bg-sig-live/12 text-sig-live",
        think: "border-sig-think/40 bg-sig-think/12 text-sig-think",
        warn: "border-sig-warn/40 bg-sig-warn/12 text-sig-warn",
        stop: "border-sig-stop/40 bg-sig-stop/12 text-sig-stop",
        ok: "border-sig-ok/40 bg-sig-ok/12 text-sig-ok",
        trace: "border-sig-trace/40 bg-sig-trace/12 text-sig-trace",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Show a leading status dot. Off by default — prefer an icon child. */
  dot?: boolean;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, tone, dot = false, children, ...props }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ tone }), className)} {...props}>
      {dot && <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  ),
);
Badge.displayName = "Badge";

export { badgeVariants };
