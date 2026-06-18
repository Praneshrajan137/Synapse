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
import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

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
from synapse_common.schemas import SchemaValidationError, validate_agent_payload

from orchestrator.consensus.firehose_signals import emit_agent_signals
from orchestrator.consensus.models import ConflictReport, TierClassification
from orchestrator.consensus.pareto import (
    BindingSelection,
    run_pareto_arbitration,
    select_binding_action,
)
from orchestrator.state_machine import OrchestratorStateMachine

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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

# Precision for rounding floats embedded in the append-only `audit_trace`. Fixing
# the precision keeps the binding-arbitration trace byte-stable across repeated
# executions and separate process invocations (R2.1/R2.3).
_AUDIT_FLOAT_PRECISION = 9


def _canonical_json(value: Any) -> str:
    """Serialize ``value`` to a canonical, byte-stable JSON string (I-14, R2.3)."""
    return json.dumps(value, **_JSON_KWARGS)


def _round_floats(mapping: dict[str, float]) -> dict[str, float]:
    """Round a ``str -> float`` mapping to a fixed precision for stable audit output."""
    return {key: round(float(val), _AUDIT_FLOAT_PRECISION) for key, val in mapping.items()}


# R4.1/R4.4: the LLM-mediated debate analysis is best-effort. Each attempt is
# bounded to 30s (R4.1) and retried at most once for a total of 2 calls per round
# (R4.4); after the attempts are exhausted the round degrades honestly (I-7) while
# rule-based concession continues (R4.2).
_DEBATE_LLM_TIMEOUT_S = 30.0
_DEBATE_LLM_MAX_ATTEMPTS = 2

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

# Each agent's own meta-RL objective (matches pareto._AGENT_TO_OBJECTIVE). The old
# `_phase_learn` matched these with a substring test that silently NEVER fired
# ("inventorysentinel" is not a substring of "inventoryfillrate"), so the learning
# signal was effectively empty. ADR-052 uses this explicit map.
_AGENT_OBJECTIVE: dict[str, str] = {
    "demand_prophet": "demand_accuracy",
    "routing_navigator": "route_efficiency",
    "inventory_sentinel": "inventory_fill_rate",
    "freshness_guardian": "freshness_score",
    "pricing_oracle": "pricing_revenue",
    "disruption_shield": "disruption_readiness",
    "supplier_trust": "supplier_reliability",
    "sustainability_agent": "carbon_efficiency",
}

