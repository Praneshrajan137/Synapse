"""Honest No-Op execute() tests for the Sustainability Agent (ADR-052, R6.2/R6.5/R7.2).

carbon_efficiency has no natural world-mutation lever, so execute() must never report
``"executed"``: it returns status ``"diverged"`` with empty ``world_effects`` and
``reason="no_carbon_lever"`` while still performing one honest Kafka event-source.
"""

from __future__ import annotations

from typing import Any

from agents.sustainability_agent.a2a.handler import (
    CARBON_TOPIC,
    SustainabilityAgentA2AHandler,
)


class FakeProducer:
    """Records produces; optionally fails to exercise honest degradation."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.produced: list[tuple[str, Any, str | None]] = []

    def produce(self, topic: str, *, value: Any, key: str | None = None) -> None:
        if self.fail:
            raise RuntimeError("kafka unavailable")
        self.produced.append((topic, value, key))


def _params() -> dict[str, Any]:
    return {"decision_id": "dec-1", "city": "bengaluru", "ratified_proposal": {"payload": {}}}


def test_execute_is_honest_noop_never_executed() -> None:
    producer = FakeProducer()
    handler = SustainabilityAgentA2AHandler(pipeline=object(), kafka_producer=producer)  # type: ignore[arg-type]

    res = handler.execute(_params())

    assert res["status"] == "diverged"  # never "executed" (R6.2)
    assert res["status"] != "executed"
    assert res["world_effects"] == []  # no fabricated effect (R6.5)
    assert res["reason"] == "no_carbon_lever"
    assert res["agent"] == "sustainability_agent"
    assert res["decision_id"] == "dec-1"
    assert res["city"] == "bengaluru"


def test_execute_event_sources_honestly() -> None:
    producer = FakeProducer()
    handler = SustainabilityAgentA2AHandler(pipeline=object(), kafka_producer=producer)  # type: ignore[arg-type]

    res = handler.execute(_params())

    assert res["kafka_published"] is True  # a REAL produce, not a fabricated True
    assert producer.produced[0][0] == CARBON_TOPIC
    # The honest record carries the no-op outcome, not a fabricated world change.
    assert producer.produced[0][1]["reason"] == "no_carbon_lever"
    assert producer.produced[0][1]["world_effects"] == []


def test_execute_without_producer_is_honest_false() -> None:
    handler = SustainabilityAgentA2AHandler(pipeline=object(), kafka_producer=None)  # type: ignore[arg-type]

    res = handler.execute(_params())

    assert res["status"] == "diverged"
    assert res["kafka_published"] is False  # honest: nothing was published


def test_execute_publish_failure_is_honest_false() -> None:
    handler = SustainabilityAgentA2AHandler(
        pipeline=object(),  # type: ignore[arg-type]
        kafka_producer=FakeProducer(fail=True),
    )

    res = handler.execute(_params())

    assert res["status"] == "diverged"  # the no-op still diverges
    assert res["kafka_published"] is False  # produce raised → honestly reported as not published


def test_handle_request_routes_execute() -> None:
    handler = SustainabilityAgentA2AHandler(pipeline=object(), kafka_producer=FakeProducer())  # type: ignore[arg-type]

    resp = handler.handle_request({"method": "execute", "id": "x", "params": _params()})

    assert resp["result"]["status"] == "diverged"
    assert resp["result"]["reason"] == "no_carbon_lever"
