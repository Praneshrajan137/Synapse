import { useSynapseApi } from "@hooks/use-synapse-api";
import { fmt } from "@lib/formatters";
import { useEscalationStore } from "@state/escalation.store";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { HttpError, RateLimitError } from "@transport/errors";
import { toast } from "sonner";

interface OverrideArgs {
  readonly decision_id: string;
  readonly action: "approved" | "rejected" | "modified";
  readonly reason: string;
  readonly modified_action?: Record<string, unknown>;
}

/**
 * Audit-row-first override mutation (FE-INV-003 / FE-INV-021).
 *
 *   1. POST /api/v1/decisions/{id}/override (commits audit_escalations).
 *   2. On 2xx, mark the escalation entry as acted in the local store.
 *   3. On error, no optimistic update; show a typed toast.
 *
 * The orchestrator-side `override_confirm` envelope will also flow through
 * the existing /ws/escalation socket; the store entry is already acted by
 * then, so it's a no-op confirmation (used for telemetry).
 */
export function useOverrideMutation() {
  const api = useSynapseApi();
  const markActed = useEscalationStore((s) => s.markActed);
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (args: OverrideArgs) =>
      api.submitOverride(args.decision_id, {
        action: args.action,
        reason: args.reason,
        ...(args.modified_action ? { modified_action: args.modified_action } : {}),
      }),
    onSuccess: (response, args) => {
      markActed(args.decision_id, args.action);
      toast.success(
        `Override committed (${args.action}) — audit row #${response.audit_escalation_id}`,
      );
      qc.invalidateQueries({ queryKey: ["decisions"] });
    },
    onError: (err: Error) => {
      if (err instanceof RateLimitError) {
        toast.warning(
          err.retryAfterMs
            ? `Rate limited — retry in ${fmt.durationMs(err.retryAfterMs)}`
            : "Rate limited",
        );
        return;
      }
      if (err instanceof HttpError) {
        toast.error(`Override rejected: ${err.status} ${err.statusText}`);
        return;
      }
      toast.error(`Override failed: ${err.message}`);
    },
  });
}
