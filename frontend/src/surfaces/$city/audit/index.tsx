/**
 * SYNAPSE Atlas Console — Audit Vault route (S5 deep work).
 *
 * Plan §5.6:
 *   - Faceted filters (tier, override code, user, since/until).
 *   - Override history with controlled vocabulary.
 *   - Chain proof via the shared ChainProof primitive (S3).
 *   - PDF export gated on chain validity (deterministic body).
 *   - PII reveal gated on BFF reauth.
 *   - Data residency chip — DPDPA / I-11.
 */
import { createFileRoute, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@shared/ui/card";
import { ChainProof } from "@surfaces/$city/decisions/components/chain-proof";
import { useDecision } from "@surfaces/$city/decisions/hooks/use-decision";

import { AuditFilters } from "./components/audit-filters";
import { OverrideHistory, type OverrideRecord } from "./components/override-history";
import { PiiGate } from "./components/pii-gate";
import { useDecisions } from "@surfaces/$city/decisions/hooks/use-decisions";
import { useReauth } from "./hooks/use-reauth";
import { usePdfExport } from "./hooks/use-pdf-export";
import { type AuditSearch, AuditSearchSchema } from "./model/filters";
import type { AuditEntry } from "@surfaces/$city/decisions/model/audit-hash";

export const Route = createFileRoute("/$city/audit/")({
  validateSearch: (search) => AuditSearchSchema.parse(search),
  component: AuditVault,
});

function AuditVault() {
  const { t } = useTranslation();
  const { city } = useParams({ from: "/$city/audit/" });
  const search = useSearch({ from: "/$city/audit/" });
  const navigate = useNavigate({ from: "/$city/audit/" });

  const update = useCallback(
    (next: Partial<AuditSearch>) => {
      void navigate({ search: (prev) => ({ ...prev, ...next }), replace: true });
    },
    [navigate],
  );

  // Reuse the Decision Trace listing endpoint — Audit Vault is a different
  // lens over the same data (chain-of-custody first instead of operations
  // first).
  const { rows } = useDecisions({
    cityId: city,
    tier: search.tier,
    escalated: undefined,
    limit: 50,
  });

  // Reauth state for PII reveal.
  const { elevated, elevatedUntil, reauth, busy: reauthBusy, error: reauthError } = useReauth();
  const piiVisible = (search.pii ?? false) && elevated;
  const [reauthOpen, setReauthOpen] = useState(false);

  // Open-decision drill-in.
  const { decision } = useDecision(search.open ?? null);

  const exporter = usePdfExport();

  // S5 placeholder — real override-record join wires in S6 hardening once
  // the audit_consensus.human_override projection has shipped.
  const overrideRecords: OverrideRecord[] = [];

  const auditEntries: readonly AuditEntry[] | null = decision
    ? decision.audit_trace.map((e, i) => ({
        hash: String((e as { hash?: unknown }).hash ?? ""),
        prev: ((e as { prev?: unknown }).prev as string | null) ?? null,
        body: { ...decision, _entry_index: i },
        ts: (e as { ts?: string }).ts,
      }))
    : null;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-ops-xl font-bold tracking-tight">{t("auditVault.title")}</h1>
        <span className="text-ops-sm text-muted-fg">{t(`city.${city}`)}</span>
        <Badge variant="muted" className="ml-auto" aria-label={t("common.residencyChip")}>
          {t("common.residencyChip")}
        </Badge>
        <Button
          variant={piiVisible ? "primary" : "outline"}
          size="sm"
          onClick={() => {
            if (piiVisible) {
              update({ pii: undefined });
            } else if (elevated) {
              update({ pii: true });
            } else {
              setReauthOpen(true);
            }
          }}
        >
          {piiVisible ? t("auditVault.redactedNotice") : t("auditVault.showPii")}
        </Button>
      </header>

      <AuditFilters search={search} onChange={update} resultCount={rows.length} />

      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(360px,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-ops-base">Override history</CardTitle>
          </CardHeader>
          <CardContent>
            <OverrideHistory records={overrideRecords} piiVisible={piiVisible} />
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <ChainProof entries={auditEntries} />
          {decision && (
            <Card>
              <CardHeader>
                <CardTitle className="text-ops-base">Evidence pack</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="font-mono text-ops-xs text-muted-fg">{decision.decision_id}</p>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={exporter.busy}
                  onClick={() => exporter.download(decision.decision_id, decision)}
                >
                  {exporter.busy
                    ? t("common.loading")
                    : exporter.mode === "json"
                      ? "Download JSON evidence"
                      : "Download PDF evidence"}
                </Button>
                {exporter.mode === "json" && (
                  <p className="text-ops-xs text-muted-fg">
                    Server PDF route not yet shipped — fell back to deterministic JSON.
                  </p>
                )}
                {exporter.error && (
                  <p role="alert" className="text-ops-xs text-safety-critical">
                    {exporter.error}
                  </p>
                )}
              </CardContent>
            </Card>
          )}
          {!decision && search.open && (
            <p className="text-ops-sm text-muted-fg">Decision not found.</p>
          )}
          {!search.open && (
            <p className="text-ops-sm text-muted-fg">
              Open a decision from Decision Trace to verify its chain here.
            </p>
          )}
        </div>
      </div>

      <PiiGate
        open={reauthOpen}
        busy={reauthBusy}
        error={reauthError}
        onSubmit={async (pw) => {
          await reauth(pw);
          setReauthOpen(false);
          update({ pii: true });
        }}
        onOpenChange={setReauthOpen}
      />

      {elevatedUntil && elevated && (
        <p className="text-ops-xs text-muted-fg" aria-live="polite">
          PII window open until {new Date(elevatedUntil).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })}.
        </p>
      )}
    </div>
  );
}