# C7 (ADR-043): Tier-4 decisions are verified against the digital twin's
# Monte-Carlo what-if before execution (orchestrator→twin is no longer dead
# code). The twin exposes A2A `monte_carlo` (digital_twin/inference/serve.py);
# its response conforms to MonteCarloOutput
# (orchestrator/contracts/twin_simulation_contract.py). Bounded + degrades
# honestly (I-7) so a slow/absent twin never stalls or 504s the decision.
TWIN_ENDPOINT = "http://digital-twin:8009"
# PR-5: tunable so the synchronous twin-verify cap (~8s on a small CPU VM) can be
# matched to the deployment's compute instead of a hardcoded 1000-scenario run.
TWIN_SCENARIOS = int(os.environ.get("SYNAPSE_TWIN_SCENARIOS", "1000"))


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
        world_observer: Callable[[str], Awaitable[dict[str, Any] | None]] | None = None,
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
        # ADR-052: perceive the realized world to learn from reality (not predicted
        # utility). Async (city -> WorldState dict | None); None ⇒ degrade honestly.
        self._world_observer = world_observer
        self._fsm = OrchestratorStateMachine()
        # ADR-051: correlation id for the live cognition stream. Generated at run
        # start so the phase events and the final ConsensusDecision share one id —
        # the live stream and the recorded Council Theater reconstruction line up.
        self._decision_id: UUID | None = None
        self._city: str | None = None

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

    # ── Live cognition telemetry (ADR-051) ──────────────────────────────

    def _emit_phase(
        self,
        phase: str,
        *,
        agent_name: str | None = None,
        round_: int | None = None,
        event: str | None = None,
    ) -> None:
        """Publish one FSM phase-transition event to ``synapse.orchestrator.phase``.

        This is the live Cognition Channel: the firehose streams the council's
        *reasoning* (collecting → debating → arbitrating → executing → learning),
        not only the final verdict, so the AUX grammar can show thinking/debating
        honestly from REAL events. Fire-and-forget and fully guarded — a missing
        or slow producer NEVER blocks or fails the decision (I-7). Correlated to
        the eventual ConsensusDecision by ``decision_id``.
        """
        if self._kafka is None or self._decision_id is None:
            return
        payload: dict[str, Any] = {
            "type": "cognition_phase",
            "decision_id": str(self._decision_id),
            "phase": phase,
            "ts": datetime.now(UTC).isoformat(),
        }
        if self._city is not None:
            payload["city"] = self._city
        if agent_name is not None:
            payload["agent_name"] = agent_name
        if round_ is not None:
            payload["round"] = round_
        if event is not None:
            payload["event"] = event
        try:
            self._kafka.produce(
                "synapse.orchestrator.phase",
                value=payload,
                key=str(self._decision_id),
            )
        except Exception as exc:  # noqa: BLE001 — telemetry is best-effort (I-7)
            logger.warning("cognition_phase_emit_failed", phase=phase, error=str(exc))

    # ── Main entry point ────────────────────────────────────────────────

    async def run_consensus(
        self,
        decision_request: dict[str, Any],
    ) -> ConsensusDecision:
        """Execute the full consensus lifecycle for a single decision."""
        self._reset()
        # ADR-051: stamp the correlation id + city up front so every phase event
        # carries them and the final decision reuses the same id.
        self._decision_id = uuid4()
        self._city = decision_request.get("city") if isinstance(decision_request, dict) else None
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
        proposals = await self._phase_collect(request, tier)

        fast_best = max(proposals, key=lambda p: p.utility_score) if proposals else None
        decision = self._build_decision(
            proposals=proposals,
            tier=tier,
            phase_reached=4,
            pareto_weights=self._meta_rl.get_weights(self._system_state()),
            fast_best=fast_best,
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
        proposals = await self._phase_collect(request, tier)

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

        # Binding Pareto arbitration (R1.1): apply the knee weights to the
        # per-objective proposal utilities and let that selection — not a raw
        # `utility_score` argmax — drive the ratified action on the full path.
        selection = select_binding_action(proposals, weights)
        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "binding_selection",
                    "selected_agent": selection.selected_agent,
                    "selected_index": selection.selected_index,
                    "weighted_scores": _round_floats(selection.weighted_scores),
                    "excluded_agents": list(selection.excluded_agents),
                    "tie_break_applied": selection.tie_break_applied,
                    "tie_break_reason": selection.tie_break_reason,
                },
            )
        )
        decision = self._build_decision(
            proposals=proposals,
            tier=tier,
            phase_reached=4,
            pareto_weights=weights,
            pareto_front=pareto_result["pareto_front"],
            debate_rounds=debate_rounds,
            selection=selection,
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
        tier: DecisionTier,
    ) -> list[AgentProposal]:
        self._fsm.transition("decision_request_received")
        self._emit_phase("collecting")

        tasks = {
            name: self._request_proposal(name, url, request, tier)
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
                self._emit_phase("collecting", agent_name=name, event="proposed")
            else:
                self._append_context(
                    ContextMessage(
                        source=name,
                        content={"error": str(result)},
                        status=MessageStatus.ERROR,
                    )
                )
                self._emit_phase("collecting", agent_name=name, event="failed")
        # Phase 1.5 (#64): event-source each agent's domain output onto its
        # firehose topic (ADR-038) so the FE pricing/demand/freshness surfaces
        # show live data. Pre-debate proposals = "what each agent proposed".
        # Best-effort (I-7) — never blocks consensus. (Coexists with the ADR-051
        # cognition phase events above.)
        emit_agent_signals(self._kafka, proposals)
        return proposals

    async def _request_proposal(
        self,
        agent_name: str,
        agent_url: str,
        request: dict[str, Any],
        tier: DecisionTier,
    ) -> AgentProposal:
        # PR-4 (P1.6): tier-aware timeout (I-10 SLAs: T1=2s … T4=120s) instead of a
        # single fixed proposal_timeout for every tier — so a fast tier fails fast on
        # a dead agent rather than waiting the worst-case budget.
        response = await send_a2a_request(
            target_url=agent_url,
            method="proposal",
            params={"decision_context": request},
            tier=tier,
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
            self._emit_phase("debating", round_=round_num)

            if model:
                content, degraded_reason = await self._run_debate_llm_analysis(model, tier)
                if degraded_reason is not None:
                    # R4.1/R4.3: the LLM is unavailable after the bounded attempts.
                    # DEGRADE the round honestly — record the failure reason — but
                    # do NOT break: concession is LLM-independent (R4.2), so the
                    # round still runs concession and the convergence check below,
                    # and arbitration proceeds with the most-recent proposals.
                    logger.warning(
                        "debate_llm_unavailable", round=round_num, reason=degraded_reason
                    )
                    self._append_context(
                        ContextMessage(
                            source="orchestrator",
                            content={
                                "type": "debate_round",
                                "round": round_num,
                                "llm_analysis": "",
                                "degraded": True,
                                "degraded_reason": degraded_reason,
                            },
                            status=MessageStatus.ERROR,
                        )
                    )
                else:
                    self._append_context(
                        ContextMessage(
                            source="orchestrator",
                            content={
                                "type": "debate_round",
                                "round": round_num,
                                "llm_analysis": content,
                                "degraded": False,
                            },
                        )
                    )

            # R3.1/R3.8: rule-based concession round. Invoke each agent's
            # `debate_respond` over A2A and replace a proposal ONLY with a
            # `"revised"` response whose payload re-validates schema-side;
            # otherwise retain the prior proposal. Concession is LLM-independent
            # (R4.2) so it runs whether or not an LLM model mediates this round.
            proposals = await self._run_concession_round(proposals, tier, round_num)

            # R3.4: stop once the (possibly revised) proposals converge.
            if self._check_convergence(proposals):
                break

        CONSENSUS_DEBATE_ROUNDS.labels(tier=tier.value).observe(rounds)
        return proposals, rounds

    async def _run_debate_llm_analysis(
        self,
        model: str,
        tier: DecisionTier,
    ) -> tuple[str | None, str | None]:
        """Run the best-effort, LLM-mediated analysis for one debate round.

        Each attempt is bounded to ``_DEBATE_LLM_TIMEOUT_S`` via ``asyncio.wait_for``
        (R4.1) and the call is retried at most once for a total of
        ``_DEBATE_LLM_MAX_ATTEMPTS`` attempts (R4.4). Returns ``(content, None)`` on
        success or ``(None, reason)`` when the LLM is unavailable after the attempts
        are exhausted, capturing the failure reason honestly (I-7) — ``"timeout"``
        on a timed-out attempt, otherwise the exception string.
        """
        messages = self._ctx_builder.build_ollama_messages(self._context_messages)
        mask = self._tier_router.get_tool_mask(tier)
        last_reason = "llm_unavailable"
        for attempt in range(1, _DEBATE_LLM_MAX_ATTEMPTS + 1):
            try:
                llm_response = await asyncio.wait_for(
                    self._ollama.chat(
                        model=model,
                        messages=messages,
                        prefill=mask.get("prefill"),
                    ),
                    timeout=_DEBATE_LLM_TIMEOUT_S,
                )
            except TimeoutError:
                last_reason = "timeout"
                logger.warning(
                    "debate_llm_timeout",
                    attempt=attempt,
                    timeout_s=_DEBATE_LLM_TIMEOUT_S,
                )
                continue
            except Exception as exc:  # noqa: BLE001 — LLM is best-effort (I-7)
                last_reason = str(exc) or exc.__class__.__name__
                logger.warning("debate_llm_error", attempt=attempt, error=last_reason)
                continue
            content = llm_response.get("message", {}).get("content", "")
            return str(content), None
        return None, last_reason

    async def _run_concession_round(
        self,
        proposals: list[AgentProposal],
        tier: DecisionTier,
        round_num: int,
    ) -> list[AgentProposal]:
        """Run one rule-based concession round and return the next round's proposals.

        Each conflicting agent's ``debate_respond`` is invoked over A2A (mirroring
        ``_request_proposal``); the orchestrator replaces an agent's prior proposal
        only with a ``"revised"`` response whose payload passes ``proto/domain/``
        schema validation (defense-in-depth re-validation, R3.1/R3.10/I-3), and
        otherwise retains the prior proposal. The round's revisions are appended to
        the append-only context (R3.8/I-14).
        """
        if len(proposals) < 2:
            return proposals

        round_utilities = [p.utility_score for p in proposals]
        tasks = [
            self._request_debate_response(
                str(p.agent_name),
                AGENT_ENDPOINTS.get(str(p.agent_name), ""),
                p,
                tier,
                round_num,
                round_utilities,
            )
            for p in proposals
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        revised: list[AgentProposal] = []
        revisions: list[dict[str, Any]] = []
        for prior, result in zip(proposals, results, strict=False):
            new_proposal, record = self._apply_debate_result(prior, result)
            revised.append(new_proposal)
            revisions.append(record)

        self._append_context(
            ContextMessage(
                source="orchestrator",
                content={
                    "type": "debate_revisions",
                    "round": round_num,
                    "revisions": revisions,
                },
            )
        )
        return revised

    async def _request_debate_response(
        self,
        agent_name: str,
        agent_url: str,
        proposal: AgentProposal,
        tier: DecisionTier,
        round_num: int,
        round_utilities: list[float],
    ) -> dict[str, Any]:
        """Invoke one agent's ``debate_respond`` over A2A (mirrors ``_request_proposal``).

        Passes the params the shared ``build_debate_response`` handler expects: the
        round number, the current round's utility scores, this agent's current
        ``utility_score``, and its current payload so the agent can honestly revise it.
        """
        response = await send_a2a_request(
            target_url=agent_url,
            method="debate_respond",
            params={
                "round_number": round_num,
                "round_utilities": round_utilities,
                "current_utility_score": proposal.utility_score,
                "current_payload": proposal.payload,
            },
            tier=tier,
        )
        if response.error:
            raise RuntimeError(f"{agent_name}: {response.error}")
        return response.result or {}

    def _apply_debate_result(
        self,
        prior: AgentProposal,
        result: dict[str, Any] | BaseException,
    ) -> tuple[AgentProposal, dict[str, Any]]:
        """Reconstruct the next-round proposal from one ``debate_respond`` result.

        Returns ``(proposal, record)`` where ``proposal`` is the honestly revised
        ``AgentProposal`` when the response is a schema-valid ``"revised"`` reply,
        otherwise the unchanged prior proposal (R3.1/R3.10). ``record`` is the
        append-only audit entry describing the outcome for this agent (R3.8).
        """
        agent_name = str(prior.agent_name)

        # An A2A failure honestly retains the prior proposal rather than fabricating
        # a revision (I-7).
        if isinstance(result, BaseException):
            return prior, {
                "agent": agent_name,
                "status": "error",
                "prior_utility": prior.utility_score,
                "error": str(result),
            }

        if result.get("status") != "revised":
            return prior, {
                "agent": agent_name,
                "status": "maintained",
                "prior_utility": prior.utility_score,
                "rationale": str(result.get("rationale", "")),
            }

        payload = result.get("payload")
        raw_score = result.get("utility_score")
        if not isinstance(payload, dict) or not isinstance(raw_score, (int, float)):
            return prior, {
                "agent": agent_name,
                "status": "maintained",
                "prior_utility": prior.utility_score,
                "rationale": "revision_missing_fields",
            }

        # R3.10/I-3: replace ONLY when the revised payload re-validates against the
        # agent's proto/domain schema; an invalid revision retains the prior position.
        try:
            validate_agent_payload(agent_name, payload)
        except SchemaValidationError:
            return prior, {
                "agent": agent_name,
                "status": "maintained",
                "prior_utility": prior.utility_score,
                "rationale": "revision_failed_schema",
                "schema_valid": False,
            }

        revised_score = float(raw_score)
        # Honest reconstruction: preserve agent identity/decision/tier/provenance and
        # update only the revised payload and utility_score (R3.7).
        new_proposal = prior.model_copy(
            update={"payload": payload, "utility_score": revised_score},
        )
        return new_proposal, {
            "agent": agent_name,
            "status": "revised",
            "prior_utility": prior.utility_score,
            "revised_utility": revised_score,
            "schema_valid": True,
        }

    # ── Phase 3: Pareto arbitration ─────────────────────────────────────

    async def _phase_arbitrate(
        self,
        proposals: list[AgentProposal],
    ) -> dict[str, Any]:
        self._fsm.transition("convergence_or_max_rounds")
        self._emit_phase("arbitrating")
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
                # Bounded at 8s: 1000-scenario Monte-Carlo exceeds the twin's 10s
                # SLA on the small CPU VM; cap the wait so a slow twin degrades to
                # an honest note instead of stalling Tier-4 past the gateway timeout.
                timeout=8.0,
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
            # ADR-044: the typed AgentProposal.provenance field is authoritative;
            # the payload["provenance"] dict remains as the pre-044 fallback so
            # proposals from older agents are still read honestly.
            if p.provenance is not None:
                if p.provenance.degraded:
                    degraded.append(str(p.agent_name))
                continue
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
        self._emit_phase("executing")

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
                        # ADR-052: an agent enacts ITS OWN ratified proposal on the world
                        # (real actuation), and needs the city to route to the right
                        # WorldRuntime. `self._city` was stamped at run_consensus start.
                        "city": self._city,
                        "ratified_proposal": json.loads(proposal.to_deterministic_json()),
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
        self._emit_phase("learning")

        # ADR-052: learn from the REALIZED world, not the predicted utility_score.
        # Perceive the post-execution world for this city; objectives the world can
        # observe (fill rate, spoilage, delivery) get the realized value, the rest fall
        # back to predicted utility. An unreachable world degrades to the old
        # predicted-utility path (I-7). This closes the loop Agent-audit flagged:
        # meta-RL previously learned only from its own predictions.
        world_state: dict[str, Any] | None = None
        if self._world_observer is not None and self._city is not None:
            try:
                world_state = await self._world_observer(self._city)
            except Exception as exc:  # noqa: BLE001 — a missing world degrades learning (I-7)
                logger.warning("learn_world_unavailable", error=str(exc))
                world_state = None

        self._meta_rl.update(self._build_learning_outcome(decision, world_state))

        if decision.tier in (DecisionTier.TIER_3, DecisionTier.TIER_4):
            await self._semantic_cache.store_decision(
                query_embedding=[0.0] * 384,
                decision=json.loads(decision.to_deterministic_json()),
                context_hash=str(decision.tier.value),
            )

        self._fsm.transition("updates_applied")

    def _build_learning_outcome(
        self,
        decision: ConsensusDecision,
        world_state: dict[str, Any] | None,
    ) -> dict[str, float]:
        """Map the realized world + proposals onto the 8 meta-RL objective scores.

        World-observable objectives use the REALIZED KPI; the rest fall back to the
        agent's predicted ``utility_score`` (no realized signal exists for them yet —
        honest, not fabricated). Pure given its inputs, so it is unit-tested directly.
        """
        outcome: dict[str, float] = {}
        if world_state is not None:
            if "fill_rate" in world_state:
                outcome["inventory_fill_rate"] = float(world_state["fill_rate"])
            if "spoilage_rate" in world_state:
                outcome["freshness_score"] = max(0.0, 1.0 - float(world_state["spoilage_rate"]))
            if "avg_delivery_min" in world_state:
                delivery = float(world_state["avg_delivery_min"])
                outcome["route_efficiency"] = max(0.0, min(1.0, 1.0 - delivery / 60.0))
        for proposal in decision.proposals:
            obj = _AGENT_OBJECTIVE.get(str(proposal.agent_name))
            if obj is not None and obj not in outcome:
                outcome[obj] = float(proposal.utility_score)
        return outcome

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
        *,
        selection: BindingSelection | None = None,
        fast_best: AgentProposal | None = None,
    ) -> ConsensusDecision:
        audit_trace = [f"tier={tier.value}", f"phase={phase_reached}"]

        if selection is not None:
            # Binding Pareto-knee selection drives the full-path action (R1.1/R1.2).
            # The raw `utility_score` argmax no longer selects here; it survives only
            # on the fast path via `fast_best` (R1.6).
            chosen = (
                proposals[selection.selected_index]
                if selection.selected_index is not None
                else None
            )
            selected_action = chosen.payload if chosen is not None else {}
            confidence = chosen.confidence if chosen is not None else 0.0

            # Append-only binding-arbitration audit (I-14, R2.2/R2.5): the knee
            # weight vector, every evaluated candidate's weighted score, the
            # selected identity, any exclusions, and the deterministic tie-break.
            audit_trace.append(
                f"knee_weights={_canonical_json(_round_floats(pareto_weights))}"
            )
            audit_trace.append(
                f"weighted_scores={_canonical_json(_round_floats(selection.weighted_scores))}"
            )
            audit_trace.append(f"binding_selected={selection.selected_agent}")
            if selection.excluded_agents:
                audit_trace.append(
                    f"binding_excluded={_canonical_json(selection.excluded_agents)}"
                )
            if selection.tie_break_applied:
                audit_trace.append(f"tie_break={selection.tie_break_reason}")
        else:
            # Fast path (Tier 1/2) retains raw `utility_score` argmax selection,
            # supplied by the caller as `fast_best` (R1.6).
            selected_action = fast_best.payload if fast_best is not None else {}
            confidence = fast_best.confidence if fast_best is not None else 0.0

        return ConsensusDecision(
            decision_id=self._decision_id or uuid4(),
            tier=tier,
            proposals=proposals,
            selected_action=selected_action,
            pareto_weights=pareto_weights,
            confidence=confidence,
            audit_trace=audit_trace,
            phase_reached=phase_reached,
            debate_rounds=debate_rounds,
            pareto_front=pareto_front,
            context_messages=list(self._context_messages),
        )

    def _system_state(self) -> dict[str, Any]:
        return {
            "hour_of_day": datetime.now(UTC).hour,
            "active_disruptions": 0,
            "avg_fill_rate": 0.95,
        }

    def _reset(self) -> None:
        self._context_messages = []
        self._tool_call_count = 0
        self._decision_id = None
        self._city = None
        self._fsm.reset()
