/**
 * SYNAPSE Atlas Console — Audit Vault override history.
 *
 * Joins decision rows that have a `human_override` against the
 * controlled-vocabulary code table. Renders a compact, AAA-contrast
 * timeline.
 */
import { memo } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@shared/ui/badge";

import { OVERRIDE_CODES_INDEX } from "../model/override-codes";

const SEVERITY_VARIANT = {
  info: "muted",
  warn: "warn",
  alert: "alert",
  critical: "critical",
} as const;

export interface OverrideRecord {
  readonly decision_id: string;
  readonly code: string;
  readonly user: string;
  readonly reason?: string;
  readonly at: string;
  readonly pii_redacted_user?: string;
}

export interface OverrideHistoryProps {
  readonly records: readonly OverrideRecord[];
  /** When false, redact the user column. */
  readonly piiVisible: boolean;
}

export const OverrideHistory = memo(function OverrideHistory({
  records,
  piiVisible,
}: OverrideHistoryProps) {
  const { t } = useTranslation();
  if (records.length === 0) {
    return (
      <p className="text-ops-sm text-muted-fg">No overrides in the active filter window.</p>
    );
  }
  return (
    <table
      role="table"
      aria-label="Override history"
      className="w-full border-collapse text-ops-sm"
    >
      <thead>
        <tr className="text-left">
          <Th>Time</Th>
          <Th>User</Th>
          <Th>Code</Th>
          <Th>Decision</Th>
          <Th>Reason</Th>
        </tr>
      </thead>
      <tbody>
        {records.map((r) => {
          const code = OVERRIDE_CODES_INDEX.get(r.code);
          const variant = code ? SEVERITY_VARIANT[code.severity] : "muted";
          return (
            <tr
              key={`${r.decision_id}-${r.at}`}
              className="border-b border-border/30"
            >
              <td className="px-2 py-2 tabular-nums">
                <time dateTime={r.at}>
                  {new Date(r.at).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                    hour12: false,
                  })}
                </time>
              </td>
              <td className="px-2 py-2 font-mono">
                {piiVisible ? r.user : r.pii_redacted_user ?? "•••••"}
                {!piiVisible && (
                  <span className="ml-1 text-ops-xs text-muted-fg" aria-label="PII redacted">
                    ({t("auditVault.redactedNotice")})
                  </span>
                )}
              </td>
              <td className="px-2 py-2">
                <Badge variant={variant}>{code?.label ?? r.code}</Badge>
              </td>
              <td className="px-2 py-2 font-mono text-ops-xs text-muted-fg">
                {r.decision_id.slice(0, 8)}…
              </td>
              <td className="px-2 py-2 text-muted-fg">
                {r.reason ?? "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
});

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th
      scope="col"
      className="border-b border-border bg-muted/40 px-2 py-2 text-ops-xs uppercase tracking-wide text-muted-fg"
    >
      {children}
    </th>
  );
}
