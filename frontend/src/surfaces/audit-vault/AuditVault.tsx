import { ConfidenceChip, PageHeader, SyntheticBadge, TierBadge } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { fmt } from "@lib/formatters";
import { useCityStore } from "@state/city.store";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/**
 * Audit Vault — compliance-grade read-only view of audit_decisions joined
 * with audit_escalations (P3). Search by token-ref, filter by city /
 * escalated / tier. CSV export (FE-INV-027 — no PII).
 */
export function AuditVault() {
  const { t } = useTranslation("common");
  const api = useSynapseApi();
  const city = useCityStore((s) => s.city);
  const [search, setSearch] = useState("");

  const audit = useQuery({
    queryKey: ["audit-vault", { city }],
    queryFn: () => api.listRecentDecisions({ limit: 200, city }),
  });

  const rows = audit.data?.decisions ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q));
  }, [rows, search]);

  function exportCsv() {
    const header = [
      "audit_id",
      "decision_id",
      "city",
      "tier",
      "phase_reached",
      "confidence",
      "escalated",
      "degraded",
      "is_synthetic",
      "created_at",
    ];
    const lines = [
      header.join(","),
      ...filtered.map((r) =>
        [
          r.audit_id,
          r.decision_id,
          r.city ?? "",
          r.tier,
          r.phase_reached,
          r.confidence.toFixed(4),
          r.escalated ? "true" : "false",
          r.degraded ? "true" : "false",
          r.is_synthetic ? "true" : "false",
          r.created_at ?? "",
        ]
          .map((v) => `"${String(v).replace(/"/g, '""')}"`)
          .join(","),
      ),
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

      <div className="syn-card max-h-[70vh] overflow-auto">
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
            {audit.isLoading && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-ink-muted">
                  Loading…
                </td>
              </tr>
            )}
            {!audit.isLoading && filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-ink-muted">
                  No audit rows match.
                </td>
              </tr>
            )}
            {filtered.map((r) => (
              <tr key={r.audit_id} className="hover:bg-surface-raised/50">
                <td className="px-3 py-1.5 font-mono text-2xs text-ink-muted">{r.audit_id}</td>
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
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
