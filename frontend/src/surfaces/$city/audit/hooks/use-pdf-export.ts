/**
 * SYNAPSE Atlas Console — PDF export trigger.
 *
 * Calls the gateway's deterministic-PDF endpoint
 * (`POST /api/v1/audit/{decision_id}/pdf`) and triggers a browser
 * download. The endpoint returns a deterministic byte stream — same
 * input ⇒ same bytes ⇒ FSSAI-grade evidence.
 *
 * Until S5 backend wiring lands, the call falls back to a client-side
 * canonical-JSON download so the operator always has *something*; the
 * `mode` field on the result records which path was taken.
 */
import { useState } from "react";

import { canonicalize } from "@shared/canonical-json";
import { ApiError, synapseFetcher } from "@shared/api/fetcher";

export interface UsePdfExportResult {
  readonly busy: boolean;
  readonly error: string | null;
  readonly mode: "pdf" | "json" | null;
  readonly download: (decisionId: string, decisionPayload: unknown) => Promise<void>;
}

export function usePdfExport(): UsePdfExportResult {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"pdf" | "json" | null>(null);

  async function download(decisionId: string, decisionPayload: unknown): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const blob = await synapseFetcher<Blob>({
        url: `/api/v1/audit/${encodeURIComponent(decisionId)}/pdf`,
        method: "GET",
        responseType: "blob",
      });
      saveBlob(blob, `atlas-audit-${decisionId}.pdf`);
      setMode("pdf");
    } catch (err) {
      // Backend not yet shipped → fall back to deterministic JSON so
      // the surface keeps a working evidence path. The contract here
      // matches the S3 Decision Trace export.
      if (err instanceof ApiError && err.status === 404) {
        const body = canonicalize(decisionPayload);
        saveBlob(new Blob([body], { type: "application/json" }), `atlas-audit-${decisionId}.json`);
        setMode("json");
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return { busy, error, mode, download };
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}
