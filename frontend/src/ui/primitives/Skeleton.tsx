import { cn } from "@/ui/lib/cn";

/**
 * Skeleton — a loading placeholder.
 *
 * The shimmer is opacity-only so it degrades gracefully under
 * prefers-reduced-motion (the keyframe is defined in globals.css scope
 * via Tailwind's `animate-pulse`, itself a reduced-motion-safe fade).
 */
export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Shape preset. */
  shape?: "line" | "block" | "circle";
}

const shapeClass = {
  line: "h-3 rounded-xs",
  block: "h-full w-full rounded-md",
  circle: "aspect-square rounded-full",
} as const;

export function Skeleton({ className, shape = "line", ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse bg-membrane", shapeClass[shape], className)}
      {...props}
    />
  );
}
