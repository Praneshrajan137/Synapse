/**
 * SYNAPSE Atlas Console — Mission Control route (S3 deep work).
 *
 * Plan §5.2 contract:
 *   - Live escalation queue ranked by tier × (1−confidence) × ttl⁻¹.
 *   - Sticky urgency bar when any tier-4 has ≤30s left.
 *   - Detail drawer alongside the queue showing proposals + Pareto.
 *   - Keyboard-first navigation (j/k/Enter/r/m/Esc/?).
 *   - WebSocket transport with offline-queue persistence.
 *   - Live region announcing new escalations.
 *
 * Acceptance: ≤5s median decision time + zero axe violations + every
 * hotkey discoverable via the "?" dialog.
 */
import { createFileRoute, useParams } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { hasCriticalTier4 } from "./model/ranker";
import type { ResponsePayload } from "./model/escalation";
import { EscalationDrawer } from "./components/escalation-drawer";
import { EscalationQueue } from "./components/escalation-queue";
import { HotkeysHelp } from "./components/hotkeys-help";
import { ModifyForm, type ModifyFormValues } from "./components/modify-form";
import { UrgencyBar } from "./components/urgency-bar";
import { useEscalations } from "./hooks/use-escalations";
import { useHotkeys, type HotkeyAction } from "./hooks/use-hotkeys";
import { useOfflineQueue } from "./hooks/use-offline-queue";

export const Route = createFileRoute("/$city/mission-control/")({
  component: MissionControl,
});

function MissionControl() {
  const { t } = useTranslation();
  const { city } = useParams({ from: "/$city/mission-control/" });

  const { escalations, connected, send, latestAck } = useEscalations();
  const { pending: offlinePending, enqueue, ack } = useOfflineQueue();

  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [modifyTarget, setModifyTarget] = useState<string | null>(null);

  // Tick once per second so the urgency bar's "remaining seconds" stays fresh.
  // Cards manage their own per-second tick; this drives only the bar.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  // Drop the IDB entry when the orchestrator ACKs.
  useEffect(() => {
    if (latestAck?.client_id) {
      void ack(latestAck.client_id);
    }
  }, [latestAck, ack]);

  // Replay any unACKed entries on reconnect. Each replay is a no-op if the
  // orchestrator already processed it (decision_id is idempotent).
  useEffect(() => {
    if (!connected) return;
    for (const entry of offlinePending) {
      send({ ...entry.payload, client_id: entry.clientId });
    }
    // Intentionally only depend on `connected`: replay on transition false→true.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected]);

  const focusedEscalation =
    focusedId !== null
      ? escalations.find((e) => e.decision_id === focusedId) ?? null
      : null;

  // Snap focus to the head of the queue if the focused item disappears (ACKed).
  useEffect(() => {
    if (focusedId && !escalations.some((e) => e.decision_id === focusedId)) {
      setFocusedId(escalations[0]?.decision_id ?? null);
    }
  }, [escalations, focusedId]);

  const dispatch = useCallback(
    async (
      decisionId: string,
      response: ResponsePayload["response"],
    ): Promise<void> => {
      const payload: ResponsePayload = {
        decision_id: decisionId,
        response,
        client_id: "", // filled by enqueue
      };
      const queued = await enqueue(decisionId, payload);
      send({ ...payload, client_id: queued.clientId });
    },
    [enqueue, send],
  );

  const onApprove = useCallback(
    (id: string) => void dispatch(id, { action: "approved" }),
    [dispatch],
  );
  const onReject = useCallback(
    (id: string) => void dispatch(id, { action: "rejected" }),
    [dispatch],
  );
  const onModifyStart = useCallback((id: string) => setModifyTarget(id), []);
  const onModifySubmit = useCallback(
    (values: ModifyFormValues) => {
      if (!modifyTarget) return;
      void dispatch(modifyTarget, {
        action: "modified",
        modification: values as unknown as Record<string, unknown>,
      });
      setModifyTarget(null);
    },
    [dispatch, modifyTarget],
  );

  const onHotkey = useCallback(
    (action: HotkeyAction) => {
      const idx = focusedId ? escalations.findIndex((e) => e.decision_id === focusedId) : -1;
      switch (action) {
        case "next": {
          if (escalations.length === 0) return;
          const next = idx < 0 ? 0 : Math.min(idx + 1, escalations.length - 1);
          const target = escalations[next];
          if (target) setFocusedId(target.decision_id);
          break;
        }
        case "prev": {
          if (escalations.length === 0) return;
          const next = idx <= 0 ? 0 : idx - 1;
          const target = escalations[next];
          if (target) setFocusedId(target.decision_id);
          break;
        }
        case "approve":
          if (focusedId) onApprove(focusedId);
          break;
        case "reject":
          if (focusedId) onReject(focusedId);
          break;
        case "modify":
          if (focusedId) onModifyStart(focusedId);
          break;
        case "defocus":
          setHelpOpen(false);
          setModifyTarget(null);
          setFocusedId(null);
          break;
        case "help":
          setHelpOpen((o) => !o);
          break;
        default: {
          const _exhaustive: never = action;
          void _exhaustive;
        }
      }
    },
    [escalations, focusedId, onApprove, onModifyStart, onReject],
  );

  // Disable hotkeys when a modal is open — Radix already traps focus, but
  // we don't want `j/k` to leak through to the queue underneath.
  const hotkeysActive = !helpOpen && modifyTarget === null;
  useHotkeys({ enabled: hotkeysActive, onAction: onHotkey });

  // Live region announces new arrivals (assertive when tier-4, polite else).
  const criticals = useMemo(
    () => escalations.filter((e) => e.tier === "tier_4"),
    [escalations],
  );
  const showUrgency = hasCriticalTier4(escalations, now);

  return (
    <div className="grid h-[calc(100vh-7rem)] grid-rows-[auto_auto_1fr] gap-3 lg:h-[calc(100vh-5rem)]">
      <header className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-ops-xl font-bold tracking-tight">
          {t("missionControl.title")}
        </h1>
        <span className="text-ops-sm text-muted-fg">{t(`city.${city}`)}</span>
        <span
          className={
            "ml-auto text-ops-xs " +
            (connected ? "text-safety-ok" : "text-safety-critical")
          }
          aria-live="polite"
        >
          {connected ? "● live" : "● disconnected"}
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-ops-xs text-muted-fg hover:bg-muted"
          aria-keyshortcuts="?"
          onClick={() => setHelpOpen(true)}
        >
          ? · {t("missionControl.hotkeys.help")}
        </button>
      </header>

      <div role="status" aria-live="polite" className="sr-only">
        {t("missionControl.queueLiveAria", { count: escalations.length })}
      </div>

      {showUrgency && <UrgencyBar criticals={criticals} now={now} />}

      <div className="grid grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(360px,1fr)_minmax(360px,1fr)]">
        <div className="overflow-auto">
          <EscalationQueue
            escalations={escalations}
            focusedDecisionId={focusedId}
            onFocusChange={setFocusedId}
            onApprove={onApprove}
            onReject={onReject}
            onModify={onModifyStart}
          />
        </div>
        <div className="overflow-hidden">
          <EscalationDrawer escalation={focusedEscalation} />
        </div>
      </div>

      <HotkeysHelp open={helpOpen} onOpenChange={setHelpOpen} />
      <ModifyForm
        open={modifyTarget !== null}
        onOpenChange={(o) => {
          if (!o) setModifyTarget(null);
        }}
        onSubmit={onModifySubmit}
        decisionIdLabel={modifyTarget ?? ""}
      />
    </div>
  );
}
