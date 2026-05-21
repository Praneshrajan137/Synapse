/**
 * SYNAPSE Atlas Console — Decision Trace route (S3 deep work).
 *
 * Plan §5.3:
 *   - Faceted search bound to TanStack Router search-params.
 *   - Virtualised infinite-scroll table over /api/v1/decisions/recent.
 *   - Drawer with 5-phase Visx timeline, chain proof, debate rounds,
 *     Pareto front, deterministic JSON export.
 *   - Replay scrubber over the loaded window.
 */
import { createFileRoute, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { DecisionsFilters } from "./components/decisions-filters";
import { DecisionsTable } from "./components/decisions-table";
import { DecisionDrawer } from "./components/decision-drawer";
import { Scrubber, type ReplaySpeed } from "./components/scrubber";
import { useDecisions } from "./hooks/use-decisions";
import {
  type DecisionsSearch,
  DecisionsSearchSchema,
  type RecentDecisionRow,
} from "./model/decision";

export const Route = createFileRoute("/$city/decisions/")({
  validateSearch: (search) => DecisionsSearchSchema.parse(search),
  component: DecisionTrace,
});

function DecisionTrace() {
  const { t } = useTranslation();
  const { city } = useParams({ from: "/$city/decisions/" });
  const search = useSearch({ from: "/$city/decisions/" });
  const navigate = useNavigate({ from: "/$city/decisions/" });

  function update(next: Partial<DecisionsSearch>): void {
    void navigate({
      search: (prev) => ({ ...prev, ...next }),
      replace: true,
    });
  }

  const { rows, hasNextPage, isFetching, fetchNextPage } = useDecisions({
    cityId: city,
    tier: search.tier,
    escalated: search.escalated,
  });

  const filtered = useMemo(() => clientFilter(rows, search), [rows, search]);

  // Bound the scrubber to the loaded window.
  const minTs = filtered.length > 0
    ? Date.parse(filtered[filtered.length - 1]!.created_at)
    : 0;
  const maxTs = filtered.length > 0 ? Date.parse(filtered[0]!.created_at) : 0;
  const scrubPosition = search.scrub ?? maxTs;
  const speed: ReplaySpeed = 1;

  function openRow(decisionId: string): void {
    update({ open: decisionId });
  }
  function closeDrawer(): void {
    update({ open: undefined });
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-3 lg:h-[calc(100vh-5rem)]">
      <header className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-ops-xl font-bold tracking-tight">
          {t("decisionTrace.title")}
        </h1>
        <span className="text-ops-sm text-muted-fg">{t(`city.${city}`)}</span>
      </header>

      <DecisionsFilters
        search={search}
        onChange={update}
        resultCount={filtered.length}
      />

      <Scrubber
        position={scrubPosition || Date.now()}
        min={minTs || Date.now() - 60 * 60 * 1000}
        max={maxTs || Date.now()}
        speed={speed}
        onPosition={(p) => update({ scrub: p })}
        onSpeed={() => {
          /* speed wires to the replay engine in S5 */
        }}
      />

      <div className="grid flex-1 grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(0,1fr)_minmax(360px,1fr)]">
        <DecisionsTable
          rows={filtered}
          hasNextPage={hasNextPage}
          isFetching={isFetching}
          onLoadMore={fetchNextPage}
          onRowOpen={openRow}
          openId={search.open ?? null}
        />
        <DecisionDrawer decisionId={search.open ?? null} onClose={closeDrawer} />
      </div>
    </div>
  );
}

function clientFilter(
  rows: readonly RecentDecisionRow[],
  search: DecisionsSearch,
): readonly RecentDecisionRow[] {
  if (!search.q && !search.since && !search.until) return rows;
  const since = search.since ? Date.parse(search.since) : -Infinity;
  const until = search.until ? Date.parse(search.until) : Infinity;
  const needle = search.q?.toLowerCase();
  return rows.filter((r) => {
    const ts = Date.parse(r.created_at);
    if (ts < since || ts > until) return false;
    if (needle) {
      const hay = `${r.decision_id} ${r.audit_id} ${r.tier}`.toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  });
}
