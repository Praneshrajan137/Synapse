import { cn } from "@/ui/lib/cn";
import { forwardRef, useId } from "react";

/**
 * Input — single-line text entry.
 *
 * Always pass `label`. When no visible label is wanted, pass `label` for
 * the accessible name and `hideLabel` to clip it visually.
 */
export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  hideLabel?: boolean;
  hint?: string;
  invalid?: boolean;
  /** Optional leading adornment, e.g. a search icon. */
  leading?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    { className, label, hideLabel = false, hint, invalid = false, leading, id, ...props },
    ref,
  ) => {
    const autoId = useId();
    const inputId = id ?? autoId;
    const hintId = hint ? `${inputId}-hint` : undefined;

    return (
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={inputId}
          className={cn(
            "font-display text-2xs font-semibold uppercase tracking-[0.12em] text-ink-secondary",
            hideLabel && "sr-only",
          )}
        >
          {label}
        </label>
        <div className="relative flex items-center">
          {leading && (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute left-2.5 text-ink-hint"
            >
              {leading}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            aria-invalid={invalid || undefined}
            aria-describedby={hintId}
            className={cn(
              "h-9 w-full rounded-md border bg-void px-3 text-xs text-ink-primary",
              "placeholder:text-ink-hint",
              "transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
              leading && "pl-8",
              invalid ? "border-sig-stop/60" : "border-line-strong hover:border-ink-hint",
              className,
            )}
            {...props}
          />
        </div>
        {hint && (
          <p
            id={hintId}
            className={cn("text-2xs", invalid ? "text-sig-stop" : "text-ink-hint")}
          >
            {hint}
          </p>
        )}
      </div>
    );
  },
);
Input.displayName = "Input";
