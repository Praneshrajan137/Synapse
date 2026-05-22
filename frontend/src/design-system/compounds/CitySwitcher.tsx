import type { City } from "@domain/primitives";
import { cn } from "@lib/cn";
import { useCityStore } from "@state/city.store";

const OPTIONS: ReadonlyArray<{ value: City; label: string }> = [
  { value: "bengaluru", label: "Bengaluru" },
  { value: "mumbai", label: "Mumbai" },
];

/**
 * Bengaluru ↔ Mumbai segmented control. Persists to localStorage and threads
 * through every WS handshake / API call via the city store.
 */
export function CitySwitcher() {
  const city = useCityStore((s) => s.city);
  const setCity = useCityStore((s) => s.setCity);

  return (
    <div
      role="radiogroup"
      aria-label="Active city"
      className="inline-flex items-center rounded-md bg-surface-raised p-0.5"
    >
      {OPTIONS.map((opt) => {
        const active = opt.value === city;
        return (
          <button
            key={opt.value}
            // biome-ignore lint/a11y/useSemanticElements: styled segmented control — the radiogroup/radio ARIA pattern is intentional
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setCity(opt.value)}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium transition-colors duration-fast ease-standard",
              "focus-visible:outline-none focus-visible:shadow-focus",
              active ? "bg-accent text-ink-inverse" : "text-ink-muted hover:text-ink",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
