import { cn } from "@/ui/lib/cn";

/**
 * Kbd — a keyboard-shortcut hint chip.
 *
 * The keyboard is the primary input for Synaptic Calm (plan tenet T-11),
 * so shortcut hints appear throughout the UI. Pass keys individually for
 * a chord: <Kbd keys={["⌘", "K"]} />.
 *
 * The wrapper carries role="img" with an accessible label, which
 * collapses the <kbd> subtree for assistive tech — a chord is announced
 * as one unit ("Command K"), not key-by-key.
 */
export interface KbdProps {
  keys: readonly string[];
  className?: string;
  /** Accessible label, e.g. "Command K". Defaults to the joined keys. */
  label?: string;
}

export function Kbd({ keys, className, label }: KbdProps) {
  return (
    <span
      role="img"
      aria-label={label ?? keys.join(" ")}
      className={cn("inline-flex items-center gap-0.5", className)}
    >
      {keys.map((key, index) => (
        <kbd
          // Keys in a chord are positional and static — index key is safe.
          // biome-ignore lint/suspicious/noArrayIndexKey: positional chord
          key={`${key}-${index}`}
          className={cn(
            "inline-flex h-5 min-w-5 items-center justify-center px-1",
            "rounded-xs border border-line-strong bg-membrane",
            "font-mono text-2xs text-ink-secondary",
          )}
        >
          {key}
        </kbd>
      ))}
    </span>
  );
}
