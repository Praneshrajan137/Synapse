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
from orchestrator.consensus.firehose_signals import METRICS_TOPIC, SIGNAL_CHANNELS
from orchestrator.consensus.models import TierClassification
from orchestrator.consensus.protocol import ConsensusProtocol

#: Mirrors the literal at `orchestrator/consensus/protocol.py:594`, which is where
#: `_emit_phase` names its topic. Declared here rather than imported because that module
#: states it inline and adding a production constant is not this repair's remit; declared
#: ONCE rather than repeated so the two tests that assert on it cannot drift apart.
PHASE_TOPIC = "synapse.orchestrator.phase"


def _protocol(kafka: Any = None) -> ConsensusProtocol:
    cfg = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
    return ConsensusProtocol(
        config=cfg,
        tier_router=MagicMock(),
        # ADR-054 D1: every tier now ratifies through `_ratify_and_dispatch`, so a
        # protocol that reaches dispatch needs a guardrail verdict to unpack. Task
        # 12.1a: it also reads the boundary in force, so the double states one - `0.0`,
        # imposing no floor, which is what its `(True, [])` verdict already says.
        guardrails=MagicMock(
            **{"validate_decision.return_value": (True, []), "confidence_threshold": 0.0},
        ),
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
        assert args[0] == PHASE_TOPIC
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
    # `classify` is declared `Callable[[dict[str, Any]], TierClassification]` and
    # `log_decision` is a real method, so reaching for `.return_value` on the first
    # was `attr-defined` and rebinding the second was `method-assign`. Both belong
    # to the mock, not to the declared type. `monkeypatch` replaces the attribute
    # outright and restores it afterwards, which is also the stronger test.
    monkeypatch.setattr(
        proto._tier_router,
        "classify",
        MagicMock(
            return_value=TierClassification(
                tier=DecisionTier.TIER_1,
                confidence=0.95,
                reasons=["single_agent"],
                latency_budget_ms=100,
            )
        ),
    )
    monkeypatch.setattr(proto._audit, "log_decision", AsyncMock(return_value=uuid4()))

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
    assert calls, "no events emitted at all"

    # PRECONDITION CORRECTION, NOT AN ASSERTION WEAKENING (R2.10).
    #
    # This block used to read `assert all(c.args[0] == PHASE_TOPIC for c in calls)`,
    # which claims the protocol emits to NO other topic. That stopped being true when
    # ADR-038's `emit_agent_signals` and ADR-053's `emit_agent_metrics` began sharing
    # this same producer (`protocol.py:1021` and `:1024`), so the assertion described a
    # subject that no longer exists. The SUBJECT moved; the STANDARD has not -- an
    # emission to a rogue topic must still fail this test.
    #
    # So the calls are PARTITIONED and the partition is asserted EXHAUSTIVE. Filtering
    # to the phase topic and stopping there was the tempting repair and it is the wrong
    # one: it discards exactly what the original assertion was protecting, leaving a
    # test that cannot fail on an unexpected emission.
    #
    # The permitted non-phase topics are DERIVED from the emitting module's own
    # declarations rather than transcribed here, so enabling either of the two follow-up
    # channels `firehose_signals.py` records as pending (`routing_navigator`,
    # `disruption_shield`) does not break this test, while an emission to a genuinely
    # undeclared topic still does.
    telemetry_topics = {METRICS_TOPIC} | {topic for topic, _ in SIGNAL_CHANNELS.values()}
    phase_calls = [call for call in calls if call.args[0] == PHASE_TOPIC]
    other_topics: set[str] = {str(call.args[0]) for call in calls if call.args[0] != PHASE_TOPIC}
    assert phase_calls, f"no cognition-phase events emitted; topics seen: {sorted(other_topics)}"
    assert other_topics <= telemetry_topics, (
        f"the protocol emitted to undeclared topic(s) {sorted(other_topics - telemetry_topics)}; "
        f"declared telemetry topics are {sorted(telemetry_topics)}"
    )
    # AND THE PARTITION MUST BE NON-TRIVIAL, because `set() <= anything` is vacuously
    # true: if the telemetry emitters ever stop firing here, the clause above silently
    # becomes an assertion that cannot fail, which is the defect class finding 26 caught
    # twice. `emit_agent_metrics` emits one event per proposal unconditionally whenever the
    # producer is present, and this run collects one proposal, so a non-empty set is a real
    # property of the run rather than an accident -- and its absence is worth failing on,
    # since it would mean the shared producer this partition exists to describe is gone.
    assert other_topics, (
        "no non-phase emission was observed, so the subset assertion above is vacuous; "
        "the shared-producer premise this partition describes no longer holds"
    )

    # The phase emissions are also the only ones carrying a `value=` payload:
    # `_emit_phase` passes it by KEYWORD while both telemetry emitters pass theirs
    # POSITIONALLY, so `c.kwargs["value"]` over the unfiltered list raised KeyError as
    # well. One defect, two symptoms; the partition above repairs both.
    phases = [call.kwargs["value"]["phase"] for call in phase_calls]
    # ... the fast path narrates collect -> execute -> learn ...
    assert "collecting" in phases
    assert "executing" in phases
    assert "learning" in phases
    # ... and every phase event correlates to the ONE final decision id.
    ids = {call.kwargs["value"]["decision_id"] for call in phase_calls}
    assert ids == {str(decision.decision_id)}
