import { ConfidenceChip, PageHeader, TierBadge } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { fmt } from "@lib/formatters";
import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { DecisionFilters, type DecisionFiltersState } from "./DecisionFilters";

const INITIAL: DecisionFiltersState = { tier: null, city: null, escalatedOnly: false };

/** Decision Theater — P3 elevation with server-side filters + drill-down. */
export function DecisionTheater() {
  const api = useSynapseApi();
  const city = useCityStore((s) => s.city);
  const [filters, setFilters] = useState<DecisionFiltersState>(INITIAL);
  const [search, setSearch] = useState("");

  const decisions = useQuery({
    queryKey: ["decisions", "recent", { ...filters, city }],
    queryFn: () =>
      api.listRecentDecisions({
        limit: 100,
        city,
        ...(filters.tier ? { tier: filters.tier } : {}),
        ...(filters.escalatedOnly ? { escalated: true } : {}),
      }),
  });

  const rows = decisions.data?.decisions ?? [];
  const filtered = search
    ? rows.filter((r) => JSON.stringify(r).toLowerCase().includes(search.toLowerCase()))
    : rows;

  return (
    <section className="space-y-4">
      <PageHeader
        title="Decision Theater"
        subtitle="Audit-anchored history with server-side filtering. Click a row to replay the 5-phase consensus."
        actions={
          <input
            type="search"
            placeholder="Search decisions…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-72 rounded-md border border-border bg-surface px-3 text-sm text-ink placeholder:text-ink-subtle focus-visible:shadow-focus focus-visible:outline-none"
          />
        }
      />

      <DecisionFilters value={filters} onChange={setFilters} />

      <div className="syn-card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-raised text-2xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Decision</th>
              <th className="px-3 py-2">Tier</th>
              <th className="px-3 py-2">Phase</th>
              <th className="px-3 py-2">Confidence</th>
              <th className="px-3 py-2">Escalated</th>
              <th className="px-3 py-2 sr-only">Replay</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {decisions.isLoading && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-ink-muted">
                  Loading…
                </td>
              </tr>
            )}
            {decisions.isError && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-confidence-risk">
                  Failed to load: {(decisions.error as Error).message}
                </td>
              </tr>
            )}
            {!decisions.isLoading && filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-ink-muted">
                  No decisions match the current filters.
                </td>
              </tr>
            )}
            {filtered.map((row) => (
              <tr key={row.audit_id} className="hover:bg-surface-raised/50">
                <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink-muted">
                  {fmt.relativeTime(row.created_at ?? new Date().toISOString())}
                </td>
                <td className="px-3 py-2 font-mono text-2xs text-ink">
                  {fmt.shortId(row.decision_id)}
                </td>
                <td className="px-3 py-2">
                  <TierBadge tier={row.tier} />
                </td>
                <td className="px-3 py-2 tabular-nums text-ink-muted">{row.phase_reached}/5</td>
                <td className="px-3 py-2">
                  <ConfidenceChip value={row.confidence} />
                </td>
                <td className="px-3 py-2">
                  {row.escalated ? (
                    <Badge tone="warning">Escalated</Badge>
                  ) : (
                    <Badge tone="neutral">Auto</Badge>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  <Link
                    to={`/decisions/${row.decision_id}`}
                    className="text-2xs font-medium text-accent hover:underline"
                  >
                    Replay →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
