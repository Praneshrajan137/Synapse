import type { EscalationMessage } from "@domain/escalation";
import {
  AgentProposalChip,
  ConfidenceGauge,
  ParetoFrontier,
  type ParetoPoint,
  ThresholdCountdown,
  TierBadge,
} from "@ds/compounds";
import { Button } from "@ds/primitives";
import { isBelowThreshold } from "@lib/confidence";
import { fmt } from "@lib/formatters";
import * as Dialog from "@radix-ui/react-dialog";
import { useMemo, useState } from "react";
import { ApproveForm } from "./ApproveForm";
import { ModifyForm } from "./ModifyForm";
import { RejectForm } from "./RejectForm";

interface EscalationCardProps {
  readonly message: EscalationMessage;
  readonly receivedAt: number;
  readonly pending: boolean;
  readonly onCommit: (payload: {
    action: "approved" | "rejected" | "modified";
    reason: string;
    modified_action?: Record<string, unknown>;
  }) => void;
}

type DialogKind = "approve" | "reject" | "modify" | null;

/**
 * The centerpiece. Header (decision_id + tier + age), confidence gauge,
 * the agent proposals row, Pareto frontier, reasoning trace (collapsible),
 * and action bar. Sub-threshold confidence demotes Approve from default
 * focus (FE-INV-007) and force-requires a reason.
 */
