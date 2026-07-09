import {
  ConfidenceChip,
  PageHeader,
  SyntheticBadge,
  TierBadge,
  UniversalStateRow,
} from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useUniversalState } from "@hooks/use-universal-state";
import { AUDIT_EXPORT_FIELDS, toAuditExportRow } from "@lib/audit-export";
import { fmt } from "@lib/formatters";
import { ROW_OVERSCAN } from "@lib/virtual-window";
import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/** Estimated audit row height (px) for the virtualizer; measured precisely at
 *  runtime via `measureElement`, so this is only the pre-measure estimate. */
const AUDIT_ROW_HEIGHT = 30;

/**
 * Audit Vault — compliance-grade read-only view of audit_decisions joined
 * with audit_escalations (P3). Search by token-ref, filter by city /
 * escalated / tier. CSV export (FE-INV-027 — no PII).
 *
 * The row list is virtualized with `@tanstack/react-virtual` (design "H",
 * Req 9): the query no longer caps at 200 rows so the full seeded set is
 * reachable by scrolling (Req 9.3), and only a bounded window of row nodes is
 * mounted regardless of how many rows load (Req 9.1). Spacer rows preserve the
 * native `<table>` column alignment and the sticky header.
 */
export function AuditVault() {
  const { t } = useTranslation("common");
  const api = useSynapseApi();
  const city = useCityStore((s) => s.city);
  const [search, setSearch] = useState("");

  const audit = useQuery({
    queryKey: ["audit-vault", { city }],
    // No `limit` — the full seeded row set must be reachable by scrolling
    // (Req 9.3); virtualization keeps the mounted node count bounded (Req 9.1).
    queryFn: () => api.listRecentDecisions({ city }),
  });

  const rows = audit.data?.decisions ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q));
  }, [rows, search]);

  // Route the fetched dataset through the universal-state resolver so a failed
  // load, an offline session, and a degraded posture are each rendered
  // distinctly and "no audit rows yet" is never confused with "failed to load"
  // (Req 10.1, 10.7, 10.8). The search filter is applied *within* the populated
  // state, so a filter that matches nothing reads as a filter miss, not as an
  // empty dataset.
  const state = useUniversalState({
    isLoading: audit.isLoading,
    isError: audit.isError,
    itemCount: rows.length,
  });

  const scrollRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => AUDIT_ROW_HEIGHT,
    overscan: ROW_OVERSCAN,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();
  const paddingTop = virtualRows[0]?.start ?? 0;
  const lastVirtualRow = virtualRows[virtualRows.length - 1];
  const paddingBottom = lastVirtualRow ? rowVirtualizer.getTotalSize() - lastVirtualRow.end : 0;

  function exportCsv() {
    // FE-INV-027 / Req 11.5 — the export carries exactly the decision-safe field
    // set (via `toAuditExportRow`); no operator token ref, username, or override
    // reason can leak because the pure projection reads only those seven fields.
    const rows = filtered.map(toAuditExportRow);
    const cell = (field: (typeof AUDIT_EXPORT_FIELDS)[number], value: unknown) => {
      const text = field === "confidence" ? Number(value).toFixed(4) : String(value);
      return `"${text.replace(/"/g, '""')}"`;
    };
    const lines = [
      AUDIT_EXPORT_FIELDS.join(","),
      ...rows.map((r) => AUDIT_EXPORT_FIELDS.map((field) => cell(field, r[field])).join(",")),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `synapse-audit-${city}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="space-y-4">
      <PageHeader
        title="Audit Vault"
        subtitle="Append-only decision provenance (I-4). Operator identity is rendered by Vault-token reference only (FE-INV-019). Export contains zero PII."
        actions={
          <>
            <input
              type="search"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-64 rounded-md border border-border bg-surface px-3 text-sm text-ink placeholder:text-ink-subtle focus-visible:shadow-focus focus-visible:outline-none"
            />
            <button
              type="button"
              onClick={exportCsv}
              className="h-9 rounded-md border border-border bg-surface-raised px-3 text-sm font-medium text-ink hover:bg-surface focus-visible:outline-none focus-visible:shadow-focus"
            >
              Export CSV
            </button>
          </>
        }
      />

      <div ref={scrollRef} className="syn-card max-h-[70vh] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface-raised text-2xs uppercase tracking-wide text-ink-muted shadow-[inset_0_-1px_0_rgb(var(--syn-border))]">
            <tr>
              <th className="px-3 py-1.5">Audit</th>
              <th className="px-3 py-1.5">Decision</th>
              <th className="px-3 py-1.5">Tier</th>
              <th className="px-3 py-1.5">Conf.</th>
              <th className="px-3 py-1.5">Esc.</th>
              <th className="px-3 py-1.5">City</th>
              <th className="px-3 py-1.5">When</th>
              <th className="px-3 py-1.5 sr-only">View</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {state !== "populated" ? (
              <UniversalStateRow
                state={state}
                colSpan={8}
                labels={{
                  emptyTitle: "No audit rows yet",
                  emptyDetail: "Decisions will appear here as the council records them.",
                  errorDetail:
                    "Could not load the audit log. This is a load failure, not an empty vault — retry.",
                }}
              />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-ink-muted">
                  No audit rows match.
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
                  const r = filtered[vr.index];
                  if (!r) return null;
                  return (
                    <tr
                      key={r.audit_id}
                      data-index={vr.index}
                      ref={rowVirtualizer.measureElement}
                      className="hover:bg-surface-raised/50"
                    >
                      <td className="px-3 py-1.5 font-mono text-2xs text-ink-muted">
                        {r.audit_id}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-2xs text-ink">
                        {fmt.shortId(r.decision_id)}
                      </td>
                      <td className="px-3 py-1.5">
                        <TierBadge tier={r.tier} />
                      </td>
                      <td className="px-3 py-1.5">
                        <ConfidenceChip value={r.confidence} />
                      </td>
                      <td className="px-3 py-1.5">
                        <span className="inline-flex items-center gap-1">
                          {r.escalated ? (
                            <Badge tone="warning">esc.</Badge>
                          ) : (
                            <Badge tone="neutral">auto</Badge>
                          )}
                          {r.degraded && (
                            <span
                              className="text-state-degraded"
                              role="img"
                              aria-label={t("provenance.degraded")}
                              title={t("provenance.degraded")}
                            >
                              ▲
                            </span>
                          )}
                          {r.is_synthetic && <SyntheticBadge />}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-2xs text-ink-muted">{r.city ?? city}</td>
                      <td className="px-3 py-1.5 text-2xs text-ink-muted">
                        {fmt.relativeTime(r.created_at ?? new Date().toISOString())}
                      </td>
                      <td className="px-3 py-1.5 text-right">
                        <Link
                          to={`/decisions/${r.decision_id}`}
                          className="text-2xs font-medium text-accent hover:underline"
                        >
                          Open →
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
