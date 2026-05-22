import type { City } from "@domain/primitives";
import { Badge } from "@ds/primitives";
import { cn } from "@lib/cn";
import type { Tier } from "@lib/confidence";

export interface DecisionFiltersState {
  readonly tier: Tier | null;
  readonly city: City | null;
  readonly escalatedOnly: boolean;
}

interface DecisionFiltersProps {
  readonly value: DecisionFiltersState;
  readonly onChange: (next: DecisionFiltersState) => void;
}

const TIERS: Array<{ id: Tier; label: string }> = [
  { id: "tier_1", label: "Tier 1" },
  { id: "tier_2", label: "Tier 2" },
  { id: "tier_3", label: "Tier 3" },
  { id: "tier_4", label: "Tier 4" },
];

export function DecisionFilters({ value, onChange }: DecisionFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="Decision filters">
      <span className="text-2xs uppercase tracking-wide text-ink-muted">Tier</span>
      {TIERS.map((t) => {
        const active = value.tier === t.id;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange({ ...value, tier: active ? null : t.id })}
            className={cn(
              "rounded px-2 py-0.5 text-2xs font-medium uppercase tracking-wide transition-colors duration-fast ease-standard",
              "focus-visible:outline-none focus-visible:shadow-focus",
              active
                ? "bg-accent text-ink-inverse"
                : "bg-surface-raised text-ink-muted hover:text-ink",
            )}
            aria-pressed={active}
          >
            {t.label}
          </button>
        );
      })}
      <span className="ml-2 text-2xs uppercase tracking-wide text-ink-muted">Esc.</span>
      <button
        type="button"
        onClick={() => onChange({ ...value, escalatedOnly: !value.escalatedOnly })}
        className={cn(
          "rounded px-2 py-0.5 text-2xs font-medium uppercase tracking-wide transition-colors duration-fast ease-standard",
          "focus-visible:outline-none focus-visible:shadow-focus",
          value.escalatedOnly
            ? "bg-confidence-warn text-ink-inverse"
            : "bg-surface-raised text-ink-muted hover:text-ink",
        )}
        aria-pressed={value.escalatedOnly}
      >
        Escalated only
      </button>
      {(value.tier || value.escalatedOnly) && (
        <Badge tone="info" className="ml-2">
          filtered
        </Badge>
      )}
    </div>
  );
}
