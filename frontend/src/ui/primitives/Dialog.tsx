import { cn } from "@/ui/lib/cn";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { forwardRef } from "react";

/**
 * Dialog — modal surface built on Radix (focus trap, scroll lock,
 * Escape-to-close, correct ARIA all handled).
 */

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const DialogContent = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    /** Hide the default close button (e.g. for forced-decision modals). */
    hideClose?: boolean;
  }
>(({ className, children, hideClose = false, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-overlay bg-void/70 backdrop-blur-sm" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-overlay w-full max-w-lg -translate-x-1/2 -translate-y-1/2",
        "rounded-lg border border-line-strong bg-elevated shadow-overlay",
        "focus-visible:outline-none",
        className,
      )}
      {...props}
    >
      {children}
      {!hideClose && (
        <DialogPrimitive.Close
          className={cn(
            "absolute right-3 top-3 inline-flex size-7 items-center justify-center",
            "rounded-sm text-ink-hint transition-colors hover:bg-membrane hover:text-ink-primary",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sig-live",
          )}
        >
          <X size={15} aria-hidden="true" />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = "DialogContent";

export function DialogHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex flex-col gap-1 px-5 pt-5 pb-3", className)} {...props} />
  );
}

export const DialogTitle = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("font-display text-base font-semibold text-ink-primary", className)}
    {...props}
  />
));
DialogTitle.displayName = "DialogTitle";

export const DialogDescription = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-xs text-ink-secondary", className)}
    {...props}
  />
));
DialogDescription.displayName = "DialogDescription";

export function DialogBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-3", className)} {...props} />;
}

export function DialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center justify-end gap-2 px-5 pt-3 pb-5", className)}
      {...props}
    />
  );
}
