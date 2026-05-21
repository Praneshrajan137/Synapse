import { cn } from "@/ui/lib/cn";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { forwardRef } from "react";

/**
 * Tooltip — built on Radix for correct focus, hover-intent and a11y.
 *
 * Wrap the app once in <TooltipProvider>. Most call sites use the
 * convenience <Tooltip> which composes Root + Trigger + Content.
 */

export const TooltipProvider = TooltipPrimitive.Provider;

export const TooltipContent = forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-overlay max-w-64 rounded-md border border-line-strong bg-membrane",
        "px-2.5 py-1.5 text-2xs text-ink-primary shadow-overlay",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: TooltipPrimitive.TooltipContentProps["side"];
  delayDuration?: number;
}

/** Convenience composition for the common single-trigger case. */
export function Tooltip({
  content,
  children,
  side = "bottom",
  delayDuration = 300,
}: TooltipProps) {
  return (
    <TooltipPrimitive.Root delayDuration={delayDuration}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipContent side={side}>{content}</TooltipContent>
    </TooltipPrimitive.Root>
  );
}
