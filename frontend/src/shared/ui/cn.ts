import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge classnames idempotently while resolving Tailwind conflicts.
 * Used by every shadcn/ui primitive copied into src/shared/ui/.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
