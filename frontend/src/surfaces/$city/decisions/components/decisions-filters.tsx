/**
 * SYNAPSE Atlas Console — Decision Trace facet filters.
 *
 * Bound directly to TanStack Router search-params. Every change becomes
 * a URL-shareable link a teammate can drop into Slack — exactly the
 * "stale query string" failure mode TanStack Router was chosen to
 * prevent (ADR-025 §Routing).
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@shared/ui/badge";

import type { DecisionsSearch, Tier } from "../model/decision";

const TIERS: readonly Tier[] = ["tier_1", "tier_2", "tier_3", "tier_4"];

export interface DecisionsFiltersProps {
  readonly search: DecisionsSearch;
  readonly onChange: (next: Partial<DecisionsSearch>) => void;
  readonly resultCount: number;
}

export const DecisionsFilters = memo(function DecisionsFilters({
  search,
  onChange,
  resultCount,
}: DecisionsFiltersProps) {
  const { t } = useTranslation();

  return (
    <div
      role="search"
      aria-label={t("decisionTrace.title")}
      className="flex flex-wrap items-end gap-3"
    >
      <label className="flex flex-col text-ops-xs uppercase tracking-wide text-muted-fg">
        {t("decisionTrace.filters.tier")}
        <select
          value={search.tier ?? ""}
          onChange={(e) =>
            onChange({ tier: (e.target.value || undefined) as Tier | undefined })
          }
          className="mt-1 rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">—</option>
          {TIERS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col text-ops-xs uppercase tracking-wide text-muted-fg">
        {t("decisionTrace.filters.agent")}
        <input
          type="text"
          value={search.agent ?? ""}
          onChange={(e) => onChange({ agent: e.target.value || undefined })}
          className="mt-1 w-44 rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>

      <label className="flex flex-col text-ops-xs uppercase tracking-wide text-muted-fg">
        {t("decisionTrace.filters.search")}
        <input
          type="search"
          value={search.q ?? ""}
          onChange={(e) => onChange({ q: e.target.value || undefined })}
          placeholder="justification, decision_id, …"
          className="mt-1 w-64 rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>

      <Toggle
        label={t("decisionTrace.filters.escalated")}
        checked={Boolean(search.escalated)}
        onChange={(v) => onChange({ escalated: v ? true : undefined })}
      />
      <Toggle
        label={t("decisionTrace.filters.override")}
        checked={Boolean(search.override)}
        onChange={(v) => onChange({ override: v ? true : undefined })}
      />

      <span className="ml-auto inline-flex items-center gap-2">
        <Badge variant="muted" aria-live="polite">
          {resultCount} rows
        </Badge>
      </span>
    </div>
  );
});

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-ops-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-border accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <span className="text-muted-fg">{label}</span>
    </label>
  );
}
