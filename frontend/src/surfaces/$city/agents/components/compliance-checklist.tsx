/**
 * SYNAPSE Atlas Console — Agent Floor compliance checklist.
 *
 * One row per invariant / pre / post-condition derived from the
 * agent's spec.yaml. Status drives the icon + AAA-contrast colour:
 *   - pass  → ok (green)
 *   - watch → warn (amber)
 *   - fail  → critical (red, AAA on safety-critical token)
 */
import { memo } from "react";
import { Check, AlertTriangle, X } from "lucide-react";

import { Badge } from "@shared/ui/badge";

import type { ComplianceItem, ComplianceSummary } from "../model/compliance";

const STATUS_VARIANT = {
  pass: "ok",
  watch: "warn",
  fail: "critical",
} as const;

const STATUS_ICON = {
  pass: Check,
  watch: AlertTriangle,
  fail: X,
} as const;

const KIND_LABEL: Record<ComplianceItem["kind"], string> = {
  invariant: "INV",
  precondition: "PRE",
  postcondition: "POST",
};

export interface ComplianceChecklistProps {
  readonly summary: ComplianceSummary;
  readonly compact?: boolean;
}

export const ComplianceChecklist = memo(function ComplianceChecklist({
  summary,
  compact = false,
}: ComplianceChecklistProps) {
  return (
    <ul role="list" className="flex flex-col gap-1">
      {summary.items.map((item) => {
        const Icon = STATUS_ICON[item.status];
        return (
          <li
            key={`${item.kind}-${item.id}`}
            className="flex items-start gap-2 rounded border border-border/40 bg-bg/40 p-2 text-ops-xs"
          >
            <Badge variant={STATUS_VARIANT[item.status]} className="shrink-0">
              <Icon size={12} aria-hidden="true" /> {KIND_LABEL[item.kind]}
            </Badge>
            <span className="font-mono text-muted-fg">{item.id}</span>
            {!compact && (
              <span className="min-w-0 flex-1 truncate" title={item.description}>
                {item.description}
              </span>
            )}
            {item.severity === "critical" && item.status === "fail" && (
              <Badge variant="critical" className="ml-auto">
                CRITICAL
              </Badge>
            )}
          </li>
        );
      })}
    </ul>
  );
});
