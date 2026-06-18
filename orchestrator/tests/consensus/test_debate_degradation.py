"""Unit tests for honest LLM degradation in debate (R3.4, R4.1-R4.4).

These exercise ``ConsensusProtocol._phase_debate`` and its
``_run_debate_llm_analysis`` / ``_run_concession_round`` helpers in isolation,
covering the honest-degradation contract for the LLM-mediated debate phase:

* R4.1/R4.3 — when the LLM raises or times out, the round is recorded as
  ``degraded`` (with a ``degraded_reason``) and arbitration still proceeds
  (``_phase_debate`` returns the most-recent proposals rather than aborting).
* R4.4 — a single LLM invocation is retried at most once, for a total of 2
  attempts, before the round degrades.
* R4.2 — rule-based concession is LLM-independent and still runs while the LLM
  is unavailable.
* R3.4 — convergence stops debate before ``debate_max_rounds`` is reached.

The LLM (``self._ollama.chat``) and the A2A transport (``send_a2a_request``) are
mocked; everything else is the real protocol code.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_module
from orchestrator.consensus.models import TierClassification
from orchestrator.consensus.protocol import ConsensusProtocol

_MODEL = "test-debate-model"


def _build_protocol(*, debate_max_rounds: int = 3) -> ConsensusProtocol:
    cfg = OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
        debate_max_rounds=debate_max_rounds,
    )
    return ConsensusProtocol(
        config=cfg,
        tier_router=MagicMock(),
        guardrails=MagicMock(),
        audit_logger=MagicMock(),
        hitl_escalation=MagicMock(),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": {"demand_accuracy": 1.0}}),
        semantic_cache=MagicMock(**{"available": False}),
    )


def _classification(model: str | None = _MODEL) -> TierClassification:
    return TierClassification(
        tier=DecisionTier.TIER_3,
        confidence=0.9,
        reasons=["test"],
        model=model,
        latency_budget_ms=30_000,
    )


def _proposal(agent: AgentName, utility: float, decision_id: object) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=decision_id,  # type: ignore[arg-type]
        utility_score=utility,
        confidence=0.8,
        justification_trace=[f"{agent.value} proposal"],
        payload={"action": f"action_{agent.value}", "utility": utility},
        tier=DecisionTier.TIER_3,
    )


def _conflicting_proposals() -> list[AgentProposal]:
    """Two widely divergent proposals (variance >= 0.1 ⇒ they do NOT converge)."""
    decision_id = uuid4()
    return [
        _proposal(AgentName.DEMAND_PROPHET, 0.10, decision_id),
        _proposal(AgentName.PRICING_ORACLE, 0.90, decision_id),
    ]


def _a2a(result: dict[str, Any]) -> SimpleNamespace:
    """Mimic the ``A2AResponse`` shape consumed by ``_request_debate_response``."""
    return SimpleNamespace(error=None, result=result)


def _maintained_response(*_args: Any, **kwargs: Any) -> SimpleNamespace:
    return _a2a({"status": "maintained", "rationale": "within_band"})


def _degraded_rounds(proto: ConsensusProtocol) -> list[dict[str, Any]]:
    return [
        msg.content
        for msg in proto._context_messages
        if isinstance(msg.content, dict)
        and msg.content.get("type") == "debate_round"
        and msg.content.get("degraded") is True
    ]


class TestLLMRaisesDegradesAndProceeds:
    """R4.1/R4.3: an LLM error degrades the round; arbitration still proceeds."""

    @pytest.mark.asyncio
    async def test_llm_error_records_degraded_round_and_returns_proposals(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proto = _build_protocol(debate_max_rounds=1)
        proto._ollama.chat = AsyncMock(side_effect=RuntimeError("connection refused"))
        monkeypatch.setattr(
            protocol_module, "send_a2a_request", AsyncMock(side_effect=_maintained_response)
        )

        proposals = _conflicting_proposals()
        result, rounds = await proto._phase_debate(
            proposals, DecisionTier.TIER_3, _classification()
        )

        # Arbitration proceeds: the phase returns the most-recent proposals and does
        # not raise. With maintained responses the proposals are retained as-is.
        assert rounds == 1
        assert [p.agent_name for p in result] == [p.agent_name for p in proposals]

        # R4.1/R4.3: a degraded round is recorded with an honest failure reason.
        degraded = _degraded_rounds(proto)
        assert len(degraded) == 1
        assert degraded[0]["degraded_reason"] == "connection refused"
        assert degraded[0]["llm_analysis"] == ""


class TestLLMTimeoutAndAttemptBound:
    """R4.1/R4.4: per-attempt timeout + at most 2 LLM attempts before degrading."""

    @pytest.mark.asyncio
    async def test_timeout_yields_timeout_reason(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Shrink the per-attempt timeout so the slow LLM trips ``asyncio.wait_for``.
        monkeypatch.setattr(protocol_module, "_DEBATE_LLM_TIMEOUT_S", 0.01)
        proto = _build_protocol()

        async def _slow_chat(**_kwargs: Any) -> dict[str, Any]:
            await asyncio.sleep(1.0)
            return {"message": {"content": "never reached"}}

        proto._ollama.chat = _slow_chat

        content, reason = await proto._run_debate_llm_analysis(_MODEL, DecisionTier.TIER_3)

        assert content is None
        assert reason == "timeout"

    @pytest.mark.asyncio
    async def test_at_most_two_attempts(self) -> None:
        proto = _build_protocol()
        chat = AsyncMock(side_effect=RuntimeError("boom"))
        proto._ollama.chat = chat

        content, reason = await proto._run_debate_llm_analysis(_MODEL, DecisionTier.TIER_3)

        # R4.4: a single invocation is retried at most once → exactly 2 attempts.
        assert chat.call_count == protocol_module._DEBATE_LLM_MAX_ATTEMPTS == 2
        assert content is None
        assert reason == "boom"


class TestConcessionRunsWhileLLMDown:
    """R4.2: rule-based concession is LLM-independent and still revises proposals."""

    @pytest.mark.asyncio
    async def test_concession_applies_revision_with_llm_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proto = _build_protocol(debate_max_rounds=1)
        # LLM is down for the whole round.
        proto._ollama.chat = AsyncMock(side_effect=RuntimeError("llm offline"))
        # Schema validation is exercised by its own tests; here we isolate the
        # concession-while-degraded behavior, so accept the revised payload.
        monkeypatch.setattr(protocol_module, "validate_agent_payload", lambda *_a, **_k: None)

        revised_score = 0.50

        def _revised_response(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
            return _a2a(
                {
                    "status": "revised",
                    "utility_score": revised_score,
                    "payload": {"action": "revised", "utility": revised_score},
                }
            )

        monkeypatch.setattr(
            protocol_module, "send_a2a_request", AsyncMock(side_effect=_revised_response)
        )

        proposals = _conflicting_proposals()
        result, rounds = await proto._phase_debate(
            proposals, DecisionTier.TIER_3, _classification()
        )

        # The LLM was attempted and failed (degraded round recorded)...
        assert len(_degraded_rounds(proto)) == 1
        # ...yet concession still ran and replaced the proposals with the revision.
        assert rounds == 1
        assert [p.utility_score for p in result] == [revised_score, revised_score]

    @pytest.mark.asyncio
    async def test_concession_round_invoked_per_agent_while_degraded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proto = _build_protocol(debate_max_rounds=1)
        proto._ollama.chat = AsyncMock(side_effect=RuntimeError("llm offline"))
        a2a = AsyncMock(side_effect=_maintained_response)
        monkeypatch.setattr(protocol_module, "send_a2a_request", a2a)

        proposals = _conflicting_proposals()
        await proto._phase_debate(proposals, DecisionTier.TIER_3, _classification())

        # Concession invoked ``debate_respond`` once per proposal despite the LLM
        # being unavailable (R4.2).
        assert a2a.call_count == len(proposals)
        assert all(call.kwargs["method"] == "debate_respond" for call in a2a.call_args_list)


class TestConvergenceStopsDebate:
    """R3.4: convergence stops debate before ``debate_max_rounds``."""

    @pytest.mark.asyncio
    async def test_converged_proposals_stop_after_one_round(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proto = _build_protocol(debate_max_rounds=5)
        # LLM succeeds this time so the round is NOT degraded.
        proto._ollama.chat = AsyncMock(return_value={"message": {"content": "analysis"}})
        monkeypatch.setattr(
            protocol_module, "send_a2a_request", AsyncMock(side_effect=_maintained_response)
        )

        # Already-convergent proposals: variance(0.50, 0.55) ≈ 6.25e-4 < 0.1.
        decision_id = uuid4()
        proposals = [
            _proposal(AgentName.DEMAND_PROPHET, 0.50, decision_id),
            _proposal(AgentName.PRICING_ORACLE, 0.55, decision_id),
        ]

        result, rounds = await proto._phase_debate(
            proposals, DecisionTier.TIER_3, _classification()
        )

        # Debate stopped at round 1 (convergence), well short of the 5-round cap.
        assert rounds == 1
        assert [p.utility_score for p in result] == [0.50, 0.55]
        # The round ran normally (LLM available) — not degraded.
        assert _degraded_rounds(proto) == []
