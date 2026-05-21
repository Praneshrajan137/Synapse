/**
 * SYNAPSE Atlas Console — Audit Vault filter rail.
 *
 * Bound to TanStack Router search-params.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@shared/ui/badge";

import type { AuditSearch } from "../model/filters";
import { OVERRIDE_CODES } from "../model/override-codes";

const TIERS = ["tier_1", "tier_2", "tier_3", "tier_4"] as const;

export interface AuditFiltersProps {
  readonly search: AuditSearch;
  readonly onChange: (next: Partial<AuditSearch>) => void;
  readonly resultCount: number;
}

export const AuditFilters = memo(function AuditFilters({
  search,
  onChange,
  resultCount,
}: AuditFiltersProps) {
  const { t } = useTranslation();
  return (
    <div role="search" aria-label={t("auditVault.title")} className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col text-ops-xs uppercase tracking-wide text-muted-fg">
        Tier
        <select
          value={search.tier ?? ""}
          onChange={(e) =>
            onChange({ tier: (e.target.value || undefined) as AuditSearch["tier"] })
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
        Override code
        <select
          value={search.override_code ?? ""}
          onChange={(e) =>
            onChange({ override_code: (e.target.value || undefined) as AuditSearch["override_code"] })
          }
          className="mt-1 rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">—</option>
          {OVERRIDE_CODES.filter((c) => !c.deprecated).map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col text-ops-xs uppercase tracking-wide text-muted-fg">
        User
        <input
          type="text"
          value={search.user ?? ""}
          onChange={(e) => onChange({ user: e.target.value || undefined })}
          className="mt-1 w-44 rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>

      <label className="flex flex-col text-ops-xs uppercase tracking-wide text-muted-fg">
        Since
        <input
          type="datetime-local"
          value={search.since ? search.since.slice(0, 16) : ""}
          onChange={(e) =>
            onChange({ since: e.target.value ? `${e.target.value}:00Z` : undefined })
          }
          className="mt-1 rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>

      <span className="ml-auto inline-flex items-center gap-2">
        <Badge variant="muted" aria-live="polite">
          {resultCount} rows
        </Badge>
      </span>
    </div>
  );
});
