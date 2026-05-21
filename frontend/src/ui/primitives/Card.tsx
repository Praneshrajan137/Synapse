import { cn } from "@/ui/lib/cn";
import { forwardRef } from "react";

/**
 * Card — the panel primitive. Every surface is composed of cards.
 *
 * `tone` shifts the canvas layer; `accent` adds a left signal rule used
 * to mark agent-owned or status-bearing panels (e.g. an agent's color in
 * the Theater, or `--sig-think` for an LLM reasoning panel).
 */

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: "paper" | "elevated" | "membrane";
  /** A CSS color for the 2px left rule, or undefined for none. */
  accent?: string;
  interactive?: boolean;
}

const toneClass = {
  paper: "bg-paper",
  elevated: "bg-elevated",
  membrane: "bg-membrane",
} as const;

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    { className, tone = "elevated", accent, interactive = false, style, ...props },
    ref,
  ) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-line-faint",
        toneClass[tone],
        interactive &&
          "transition-colors hover:border-line-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
        className,
      )}
      style={accent ? { ...style, borderLeft: `2px solid ${accent}` } : style}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center justify-between gap-3 px-4 pt-3.5 pb-2", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "font-display text-2xs font-semibold uppercase tracking-[0.12em] text-ink-secondary",
      className,
    )}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

export const CardBody = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-4 pb-4", className)} {...props} />
  ),
);
CardBody.displayName = "CardBody";
