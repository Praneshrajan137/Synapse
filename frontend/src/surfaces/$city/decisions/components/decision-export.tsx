/**
 * SYNAPSE Atlas Console — Decision export.
 *
 * S3 ships **deterministic JSON** export. The export body is canonical
 * JSON (sorted keys, ',' / ':' separators) so two exports of the same
 * decision are byte-equal — exactly what the Audit Vault's PDF
 * deterministic-export contract (S5) needs as a substrate.
 *
 * PDF export lands in S5; in S3 the button is wired but disabled with
 * an explicit reason so the operator can't be surprised when it ships.
 */
import { memo, useState } from "react";
import { useTranslation } from "react-i18next";

import { canonicalize } from "@shared/canonical-json";
import { Button } from "@shared/ui/button";

import type { ConsensusDecision } from "../model/decision";

export interface DecisionExportProps {
  readonly decision: ConsensusDecision;
  readonly chainValid: boolean;
}

export const DecisionExport = memo(function DecisionExport({
  decision,
  chainValid,
}: DecisionExportProps) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);

  function exportJson(): void {
    setBusy(true);
    try {
      const body = canonicalize(decision);
      const blob = new Blob([body], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `atlas-decision-${decision.decision_id}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Defer revoke so the browser has a chance to start the download.
      setTimeout(() => URL.revokeObjectURL(url), 1_000);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap gap-2" aria-busy={busy}>
      <Button
        size="sm"
        variant="outline"
        onClick={exportJson}
        disabled={busy || !chainValid}
        aria-disabled={busy || !chainValid}
      >
        {t("decisionTrace.drawer.exportJson")}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        disabled
        title="Deterministic PDF export ships in S5 (Audit Vault)"
      >
        {t("decisionTrace.drawer.exportPdf")}
      </Button>
    </div>
  );
});
