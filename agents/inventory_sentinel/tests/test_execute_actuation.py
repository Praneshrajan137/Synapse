"""ADR-052 P3: inventory_sentinel.execute() actuates the world (no more status-dict stub)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agents.inventory_sentinel.a2a.handler import InventorySentinelA2AHandler

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction


class FakeActuator:
    def __init__(self, applied: bool = True) -> None:
        self.calls: list[WorldAction] = []
        self._applied = applied

    def apply(self, action: WorldAction) -> dict[str, Any]:
        self.calls.append(action)
        if self._applied:
            return {"applied": True, "result": {"effect": {"new_level": 999.0}}}
        return {"applied": False, "error": "world unreachable"}


class FakeProducer:
    def __init__(self) -> None:
        self.produced: list[tuple[str, Any, str | None]] = []

    def produce(self, topic: str, value: Any, key: str | None = None, headers: Any = None) -> None:
        self.produced.append((topic, value, key))


def _params(actions: list[dict[str, Any]], decision_id: str = "d1") -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "city": "bengaluru",
        "ratified_proposal": {"payload": {"actions": actions}},
    }


REORDER = {
    "store_id": "s", "sku_id": "sku_0", "action_type": "reorder", "quantity": 120.0,
    "safety_stock_multiplier": 1.5, "reorder_point": 40, "confidence": 0.8,
}
MARKDOWN = {
    "store_id": "s", "sku_id": "sku_1", "action_type": "markdown", "quantity": 5.0,
    "safety_stock_multiplier": 1.0, "reorder_point": 10, "confidence": 0.7,
}


def test_execute_actuates_world_and_publishes() -> None:
    actuator, producer = FakeActuator(), FakeProducer()
    handler = InventorySentinelA2AHandler(actuator=actuator, kafka_producer=producer)

    res = handler.execute(_params([REORDER, MARKDOWN]))

    assert res["status"] == "executed"
    assert res["reordered_skus"] == ["sku_0"]  # markdown is not a reorder → not actuated
    assert len(actuator.calls) == 1
    act = actuator.calls[0]
    assert act.kind.value == "reorder"
    assert act.city == "bengaluru"
    assert act.sku_id == "sku_0"
    assert act.params["quantity"] == 120.0
    # kafka_published is a REAL produce, not a bare True (the old stub).
    assert res["kafka_published"] is True
    assert producer.produced[0][0] == "synapse.inventory.reorder"


def test_execute_without_producer_is_honest_false() -> None:
    handler = InventorySentinelA2AHandler(actuator=FakeActuator(), kafka_producer=None)
    res = handler.execute(_params([REORDER]))
    assert res["reordered_skus"] == ["sku_0"]
    assert res["kafka_published"] is False  # honest: nothing was published


def test_execute_world_unavailable_degrades_without_crash() -> None:
    actuator, producer = FakeActuator(applied=False), FakeProducer()
    handler = InventorySentinelA2AHandler(actuator=actuator, kafka_producer=producer)
    res = handler.execute(_params([REORDER]))
    assert res["reordered_skus"] == []  # the world didn't apply it
    assert res["world_effects"][0]["applied"] is False
    assert res["kafka_published"] is False  # no successful reorder → nothing to publish
    # HONEST confirmation: a reorder that did not land is "diverged", so the outcome
    # scorer sees a real failure signal instead of the old always-"executed" stub.
    assert res["status"] == "diverged"


def test_handle_request_routes_execute() -> None:
    handler = InventorySentinelA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    resp = handler.handle_request(
        {"method": "execute", "id": "x", "params": _params([REORDER])}
    )
    assert resp["result"]["status"] == "executed"
    assert resp["result"]["reordered_skus"] == ["sku_0"]