export function EscalationCard({ message, receivedAt, pending, onCommit }: EscalationCardProps) {
  const [dialog, setDialog] = useState<DialogKind>(null);
  const [reasonDraft, setReasonDraft] = useState("");

  const below = isBelowThreshold(message.confidence);
  const tier = message.tier ?? "tier_3";

  // The HITL window starts when the orchestrator escalated (created_at), or
  // when the FE first saw it if the server didn't stamp one.
  const startedAtMs = useMemo(() => {
    if (message.created_at) {
      const parsed = Date.parse(message.created_at);
      if (Number.isFinite(parsed)) return parsed;
    }
    return receivedAt;
  }, [message.created_at, receivedAt]);

  const proposals = useMemo(() => message.proposals as Array<Record<string, unknown>>, [message]);

  const paretoPoints: ParetoPoint[] = useMemo(
    () =>
      proposals.map((p, i) => {
        const utility = typeof p.utility_score === "number" ? (p.utility_score as number) : 0;
        const confidence = typeof p.confidence === "number" ? (p.confidence as number) : 0;
        const agentName =
          typeof p.agent_name === "string" ? (p.agent_name as string) : `proposal-${i}`;
        return { id: `${agentName}-${i}`, x: utility, y: confidence, label: agentName };
      }),
    [proposals],
  );

  const selectedAgent =
    (message.recommended_action?.agent_name as string | undefined) ?? proposals[0]?.agent_name;

  function handleSubmit(payload: {
    action: "approved" | "rejected" | "modified";
    reason: string;
    modified_action?: Record<string, unknown>;
  }) {
    setReasonDraft(payload.reason);
    onCommit(payload);
    setDialog(null);
  }

  return (
    <section
      className="syn-card-raised flex flex-1 flex-col gap-4 overflow-auto p-5"
      aria-label={`Active escalation ${message.decision_id}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <ConfidenceGauge value={message.confidence} size={88} />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm text-ink">
                {fmt.shortId(message.decision_id, 12)}
              </span>
              <TierBadge tier={tier} />
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {message.violations.length === 0 &&
                (message.reason ?? "Escalated for human judgement")}
            </p>
            <p className="text-2xs text-ink-subtle">
              Received {fmt.relativeTime(new Date(receivedAt).toISOString())}
            </p>
          </div>
        </div>
      </header>

      {/* The Threshold spine — the operator always knows the cost of not acting. */}
      <ThresholdCountdown startedAtMs={startedAtMs} />

      {/* FE-INV-038: every violation is rendered with its severity — never
          collapsed to a count. The operator overriding a guardrail must see
          exactly WHICH constraints fired and how hard. */}
      {message.violations.length > 0 && (
        <section aria-label="Guardrail violations" className="space-y-1.5">
          <h3 className="text-2xs uppercase tracking-wide text-ink-muted">
            Guardrail violations ({message.violations.length})
          </h3>
          <ul className="space-y-1">
            {message.violations.map((v) => {
              const severity = v.severity ?? "medium";
              const tone =
                severity === "critical" || severity === "high"
                  ? "text-signal-danger"
                  : severity === "medium"
                    ? "text-signal-warning"
                    : "text-ink-muted";
              return (
                <li key={`${v.code}:${v.message}`} className="flex items-start gap-2 text-xs">
                  <span className={`shrink-0 font-semibold uppercase ${tone}`}>{severity}</span>
                  <span className="font-mono text-2xs text-ink-subtle">{v.code}</span>
                  <span className="text-ink-muted">{v.message}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section aria-label="Agent proposals" className="space-y-2">
        <h3 className="text-2xs uppercase tracking-wide text-ink-muted">Proposals</h3>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          {proposals.map((p, i) => {
            const agentName =
              typeof p.agent_name === "string" ? (p.agent_name as string) : `proposal-${i}`;
            const utility =
              typeof p.utility_score === "number" ? (p.utility_score as number) : undefined;
            const confidence =
              typeof p.confidence === "number" ? (p.confidence as number) : undefined;
            return (
              <AgentProposalChip
                key={`${agentName}-${i}`}
                agentName={agentName}
                utilityScore={utility}
                confidence={confidence}
                isWinner={agentName === selectedAgent}
                status={agentName === selectedAgent ? "selected" : "proposed"}
              />
            );
          })}
        </div>
      </section>

      {paretoPoints.length > 1 && (
        <section aria-label="Pareto frontier" className="space-y-2">
          <h3 className="text-2xs uppercase tracking-wide text-ink-muted">
            Pareto frontier (utility vs confidence)
          </h3>
          <ParetoFrontier
            points={paretoPoints}
            selectedId={paretoPoints.find((p) => p.label === selectedAgent)?.id}
            xLabel="utility"
            yLabel="confidence"
          />
        </section>
      )}

      <details className="syn-card p-3 text-xs text-ink-muted">
        <summary className="cursor-pointer text-sm font-medium text-ink">
          Reasoning trace (A2A / context)
        </summary>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-2xs">
          {JSON.stringify(message, null, 2)}
        </pre>
      </details>

      {/* Sticky action bar */}
      <footer className="sticky bottom-0 mt-auto flex flex-wrap items-center justify-end gap-2 border-t border-border bg-surface-raised px-2 pb-2 pt-3">
        <Dialog.Root
          open={dialog === "reject"}
          onOpenChange={(o) => setDialog(o ? "reject" : null)}
        >
          <Dialog.Trigger asChild>
            <Button variant="danger" size="md" aria-keyshortcuts="R" autoFocus={below}>
              Reject (R)
            </Button>
          </Dialog.Trigger>
          <OverrideDialog title="Reject decision">
            <RejectForm
              pending={pending}
              onCancel={() => setDialog(null)}
              onSubmit={handleSubmit}
            />
          </OverrideDialog>
        </Dialog.Root>

        <Dialog.Root
          open={dialog === "modify"}
          onOpenChange={(o) => setDialog(o ? "modify" : null)}
        >
          <Dialog.Trigger asChild>
            <Button variant="warning" size="md" aria-keyshortcuts="M">
              Modify (M)
            </Button>
          </Dialog.Trigger>
          <OverrideDialog title="Modify action">
            <ModifyForm
              initialAction={message.recommended_action ?? {}}
              pending={pending}
              onCancel={() => setDialog(null)}
              onSubmit={handleSubmit}
            />
          </OverrideDialog>
        </Dialog.Root>

        <Dialog.Root
          open={dialog === "approve"}
          onOpenChange={(o) => setDialog(o ? "approve" : null)}
        >
          <Dialog.Trigger asChild>
            <Button variant="success" size="md" aria-keyshortcuts="A" autoFocus={!below}>
              Approve (A)
            </Button>
          </Dialog.Trigger>
          <OverrideDialog title={below ? "Approve — reason required" : "Approve"}>
            <ApproveForm
              requireReason={below}
              pending={pending}
              onCancel={() => setDialog(null)}
              onSubmit={handleSubmit}
            />
          </OverrideDialog>
        </Dialog.Root>
      </footer>

      {/* Hidden: keeps the latest typed reason visible to the AuditPreview prop drilling. */}
      <span hidden data-reason-draft={reasonDraft} />
    </section>
  );
}

function OverrideDialog({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-canvas/70 backdrop-blur-sm" />
      <Dialog.Content
        className="fixed left-1/2 top-1/2 z-50 w-[min(560px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-surface p-5 shadow-e4"
        aria-describedby={undefined}
      >
        <Dialog.Title className="mb-3 text-base font-semibold text-ink">{title}</Dialog.Title>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  );
}
