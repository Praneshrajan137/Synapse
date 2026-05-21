import { useSessionStore } from "@state/session.store";
import type { EscalationMessage } from "@domain/escalation";

interface AuditPreviewProps {
  readonly message: EscalationMessage;
  readonly pendingAction?: "approved" | "rejected" | "modified" | null;
  readonly pendingReason?: string;
}

/**
 * Right-column audit row preview. Shows exactly what will be inserted into
 * `audit_escalations` when the operator commits. Reinforces I-4: nothing
 * hidden. Re-renders live as the operator types a reason.
 */
export function AuditPreview({ message, pendingAction, pendingReason }: AuditPreviewProps) {
  const tokenRef = useSessionStore((s) => s.operatorTokenRef);
  const row: Record<string, unknown> = {
    decision_id: message.decision_id,
    operator_token_ref: tokenRef ?? "(unauthenticated)",
    override_action: pendingAction ?? "(pending selection)",
    override_reason: pendingReason ?? "(pending reason)",
    escalation_reason: message.violations.map((v) => v.message).join("; ") || message.reason || "—",
    confidence_at_escalation: message.confidence,
    tier: message.tier ?? "tier_3",
    override_at: "(server timestamp at commit)",
    audit_immutable: true,
  };

  return (
    <aside aria-label="Audit row preview" className="syn-card-raised h-full p-4">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Audit preview</h2>
        <span className="text-2xs uppercase tracking-wide text-confidence-warn">
          will INSERT
        </span>
      </header>
      <dl className="space-y-1.5 text-xs">
        {Object.entries(row).map(([key, value]) => (
          <div key={key} className="flex justify-between gap-3">
            <dt className="font-mono text-ink-muted">{key}</dt>
            <dd className="max-w-[60%] truncate text-right font-mono text-ink" title={String(value)}>
              {typeof value === "boolean" ? String(value) : (value as string)}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-2xs text-ink-subtle">
        The row is INSERT-only into <code className="font-mono">audit_escalations</code>;
        I-4 prohibits UPDATE/DELETE.
      </p>
    </aside>
  );
}
