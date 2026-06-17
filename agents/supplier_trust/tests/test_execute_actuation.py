"""ADR-052 P3: supplier_trust.execute() publishes for real (kafka_published is honest)."""

from __future__ import annotations

from typing import Any

from agents.supplier_trust.a2a.handler import SupplierTrustA2AHandler


class FakeProducer:
    def __init__(self, fail: bool = False) -> None:
        self.produced: list[tuple[str, Any, str | None]] = []
        self._fail = fail

    def produce(self, topic: str, value: Any, key: str | None = None, headers: Any = None) -> None:
        if self._fail:
            raise RuntimeError("kafka down")
        self.produced.append((topic, value, key))


def _params(decision_id: str = "d1") -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "ratified_proposal": {"payload": {"supplier_id": "SUP-1", "trust_score": 0.72}},
    }


def test_execute_publishes_when_producer_present() -> None:
    producer = FakeProducer()
    handler = SupplierTrustA2AHandler(pipeline=object(), kafka_producer=producer)  # type: ignore[arg-type]
    res = handler.execute(_params())
    assert res["kafka_published"] is True  # a REAL produce, not a fabricated True
    assert producer.produced[0][0] == "synapse.supplier.score"


def test_execute_without_producer_is_honest_false() -> None:
    handler = SupplierTrustA2AHandler(pipeline=object(), kafka_producer=None)  # type: ignore[arg-type]
    res = handler.execute(_params())
    assert res["kafka_published"] is False


def test_execute_publish_failure_is_honest_false() -> None:
    handler = SupplierTrustA2AHandler(pipeline=object(), kafka_producer=FakeProducer(fail=True))  # type: ignore[arg-type]
    res = handler.execute(_params())
    assert res["kafka_published"] is False  # produce raised → honestly reported as not published
