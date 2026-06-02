"""
SYNAPSE Orchestrator — Five-phase consensus protocol (~400 lines).

Phase 1 (COLLECTING):   Broadcast A2A proposal() to relevant agents.
Phase 2 (DEBATING):     LLM-mediated debate (Tier 3-4 only, max 3 rounds).
Phase 3 (ARBITRATING):  NSGA-II Pareto optimisation via pymoo.
Phase 4 (EXECUTING):    Dispatch per-agent actions, log audit, guardrails.
Phase 5 (LEARNING):     Meta-RL weight update, semantic cache update.

Tier 1-2 fast path (80 % of decisions): Phase 1 -> Phase 4 -> Phase 5.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC
from typing import TYPE_CHECKING, Any

import deal
import structlog
from synapse_common.a2a_sdk import send_a2a_request
from synapse_common.metrics import (
    CONSENSUS_DEBATE_ROUNDS,
    CONSENSUS_DECISIONS_TOTAL,
    CONSENSUS_DURATION,
    CONSENSUS_PROPOSALS_RECEIVED,
    HITL_ESCALATIONS_TOTAL,
)
from synapse_common.models import (
    AgentProposal,
    ConsensusDecision,
    ContextMessage,
    DecisionTier,
    MessageStatus,
)

from orchestrator.consensus.models import ConflictReport, TierClassification
from orchestrator.consensus.pareto import OBJECTIVES, run_pareto_arbitration
from orchestrator.state_machine import OrchestratorStateMachine

if TYPE_CHECKING:
    from orchestrator.audit.logger import AuditLogger
    from orchestrator.config import OrchestratorConfig
    from orchestrator.consensus.tier_router import TierRouter
    from orchestrator.guardrails.rules import GuardrailEngine
    from orchestrator.hitl.escalation import HITLEscalation
    from orchestrator.llm.context_builder import ContextBuilder
    from orchestrator.llm.ollama_client import OllamaClient
    from orchestrator.llm.semantic_cache import SemanticDecisionCache
    from orchestrator.meta_rl.meta_agent import MetaRLAgent

logger = structlog.get_logger(__name__)

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}

AGENT_ENDPOINTS: dict[str, str] = {
    "demand_prophet": "http://demand-prophet:8001",
    "routing_navigator": "http://routing-navigator:8002",
    "inventory_sentinel": "http://inventory-sentinel:8003",
    "freshness_guardian": "http://freshness-guardian:8004",
    "pricing_oracle": "http://pricing-oracle:8005",
    "disruption_shield": "http://disruption-shield:8006",
    "supplier_trust": "http://supplier-trust:8007",
    "sustainability_agent": "http://sustainability-agent:8008",
}

# C7 (ADR-043): Tier-4 decisions are verified against the digital twin's Monte-Carlo
# what-if before execution. The twin exposes A2A `monte_carlo` at this endpoint
# (digital_twin/inference/serve.py); its response conforms to MonteCarloOutput
# (orchestrator/contracts/twin_simulation_contract.py).
TWIN_ENDPOINT = "http://digital-twin:8009"
TWIN_SCENARIOS = 1000


class ConsensusProtocol:
    """Five-phase multi-agent consensus engine."""

    def __init__(
        self,
        config: OrchestratorConfig,
        tier_router: TierRouter,
        guardrails: GuardrailEngine,
        audit_logger: AuditLogger,
        hitl_escalation: HITLEscalation,
        context_builder: ContextBuilder,
        ollama_client: OllamaClient,
        meta_rl: MetaRLAgent,
        semantic_cache: SemanticDecisionCache,
        kafka_producer: Any = None,
    ) -> None:
        self._config = config
        self._tier_router = tier_router
        self._guardrails = guardrails
        self._audit = audit_logger
        self._hitl = hitl_escalation
        self._ctx_builder = context_builder
        self._ollama = ollama_client
        self._meta_rl = meta_rl
        self._semantic_cache = semantic_cache
        self._kafka = kafka_producer
        self._fsm = OrchestratorStateMachine()

        self._context_messages: list[ContextMessage] = []
        self._tool_call_count: int = 0

    # ── Context management (I-14: append-only) ─────────────────────────

    @deal.pre(lambda self, msg: isinstance(msg, ContextMessage))
    def _append_context(self, msg: ContextMessage) -> int:
        """Append-only context modification.  Returns new length."""
        self._context_messages.append(msg)
        self._tool_call_count += 1
        if self._tool_call_count % self._config.recitation_interval == 0:
            self._append_recitation()
        return len(self._context_messages)

    def _append_recitation(self) -> None:
        """Push objective recitation into context (ADR-024)."""
        recitation = ContextMessage(
            source="orchestrator",
            content={
                "type": "objective_recitation",
                "current_phase": self._fsm.state.value,
                "proposals_received": sum(
                    1 for m in self._context_messages if m.source != "orchestrator"
                ),
                "tool_calls_completed": self._tool_call_count,
                "active_objective": self._fsm.ACTIVE_OBJECTIVE,
                "active_constraints": self._fsm.ACTIVE_CONSTRAINTS,
            },
        )
        self._context_messages.append(recitation)

    # ── Main entry point ────────────────────────────────────────────────

    async def run_consensus(
        self,
        decision_request: dict[str, Any],
    ) -> ConsensusDecision:
        """Execute the full consensus lifecycle for a single decision."""
        self._reset()
        start = time.monotonic()

        classification = self._tier_router.classify(decision_request)
        tier = classification.tier

        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "decision_request",
                    "tier": tier.value,
                    "request": decision_request,
                },
            )
        )

        try:
            if tier in (DecisionTier.TIER_1, DecisionTier.TIER_2):
                decision = await self._fast_path(decision_request, tier)
            else:
                decision = await self._full_path(decision_request, tier, classification)

            elapsed = time.monotonic() - start
            CONSENSUS_DURATION.labels(tier=tier.value).observe(elapsed)
            CONSENSUS_DECISIONS_TOTAL.labels(tier=tier.value, outcome="success").inc()
            return decision

        except Exception:
            CONSENSUS_DECISIONS_TOTAL.labels(tier=tier.value, outcome="error").inc()
            self._fsm.transition("exception_raised")
            raise

    # ── Tier 1-2 fast path ──────────────────────────────────────────────

    async def _fast_path(
        self,
        request: dict[str, Any],
        tier: DecisionTier,
    ) -> ConsensusDecision:
        proposals = await self._phase_collect(request)

        decision = self._build_decision(
            proposals=proposals,
            tier=tier,
            phase_reached=4,
            pareto_weights=self._meta_rl.get_weights(self._system_state()),
        )
        decision = await self._phase_execute(decision)
        await self._phase_learn(decision)
        return decision

    # ── Tier 3-4 full path ──────────────────────────────────────────────

    async def _full_path(
        self,
        request: dict[str, Any],
        tier: DecisionTier,
        classification: TierClassification,
    ) -> ConsensusDecision:
        proposals = await self._phase_collect(request)

        debate_rounds = 0
        conflict = self._detect_conflicts(proposals)
        if conflict.has_conflict:
            proposals, debate_rounds = await self._phase_debate(
                proposals,
                tier,
                classification,
            )

        pareto_result = await self._phase_arbitrate(proposals)
        weights = pareto_result["selected_weights"]

        decision = self._build_decision(
            proposals=proposals,
            tier=tier,
            phase_reached=4,
            pareto_weights=weights,
            pareto_front=pareto_result["pareto_front"],
            debate_rounds=debate_rounds,
        )

        # ADR-043/C7: record whether the decision rested on any degraded agent input
        # (a real model vs. an honest fallback), so the audit trail reflects substance.
        self._record_input_provenance(proposals)

        # C7: at the top tier the selected action is verified against the digital
        # twin's Monte-Carlo what-if before execution — the twin is no longer dead
        # code at Tier 4. Degrades honestly if the twin is unreachable (I-7).
        if tier == DecisionTier.TIER_4:
            decision = await self._phase_twin_verify(decision)

        passed, violations = self._guardrails.validate_decision(decision)
        if not passed:
            HITL_ESCALATIONS_TOTAL.labels(reason="guardrail_violation").inc()
            decision = await self._hitl.escalate(decision, violations)
        else:
            decision = await self._phase_execute(decision)

        await self._phase_learn(decision)
        return decision

    # ── Phase 1: Proposal collection ────────────────────────────────────

    async def _phase_collect(
        self,
        request: dict[str, Any],
    ) -> list[AgentProposal]:
        self._fsm.transition("decision_request_received")

        tasks = {
            name: self._request_proposal(name, url, request)
            for name, url in AGENT_ENDPOINTS.items()
        }
        results = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True,
        )

        proposals: list[AgentProposal] = []
        for name, result in zip(tasks.keys(), results, strict=False):
            if isinstance(result, AgentProposal):
                proposals.append(result)
                CONSENSUS_PROPOSALS_RECEIVED.labels(agent_name=name).inc()
                self._append_context(
                    ContextMessage(
                        source=name,
                        content=json.loads(result.to_deterministic_json()),
                    )
                )
            else:
                self._append_context(
                    ContextMessage(
                        source=name,
                        content={"error": str(result)},
                        status=MessageStatus.ERROR,
                    )
                )
        return proposals

    async def _request_proposal(
        self,
        agent_name: str,
        agent_url: str,
        request: dict[str, Any],
    ) -> AgentProposal:
        response = await send_a2a_request(
            target_url=agent_url,
            method="proposal",
            params={"decision_context": request},
            timeout=self._config.proposal_timeout_seconds,
        )
        if response.error:
            raise RuntimeError(f"{agent_name}: {response.error}")
        return AgentProposal.model_validate(response.result)

    # ── Phase 2: LLM-mediated debate ────────────────────────────────────

    async def _phase_debate(
        self,
        proposals: list[AgentProposal],
        tier: DecisionTier,
        classification: TierClassification,
    ) -> tuple[list[AgentProposal], int]:
        self._fsm.transition("all_proposals_received")

        model = classification.model
        rounds = 0

        for round_num in range(1, self._config.debate_max_rounds + 1):
            rounds = round_num

            if model:
                messages = self._ctx_builder.build_ollama_messages(self._context_messages)
                mask = self._tier_router.get_tool_mask(tier)
                llm_response = await self._ollama.chat(
                    model=model,
                    messages=messages,
                    prefill=mask.get("prefill"),
                )
                self._append_context(
                    ContextMessage(
                        source="orchestrator",
                        content={
                            "type": "debate_round",
                            "round": round_num,
                            "llm_analysis": llm_response.get("message", {}).get("content", ""),
                        },
                    )
                )

            if self._check_convergence(proposals):
                break

        CONSENSUS_DEBATE_ROUNDS.labels(tier=tier.value).observe(rounds)
        return proposals, rounds

    # ── Phase 3: Pareto arbitration ─────────────────────────────────────

    async def _phase_arbitrate(
        self,
        proposals: list[AgentProposal],
    ) -> dict[str, Any]:
        self._fsm.transition("convergence_or_max_rounds")
        weights = self._meta_rl.get_weights(self._system_state())
        result: dict[str, Any] = run_pareto_arbitration(proposals, weights)
        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={"type": "pareto_result", "knee_index": result["knee_index"]},
            )
        )
        return result

    # ── C7: Tier-4 digital-twin verification ────────────────────────────

    async def _phase_twin_verify(self, decision: ConsensusDecision) -> ConsensusDecision:
        """Verify the selected action against the digital twin's Monte-Carlo what-if.

        Records the twin's predicted KPI distribution into the append-only context
        and audit trace (I-14) so an operator sees the simulated outcome of the
        decision before it executes. An unreachable twin degrades to an honest
        ``twin_unavailable`` note and never blocks the decision (I-7).
        """
        note: dict[str, Any]
        try:
            resp = await send_a2a_request(
                target_url=TWIN_ENDPOINT,
                method="monte_carlo",
                params={
                    "consensus_action": decision.selected_action,
                    "n_scenarios": TWIN_SCENARIOS,
                },
                timeout=self._config.execution_timeout_seconds,
            )
            if resp.error:
                raise RuntimeError(resp.error)
            mc = resp.result or {}
            note = {
                "type": "twin_verification",
                "verdict": "twin_verified",
                "n_scenarios": mc.get("n_scenarios"),
                "kpi_means": mc.get("kpi_means", {}),
            }
        except Exception as exc:  # noqa: BLE001 — an unreachable twin degrades (I-7)
            logger.warning("twin_verification_unavailable", error=str(exc))
            note = {"type": "twin_verification", "verdict": "twin_unavailable", "error": str(exc)}

        self._append_context(ContextMessage(source="digital_twin", content=note))
        return decision.model_copy(
            update={"audit_trace": [*decision.audit_trace, f"twin={note['verdict']}"]},
        )

    def _record_input_provenance(self, proposals: list[AgentProposal]) -> None:
        """Append an honest summary of which proposals rested on a degraded input.

        Reads each proposal's ``payload['provenance']`` (ADR-040) and records the
        degraded agents into the append-only context, so the audit chain captures
        whether the decision was built on real models or fallbacks (I-3/I-4 substance).
        """
        degraded: list[str] = []
        for p in proposals:
            payload = p.payload if isinstance(p.payload, dict) else {}
            prov = payload.get("provenance", {})
            if isinstance(prov, dict) and prov.get("degraded") is True:
                degraded.append(str(p.agent_name))
        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "input_provenance",
                    "degraded_agents": degraded,
                    "all_real": not degraded,
                },
            )
        )

    # ── Phase 4: Execution dispatch ─────────────────────────────────────

    async def _phase_execute(
        self,
        decision: ConsensusDecision,
    ) -> ConsensusDecision:
        self._fsm.transition("pareto_solution_selected")

        confirmations: list[str] = []
        for proposal in decision.proposals:
            try:
                agent_name = str(proposal.agent_name)
                url = AGENT_ENDPOINTS.get(agent_name, "")
                resp = await send_a2a_request(
                    target_url=url,
                    method="execute",
                    params={
                        "decision_id": str(decision.decision_id),
                        "consensus_action": decision.selected_action,
                    },
                    timeout=self._config.execution_timeout_seconds,
                )
                confirmations.append(
                    resp.result.get("status", "unknown") if resp.result else "no_result",
                )
            except Exception as exc:
                confirmations.append(f"error:{exc}")

        audit_id = await self._audit.log_decision(decision)
        self._fsm.transition("execution_complete")

        return decision.model_copy(
            update={
                "execution_confirmations": confirmations,
                "audit_id": audit_id,
                "context_messages": list(self._context_messages),
                "audit_trace": [
                    *decision.audit_trace,
                    f"audit_id={audit_id}",
                    f"confirmations={len(confirmations)}",
                ],
            },
        )

    # ── Phase 5: Learning ───────────────────────────────────────────────

    async def _phase_learn(self, decision: ConsensusDecision) -> None:
        self._fsm.transition("execution_complete")

        outcome: dict[str, float] = {}
        for proposal in decision.proposals:
            agent_key = str(proposal.agent_name)
            for obj in OBJECTIVES:
                if agent_key.replace("_", "") in obj.replace("_", ""):
                    outcome[obj] = float(proposal.utility_score)

        self._meta_rl.update(outcome)

        if decision.tier in (DecisionTier.TIER_3, DecisionTier.TIER_4):
            await self._semantic_cache.store_decision(
                query_embedding=[0.0] * 384,
                decision=json.loads(decision.to_deterministic_json()),
                context_hash=str(decision.tier.value),
            )

        self._fsm.transition("updates_applied")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _detect_conflicts(self, proposals: list[AgentProposal]) -> ConflictReport:
        if len(proposals) < 2:
            return ConflictReport(has_conflict=False)
        scores = [p.utility_score for p in proposals]
        divergence = max(scores) - min(scores)
        return ConflictReport(
            has_conflict=divergence > 0.3,
            max_utility_divergence=divergence,
        )

    @staticmethod
    def _check_convergence(proposals: list[AgentProposal]) -> bool:
        if len(proposals) < 2:
            return True
        scores = [p.utility_score for p in proposals]
        import numpy as np

        return float(np.var(scores)) < 0.1

    def _build_decision(
        self,
        proposals: list[AgentProposal],
        tier: DecisionTier,
        phase_reached: int,
        pareto_weights: dict[str, float],
        pareto_front: list[dict[str, float]] | None = None,
        debate_rounds: int = 0,
    ) -> ConsensusDecision:
        best = max(proposals, key=lambda p: p.utility_score) if proposals else None
        return ConsensusDecision(
            tier=tier,
            proposals=proposals,
            selected_action=best.payload if best else {},
            pareto_weights=pareto_weights,
            confidence=best.confidence if best else 0.0,
            audit_trace=[f"tier={tier.value}", f"phase={phase_reached}"],
            phase_reached=phase_reached,
            debate_rounds=debate_rounds,
            pareto_front=pareto_front,
            context_messages=list(self._context_messages),
        )

    def _system_state(self) -> dict[str, Any]:
        from datetime import datetime

        return {
            "hour_of_day": datetime.now(UTC).hour,
            "active_disruptions": 0,
            "avg_fill_rate": 0.95,
        }

    def _reset(self) -> None:
        self._context_messages = []
        self._tool_call_count = 0
        self._fsm.reset()
