import { cn } from "@/ui/lib/cn";
import { Slot } from "@radix-ui/react-slot";
import { type VariantProps, cva } from "class-variance-authority";
import { forwardRef } from "react";

/**
 * Button — the primary action primitive.
 *
 * Variants are semantic, not decorative: `danger` is reserved for
 * destructive or escalation-confirming actions, `signal` for the single
 * highest-intent action on a surface. Use `asChild` to render as a link
 * while keeping button styling.
 */
const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "font-medium select-none",
    "rounded-md border transition-colors",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
    "disabled:pointer-events-none disabled:opacity-40",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-elevated border-line-strong text-ink-primary hover:bg-membrane hover:border-ink-hint",
        secondary:
          "bg-transparent border-line-strong text-ink-secondary hover:text-ink-primary hover:border-ink-hint",
        ghost:
          "bg-transparent border-transparent text-ink-secondary hover:bg-elevated hover:text-ink-primary",
        signal:
          "bg-sig-live/12 border-sig-live/40 text-sig-live hover:bg-sig-live/20 hover:border-sig-live/70",
        danger:
          "bg-sig-stop/12 border-sig-stop/40 text-sig-stop hover:bg-sig-stop/20 hover:border-sig-stop/70",
      },
      size: {
        sm: "h-7 px-2.5 text-2xs",
        md: "h-9 px-3.5 text-xs",
        lg: "h-11 px-5 text-sm",
        icon: "h-9 w-9 p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the single child element instead of a <button>. */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        type={asChild ? undefined : (type ?? "button")}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";

export { buttonVariants };
