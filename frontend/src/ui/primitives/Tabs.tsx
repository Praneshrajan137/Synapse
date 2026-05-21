import { cn } from "@/ui/lib/cn";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { forwardRef } from "react";

/**
 * Tabs — built on Radix (roving focus, arrow-key nav, correct ARIA).
 */
export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex items-center gap-1 border-b border-line-faint", className)}
    {...props}
  />
));
TabsList.displayName = "TabsList";

export const TabsTrigger = forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative -mb-px px-3 py-2 text-xs font-medium transition-colors",
      "text-ink-hint hover:text-ink-secondary",
      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
      "data-[state=active]:text-ink-primary",
      "data-[state=active]:after:absolute data-[state=active]:after:inset-x-0",
      "data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5",
      "data-[state=active]:after:bg-sig-live data-[state=active]:after:content-['']",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "pt-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
      className,
    )}
    {...props}
  />
));
TabsContent.displayName = "TabsContent";
