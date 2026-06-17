import { type ConsensusDecision, ConsensusDecisionSchema } from "@domain/consensus-decision";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { useQuery } from "@tanstack/react-query";
import type { DecisionDetailResponse } from "@transport/synapse-api";

// Shared decision source of truth (extracted from DecisionDetail in the
// Council Theater work). The GET /api/v1/decisions/{id} envelope is loose on
// its JSONB-bag fields (proposals, audit_trace, pareto_front …); the strict
// ConsensusDecisionSchema is the contract the replay slicer and the consensus
// choreography both consume. Doing the reshape ONCE means the analyst detail
// (Decision Theater) and the cinematic reconstruction (Council Theater) can
// never drift apart (FE-INV-002).

export interface DecisionView {
  readonly decision: ConsensusDecision;
  readonly raw: DecisionDetailResponse;
}

/**
 * Pure reshape of the decision-detail envelope into a validated
 * `ConsensusDecision` (+ the raw envelope for the honesty fields the strict
 * schema does not carry: chain hashes, is_synthetic, outcome, escalations).
 *
 * Pure — no I/O, no Date.now except the same created_at fallback the inline
 * version used. Throws a `schema violation` Error on an invalid envelope so
 * callers surface it as an explicit error state, never a silent render.
 */
export function reshapeDecision(raw: DecisionDetailResponse, fallbackId: string): DecisionView {
  const candidate = {
    decision_id: raw.decision_id ?? fallbackId,
    timestamp: raw.created_at ?? new Date().toISOString(),
    tier: raw.tier ?? "tier_2",
    proposals: raw.proposals ?? [],
    selected_action: raw.selected_action ?? {},
    pareto_weights: raw.pareto_weights ?? {},
    confidence: raw.confidence ?? 0,
    audit_trace: raw.audit_trace ?? [],
    phase_reached: raw.phase_reached ?? 1,
    // ADR-044: the previously-imprisoned anatomy columns now flow.
    debate_rounds: raw.debate_rounds ?? 0,
    human_override: raw.human_override ?? null,
    // The 8-D arbitration front, when the audit row carries it (Tier 3–4).
    // Fast-path / older rows have none — the choreography then renders an
    // honest empty state rather than inventing one.
    pareto_front: raw.pareto_front ?? null,
    context_messages: raw.context_messages ?? [],
    execution_confirmations: raw.execution_confirmations ?? [],
    escalated_to_human: raw.escalated ?? false,
  };
  const parsed = ConsensusDecisionSchema.safeParse(candidate);
  if (!parsed.success) {
    throw new Error(`schema violation: ${parsed.error.issues[0]?.message ?? "unknown"}`);
  }
  return { decision: parsed.data, raw };
}

/**
 * TanStack Query for one decision by id, reshaped + validated. The query key
 * (`["decision", id]`) is shared with the prior inline DecisionDetail query so
 * the cache is reused across the analyst and cinematic surfaces.
 */
export function useDecisionQuery(id: string | undefined) {
  const api = useSynapseApi();
  return useQuery({
    queryKey: ["decision", id],
    queryFn: async (): Promise<DecisionView> => {
      if (!id) throw new Error("missing decision id");
      const raw = await api.getDecision(id);
      return reshapeDecision(raw, id);
    },
    enabled: !!id,
  });
}
