import { EscalationMessageSchema } from "@domain/escalation";
import { ConnectionPill } from "@ds/compounds";
import { Badge } from "@ds/primitives";
import { useFirehose } from "@hooks/use-firehose";
import { useWs } from "@hooks/use-ws";
import { useEscalationStore } from "@state/escalation.store";
import { useEffect, useMemo, useState } from "react";
import { AuditPreview } from "./AuditPreview";
import { CalibrationMirror } from "./CalibrationMirror";
import { EscalationCard } from "./EscalationCard";
import { EscalationQueue } from "./EscalationQueue";
import { useCockpitShortcuts } from "./useCockpitShortcuts";
import { useOverrideMutation } from "./useOverrideMutation";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${
  window.location.host
}/ws/escalation`;

/**
 * Override Cockpit — P1 elevation.
 *
 *   Left column   = EscalationQueue
 *   Center column = EscalationCard (active escalation + Pareto + actions)
 *   Right column  = AuditPreview (the row that will be INSERTed)
 *
 * Keyboard: A approve, R reject, M modify, J/K cycle, Esc closes a modal.
 *
 * Mobile (<md): queue becomes a top strip, audit-preview slides up under
 * the card via Radix Dialog (room for P4 dedicated bottom-sheet hardening).
 */
export function Cockpit() {
  const ws = useWs(WS_URL);
  // ADR-044: escalations ALSO push through the multiplexed firehose
  // (`synapse.orchestrator.escalation` → channel "escalation"). The store
  // dedupes by decision_id, so the legacy socket and the firehose can
  // coexist during the transition.
  useFirehose({ topics: ["escalation"] });
  const entries = useEscalationStore((s) => s.entries);
  const append = useEscalationStore((s) => s.append);
  const setConnected = useEscalationStore((s) => s.setConnected);

  const override = useOverrideMutation();

  // Schema-validate every inbound escalation envelope.
  useEffect(() => {
    setConnected(ws.connected);
  }, [ws.connected, setConnected]);

  useEffect(() => {
    const off = ws.on("escalation", (raw) => {
      const parsed = EscalationMessageSchema.safeParse(raw);
      if (!parsed.success) {
        // eslint-disable-next-line no-console
        console.warn("escalation_rejected_by_schema", parsed.error.issues);
        return;
      }
      append(parsed.data);
    });
    return off;
  }, [ws, append]);

  // override_confirm is informational; markActed already happened on mutation
  // success. Future telemetry hook lives here.
  useEffect(() => {
    const off = ws.on("override_confirm", () => {
      /* no-op for now; logged server-side via audit_escalations */
    });
    return off;
  }, [ws]);

  const pending = useMemo(() => entries.filter((e) => e.status === "pending"), [entries]);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Keep an active id; default to the most-urgent pending entry.
  useEffect(() => {
    if (activeId && pending.some((p) => p.id === activeId)) return;
    setActiveId(pending[0]?.id ?? null);
  }, [pending, activeId]);

  const activeEntry = useMemo(
    () => entries.find((e) => e.id === activeId) ?? null,
    [entries, activeId],
  );

  // Keyboard bindings — bound to the active entry.
  useCockpitShortcuts(
    {
      approve: () => {
        if (!activeEntry) return;
        // sub-threshold approves require a reason — open the dialog rather
        // than firing directly (matches FE-INV-007 intent).
        document.querySelector<HTMLButtonElement>('button[aria-keyshortcuts="A"]')?.click();
      },
      reject: () =>
        document.querySelector<HTMLButtonElement>('button[aria-keyshortcuts="R"]')?.click(),
      modify: () =>
        document.querySelector<HTMLButtonElement>('button[aria-keyshortcuts="M"]')?.click(),
      next: () => {
        if (pending.length === 0) return;
        const idx = pending.findIndex((p) => p.id === activeId);
        setActiveId(pending[Math.min(pending.length - 1, idx + 1)]?.id ?? null);
      },
      prev: () => {
        if (pending.length === 0) return;
        const idx = pending.findIndex((p) => p.id === activeId);
        setActiveId(pending[Math.max(0, idx - 1)]?.id ?? null);
      },
      escape: () => {
        // Radix closes dialog on Esc natively; this is a no-op hook for now.
      },
    },
    pending.length > 0,
  );

  return (
    <section className="flex h-full flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-semibold text-ink">Override Cockpit</h1>
          <p className="text-sm text-ink-muted">
            Confidence-gated escalations stream in via{" "}
            <code className="font-mono text-ink">/ws/escalation</code>. Acting commits an immutable
            audit row (I-4); the orchestrator is notified only after.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ConnectionPill state={ws.state} />
          <Badge tone="neutral" aria-label={`${pending.length} pending escalations`}>
            {pending.length} pending
          </Badge>
          <output aria-live="polite" className="sr-only">
            {pending.length === 0
              ? "No escalations awaiting human judgement."
              : `${pending.length} escalations pending.`}
          </output>
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[280px_minmax(0,1fr)_320px]">
        <EscalationQueue entries={entries} activeId={activeId} onSelect={setActiveId} />
        {activeEntry ? (
          <>
            <EscalationCard
              message={activeEntry.message}
              receivedAt={activeEntry.received_at}
              pending={override.isPending}
              onCommit={(payload) => override.mutate({ decision_id: activeEntry.id, ...payload })}
            />
            <div className="hidden space-y-4 lg:block">
              <AuditPreview message={activeEntry.message} />
              <CalibrationMirror entries={entries} />
            </div>
          </>
        ) : (
          <div className="syn-card flex items-center justify-center text-sm text-ink-muted lg:col-span-2">
            All clear. No escalations awaiting human judgement.
          </div>
        )}
      </div>
    </section>
  );
}
