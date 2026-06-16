"""ADR-051: the live Cognition Channel — the protocol streams real FSM phase
transitions to ``synapse.orchestrator.phase``, correlated to the final decision.

These prove the emission is honest (real run, not a stub), correlated (one id),
and best-effort (a missing/broken producer never blocks the decision — I-7).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from synapse_common.models import DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus.models import TierClassification
from orchestrator.consensus.protocol import ConsensusProtocol


def _protocol(kafka: Any = None) -> ConsensusProtocol:
    cfg = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
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
        kafka_producer=kafka,
    )


class TestEmitPhase:
    def test_noop_without_producer(self) -> None:
        proto = _protocol(kafka=None)
        proto._decision_id = uuid4()
        proto._emit_phase("collecting")  # must not raise

    def test_noop_without_decision_id(self) -> None:
        kafka = MagicMock()
        proto = _protocol(kafka=kafka)
        proto._decision_id = None
        proto._emit_phase("collecting")
        kafka.produce.assert_not_called()

    def test_produces_correlated_event(self) -> None:
        kafka = MagicMock()
        proto = _protocol(kafka=kafka)
        did = uuid4()
        proto._decision_id = did
        proto._city = "bengaluru"
        proto._emit_phase("debating", round_=2, agent_name="demand_prophet")
        kafka.produce.assert_called_once()
        args, kwargs = kafka.produce.call_args
        assert args[0] == "synapse.orchestrator.phase"
        payload = kwargs["value"]
        assert payload["type"] == "cognition_phase"
        assert payload["decision_id"] == str(did)
        assert payload["phase"] == "debating"
        assert payload["round"] == 2
        assert payload["agent_name"] == "demand_prophet"
        assert payload["city"] == "bengaluru"
        assert "ts" in payload
        assert kwargs["key"] == str(did)

    def test_swallows_producer_error(self) -> None:
        kafka = MagicMock()
        kafka.produce.side_effect = RuntimeError("broker down")
        proto = _protocol(kafka=kafka)
        proto._decision_id = uuid4()
        proto._emit_phase("executing")  # the decision must survive a dead broker


def test_build_decision_uses_run_decision_id() -> None:
    proto = _protocol()
    did = uuid4()
    proto._decision_id = did
    decision = proto._build_decision(
        proposals=[],
        tier=DecisionTier.TIER_1,
        phase_reached=4,
        pareto_weights={"demand_accuracy": 1.0},
    )
    assert decision.decision_id == did


@pytest.mark.asyncio
async def test_run_consensus_streams_correlated_phases(monkeypatch: pytest.MonkeyPatch) -> None:
    kafka = MagicMock()
    proto = _protocol(kafka=kafka)
    proto._tier_router.classify.return_value = TierClassification(
        tier=DecisionTier.TIER_1,
        confidence=0.95,
        reasons=["single_agent"],
        latency_budget_ms=100,
    )
    proto._audit.log_decision = AsyncMock(return_value=uuid4())

    async def fake_a2a(**kwargs: Any) -> SimpleNamespace:
        if kwargs.get("method") == "proposal":
            return SimpleNamespace(
                error=None,
                result={
                    "agent_name": "demand_prophet",
                    "decision_id": str(uuid4()),
                    "utility_score": 0.8,
                    "confidence": 0.85,
                    "justification_trace": ["forecast"],
                    "payload": {"action": "reorder"},
                    "tier": "tier_1",
                },
            )
        return SimpleNamespace(error=None, result={"status": "ok"})

    monkeypatch.setattr("orchestrator.consensus.protocol.send_a2a_request", fake_a2a)

    decision = await proto.run_consensus({"city": "bengaluru", "order_id": "o1"})

    calls = kafka.produce.call_args_list
    assert calls, "no phase events emitted"
    # Every emission targets the cognition topic …
    assert all(c.args[0] == "synapse.orchestrator.phase" for c in calls)
    phases = [c.kwargs["value"]["phase"] for c in calls]
    # … the fast path narrates collect → execute → learn …
    assert "collecting" in phases
    assert "executing" in phases
    assert "learning" in phases
    # … and every event correlates to the ONE final decision id.
    ids = {c.kwargs["value"]["decision_id"] for c in calls}
    assert ids == {str(decision.decision_id)}
