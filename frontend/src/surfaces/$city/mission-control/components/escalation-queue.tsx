/**
 * SYNAPSE Atlas Console — Mission Control queue.
 *
 * Renders ranked escalations into focusable EscalationCards.
 * Owns focus management:
 *   - The first card is auto-focused when the queue mounts.
 *   - Hotkey "next" / "prev" cycle within the rendered list.
 *   - Programmatic focus moves with `focusedDecisionId` so an external
 *     "?" / Esc handler can defocus without losing the index.
 *
 * Virtualization (react-virtual) is intentionally not introduced at
 * S3 scale: an HITL queue with >50 simultaneous escalations indicates
 * the orchestrator is mis-tuned, not a UI scale bug. We keep the
 * DOM lean (memo'd EscalationCards + 1s timer per card) and revisit
 * if profiles say otherwise.
 */
import { memo, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@shared/ui/cn";

import { EscalationCard } from "./escalation-card";
import type { Escalation } from "../model/escalation";

export interface EscalationQueueProps {
  readonly escalations: readonly Escalation[];
  readonly focusedDecisionId: string | null;
  readonly onFocusChange: (id: string | null) => void;
  readonly onApprove: (decisionId: string) => void;
  readonly onReject: (decisionId: string) => void;
  readonly onModify: (decisionId: string) => void;
  readonly disabled?: boolean;
  readonly className?: string;
}

export const EscalationQueue = memo(function EscalationQueue({
  escalations,
  focusedDecisionId,
  onFocusChange,
  onApprove,
  onReject,
  onModify,
  disabled = false,
  className,
}: EscalationQueueProps) {
  const { t } = useTranslation();
  const itemRefs = useRef<Map<string, HTMLLIElement>>(new Map());

  // Auto-focus the first card on initial mount when no other card is focused.
  // Subsequent focus changes are driven by the parent's hotkey handler.
  useEffect(() => {
    if (escalations.length === 0) return;
    if (focusedDecisionId) return;
    const first = escalations[0];
    if (first) onFocusChange(first.decision_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [escalations.length === 0]);

  // Move DOM focus when the React focus state updates.
  useEffect(() => {
    if (!focusedDecisionId) return;
    const el = itemRefs.current.get(focusedDecisionId);
    el?.focus();
  }, [focusedDecisionId]);

  if (escalations.length === 0) {
    return (
      <p
        role="status"
        aria-live="polite"
        className={cn(
          "rounded-md border border-border bg-card p-6 text-ops-sm text-muted-fg",
          className,
        )}
      >
        {t("missionControl.queueEmpty")}
      </p>
    );
  }

  return (
    <ul
      role="list"
      className={cn("grid gap-3", className)}
      aria-label={t("missionControl.title")}
    >
      {escalations.map((esc) => (
        <li
          key={esc.decision_id}
          ref={(el) => {
            if (el) itemRefs.current.set(esc.decision_id, el);
            else itemRefs.current.delete(esc.decision_id);
          }}
          tabIndex={-1}
          className="outline-none"
        >
          <EscalationCard
            escalation={esc}
            focused={esc.decision_id === focusedDecisionId}
            disabled={disabled}
            onFocus={() => onFocusChange(esc.decision_id)}
            onApprove={() => onApprove(esc.decision_id)}
            onReject={() => onReject(esc.decision_id)}
            onModify={() => onModify(esc.decision_id)}
          />
        </li>
      ))}
    </ul>
  );
});
