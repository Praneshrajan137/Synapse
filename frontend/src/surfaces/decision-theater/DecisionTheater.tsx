import {
  ConfidenceChip,
  InitiatorBadge,
  PageHeader,
  TierBadge,
  UniversalStateRow,
} from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useUniversalState } from "@hooks/use-universal-state";
import { fmt } from "@lib/formatters";
import { ROW_OVERSCAN } from "@lib/virtual-window";
import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { DecisionFilters, type DecisionFiltersState } from "./DecisionFilters";

const INITIAL: DecisionFiltersState = { tier: null, city: null, escalatedOnly: false };

/** Estimated decision row height (px) for the virtualizer; measured precisely
 *  at runtime via `measureElement`. */
const DECISION_ROW_HEIGHT = 34;

/**
 * Decision Theater — P3 elevation with server-side filters + drill-down.
 *
 * The row list is virtualized with `@tanstack/react-virtual` (design "H",
 * Req 9): the query no longer caps at 100 rows so the full seeded set is
 * reachable by scrolling (Req 9.3), and only a bounded window of row nodes is
 * mounted regardless of dataset size (Req 9.1). Spacer rows keep the native
 * `<table>` column alignment intact.
 */
export function DecisionTheater() {
  const api = useSynapseApi();
  const city = useCityStore((s) => s.city);
  const [filters, setFilters] = useState<DecisionFiltersState>(INITIAL);
  const [search, setSearch] = useState("");

  const decisions = useQuery({
    queryKey: ["decisions", "recent", { ...filters, city }],
    // No `limit` — the full seeded row set must be reachable by scrolling
    // (Req 9.3); virtualization keeps the mounted node count bounded (Req 9.1).
    queryFn: () =>
      api.listRecentDecisions({
        city,
        ...(filters.tier ? { tier: filters.tier } : {}),
        ...(filters.escalatedOnly ? { escalated: true } : {}),
      }),
  });

  const rows = decisions.data?.decisions ?? [];
  const filtered = useMemo(
    () =>
      search
        ? rows.filter((r) => JSON.stringify(r).toLowerCase().includes(search.toLowerCase()))
        : rows,
    [rows, search],
  );

  // Distinct rendering for loading/empty/error/degraded/offline (Req 10.1);
  // "no decisions yet" (empty) stays distinct from "failed to load" (error)
  // per Req 10.8. The search box filters within the populated dataset.
  const state = useUniversalState({
    isLoading: decisions.isLoading,
    isError: decisions.isError,
    itemCount: rows.length,
  });

  const scrollRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => DECISION_ROW_HEIGHT,
    overscan: ROW_OVERSCAN,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualRows[0]?.start ?? 0;
  const lastVirtualRow = virtualRows[virtualRows.length - 1];
  const paddingBottom = lastVirtualRow ? rowVirtualizer.getTotalSize() - lastVirtualRow.end : 0;

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

      <div ref={scrollRef} className="syn-card max-h-[70vh] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface-raised text-2xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Decision</th>
              <th className="px-3 py-2">Origin</th>
              <th className="px-3 py-2">Tier</th>
              <th className="px-3 py-2">Phase</th>
              <th className="px-3 py-2">Confidence</th>
              <th className="px-3 py-2">Escalated</th>
              <th className="px-3 py-2 sr-only">Replay</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {state !== "populated" ? (
              <UniversalStateRow
                state={state}
                colSpan={8}
                labels={{
                  emptyTitle: "No decisions yet",
                  emptyDetail: "Recorded decisions will appear here as the council acts.",
                  errorDetail:
                    "Could not load decisions. This is a load failure, not an empty result — retry.",
                }}
              />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-ink-muted">
                  No decisions match the current filters.
                </td>
              </tr>
            ) : (
              <>
                {paddingTop > 0 && (
                  <tr>
                    <td colSpan={8} style={{ height: paddingTop, padding: 0, border: 0 }} />
                  </tr>
                )}
                {virtualRows.map((vr) => {
                  const row = filtered[vr.index];
                  if (!row) return null;
                  return (
                    <tr
                      key={row.audit_id}
                      data-index={vr.index}
                      ref={rowVirtualizer.measureElement}
                      className="hover:bg-surface-raised/50"
                    >
                      <td className="px-3 py-2 font-mono text-2xs tabular-nums text-ink-muted">
                        {fmt.relativeTime(row.created_at ?? new Date().toISOString())}
                      </td>
                      <td className="px-3 py-2 font-mono text-2xs text-ink">
                        {fmt.shortId(row.decision_id)}
                      </td>
                      <td className="px-3 py-2">
                        <InitiatorBadge initiator={row.initiator ?? "operator"} />
                      </td>
                      <td className="px-3 py-2">
                        <TierBadge tier={row.tier} />
                      </td>
                      <td className="px-3 py-2 tabular-nums text-ink-muted">
                        {row.phase_reached}/5
                      </td>
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
                  );
                })}
                {paddingBottom > 0 && (
                  <tr>
                    <td colSpan={8} style={{ height: paddingBottom, padding: 0, border: 0 }} />
                  </tr>
                )}
              </>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
