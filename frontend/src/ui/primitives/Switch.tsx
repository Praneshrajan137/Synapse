import { cn } from "@/ui/lib/cn";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { forwardRef } from "react";

/**
 * Switch — a binary toggle (Radix). Used for sound, density, demo mode.
 */
export const Switch = forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center",
      "rounded-full border border-line-strong transition-colors",
      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
      "disabled:cursor-not-allowed disabled:opacity-40",
      "data-[state=unchecked]:bg-membrane data-[state=checked]:bg-sig-live/30",
      "data-[state=checked]:border-sig-live/60",
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        "pointer-events-none block size-3.5 rounded-full bg-ink-secondary transition-transform",
        "data-[state=checked]:translate-x-4 data-[state=checked]:bg-sig-live",
        "data-[state=unchecked]:translate-x-0.5",
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = "Switch";
