import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@lib/cn";

const button = cva(
  [
    "inline-flex items-center justify-center gap-2 select-none",
    "font-medium whitespace-nowrap rounded-md",
    "transition-colors duration-fast ease-standard",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "focus-visible:outline-none focus-visible:shadow-focus",
  ],
  {
    variants: {
      variant: {
        primary: "bg-accent text-ink-inverse hover:opacity-90",
        secondary: "bg-surface-raised text-ink hover:bg-surface",
        success: "bg-signal-success text-ink-inverse hover:opacity-90",
        danger: "bg-signal-danger text-ink-inverse hover:opacity-90",
        warning: "bg-signal-warning text-ink-inverse hover:opacity-90",
        ghost: "bg-transparent text-ink hover:bg-surface-raised",
        outline:
          "bg-transparent border border-border text-ink hover:border-border-strong",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button ref={ref} type={type} className={cn(button({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
