/**
 * SYNAPSE Atlas Console — client-side audit chain banner.
 *
 * Wraps `useChainVerify` with a UI: green "verified" tile when the
 * chain checks out, red banner with the broken row index when it
 * doesn't. Audit Vault export is gated on this state in S5.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@shared/ui/badge";
import { Card, CardContent } from "@shared/ui/card";

import { type AuditEntry } from "../model/audit-hash";
import { useChainVerify } from "../hooks/use-chain-verify";

export interface ChainProofProps {
  readonly entries: readonly AuditEntry[] | null;
}

export const ChainProof = memo(function ChainProof({ entries }: ChainProofProps) {
  const { t } = useTranslation();
  const { result, isVerifying } = useChainVerify(entries);

  if (!entries || entries.length === 0) {
    return (
      <Card>
        <CardContent className="text-ops-sm text-muted-fg">
          No audit chain attached.
        </CardContent>
      </Card>
    );
  }

  if (isVerifying) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 text-ops-sm text-muted-fg">
          <span className="inline-block h-2 w-2 animate-pulse-slow rounded-full bg-tier-2" />
          Verifying {entries.length} entries…
        </CardContent>
      </Card>
    );
  }

  if (result.valid) {
    return (
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 text-ops-sm">
          <Badge variant="ok">{t("auditVault.chainOk")}</Badge>
          <span className="text-muted-fg">{entries.length} entries verified</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-2">
        <div role="alert" className="flex flex-wrap items-center gap-3">
          <Badge variant="critical">{t("auditVault.chainBroken")}</Badge>
          <span className="text-ops-sm text-safety-critical">
            Broken at index {result.brokenAt}
          </span>
        </div>
        <dl className="grid grid-cols-[120px_1fr] gap-y-1 font-mono text-ops-xs">
          <dt className="text-muted-fg">expected</dt>
          <dd className="break-all">{result.expected ?? "(none)"}</dd>
          <dt className="text-muted-fg">actual</dt>
          <dd className="break-all">{result.actual ?? "(none)"}</dd>
        </dl>
      </CardContent>
    </Card>
  );
});
