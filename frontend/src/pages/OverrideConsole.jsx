import React from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import ConfidenceGauge from "../components/ConfidenceGauge";
import { confidenceZone } from "@chromatic/tokens.ts";

const ACTIONS = [
  { action: "approved", label: "Approve", token: "var(--color-hitl-approve)" },
  { action: "modified", label: "Modify", token: "var(--color-hitl-modify)" },
  { action: "rejected", label: "Reject", token: "var(--color-hitl-reject)" },
];

function PageHeader({ title, subtitle, children }) {
  return (
    <header className="mb-5 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text-primary">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-text-tertiary">{subtitle}</p>}
      </div>
      {children}
    </header>
  );
}

function EscalationCard({ esc, onAction }) {
  const confidence = esc.confidence ?? 0;
  const zoneColor = `var(--color-confidence-${confidenceZone(confidence)})`;
  const tier = esc.tier ?? 1;
  const violations = esc.violations?.length ?? 0;

  return (
    <article
      className="panel relative overflow-hidden p-5"
      style={{ borderLeft: `3px solid ${zoneColor}` }}
    >
      <div className="flex flex-wrap items-center gap-5">
        <ConfidenceGauge value={confidence} size={96} />
        <div className="min-w-[180px] flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-base font-semibold text-text-primary">
              Decision {esc.decision_id?.slice(0, 8) ?? "--------"}
            </span>
            <span
              className="rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-text-inverse"
              style={{ background: `var(--color-tier-${tier})` }}
            >
              Tier {tier}
            </span>
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {violations} guardrail {violations === 1 ? "violation" : "violations"} · awaiting
            human decision
          </p>
        </div>
        <div className="flex gap-2">
          {ACTIONS.map(({ action, label, token }) => (
            <button
              key={action}
              type="button"
              onClick={() => onAction(esc.decision_id, action)}
              className="rounded-md px-4 py-2 text-sm font-semibold text-text-inverse transition-transform hover:-translate-y-px focus-visible:outline-2"
              style={{ background: token }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

export default function OverrideConsole() {
  const { messages, connected, send } = useWebSocket(
    `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/escalation`,
  );
  const pending = messages.filter((m) => m.type === "escalation");

  function handleAction(decisionId, action) {
    send({ decision_id: decisionId, response: { action } });
  }

  return (
    <div className="mx-auto max-w-[1100px] animate-fade-in">
      <PageHeader title="Override Console" subtitle="Confidence-gated human-in-the-loop review (I-5)">
        <span
          className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-1.5 text-xs font-semibold"
          style={{ color: connected ? "var(--color-state-success)" : "var(--color-state-danger)" }}
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: connected ? "var(--color-state-success)" : "var(--color-state-danger)" }}
            aria-hidden="true"
          />
          {connected ? "Connected" : "Disconnected"}
        </span>
      </PageHeader>

      {pending.length === 0 ? (
        <div className="panel p-8 text-center text-sm text-text-tertiary">
          No pending escalations — all decisions cleared the confidence gate.
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((esc, i) => (
            <EscalationCard key={esc.decision_id ?? i} esc={esc} onAction={handleAction} />
          ))}
        </div>
      )}
    </div>
  );
}
