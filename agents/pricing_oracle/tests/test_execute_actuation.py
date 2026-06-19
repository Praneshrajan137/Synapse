"""ADR-052 R5/R7: pricing_oracle.execute() actuates the world (no more status-dict stub)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog.testing import capture_logs

from agents.pricing_oracle.a2a.handler import PricingOracleA2AHandler

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction


class FakeActuator:
    """In-memory actuator that records actions and reports a non-empty effect."""

    def __init__(self, applied: bool = True) -> None:
        self.calls: list[WorldAction] = []
        self._applied = applied

    def apply(self, action: WorldAction) -> dict[str, Any]:
        self.calls.append(action)
        if self._applied:
            price_mult = action.params["price_mult"]
            demand_mult = max(0.1, min(3.0, 1.0 / price_mult)) if price_mult > 0 else 1.0
            return {
                "applied": True,
                "result": {"effect": {"price_mult": price_mult, "demand_mult": demand_mult}},
            }
        return {"applied": False, "error": "world unreachable"}


class RaisingActuator:
    """Actuator whose apply() never raises but always reports no effect (honest degrade)."""

    def apply(self, action: WorldAction) -> dict[str, Any]:
        return {"applied": False, "error": "boom"}


class FakeProducer:
    def __init__(self) -> None:
        self.produced: list[tuple[str, Any, str | None]] = []

    def produce(self, topic: str, value: Any, key: str | None = None, headers: Any = None) -> None:
        self.produced.append((topic, value, key))


def _update(sku_id: str, multiplier: float) -> dict[str, Any]:
    """A schema-valid pricing_update sub-object."""
    base_price = 100.0
    return {
        "pricing_id": f"pid-{sku_id}",
        "sku_id": sku_id,
        "store_id": "STORE_BLR_001",
        "category": "staples",
        "base_price": base_price,
        "multiplier": multiplier,
        "final_price": base_price * multiplier,
        "is_essential": False,
        "elasticity_source": "correlation_fallback",
        "timestamp": "2025-01-01T00:00:00Z",
        "confidence": 0.8,
    }


def _params(
    updates: list[dict[str, Any]], decision_id: str = "d1", city: str | None = "bengaluru"
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "decision_id": decision_id,
        "ratified_proposal": {"payload": {"updates": updates}},
    }
    if city is not None:
        params["city"] = city
    return params


def test_execute_actuates_world_and_publishes() -> None:
    actuator, producer = FakeActuator(), FakeProducer()
    handler = PricingOracleA2AHandler(actuator=actuator, kafka_producer=producer)

    res = handler.execute(_params([_update("sku_0", 1.2), _update("sku_1", 0.9)]))

    assert res["status"] == "executed"
    assert len(actuator.calls) == 2  # one SET_PRICE_MULT per actionable update
    act = actuator.calls[0]
    assert act.kind.value == "set_price_mult"
    assert act.city == "bengaluru"
    assert act.sku_id == "sku_0"
    assert act.params["price_mult"] == 1.2
    # kafka_published is a REAL produce, not a bare True (the old stub).
    assert res["kafka_published"] is True
    assert producer.produced[0][0] == "synapse.pricing.update"
    # world_effects reflects the real applied effect.
    assert res["world_effects"][0]["applied"] is True
    assert "demand_mult" in res["world_effects"][0]["effect"]


def test_execute_rejects_schema_invalid_payload() -> None:
    actuator = FakeActuator()
    handler = PricingOracleA2AHandler(actuator=actuator, kafka_producer=FakeProducer())
    # multiplier <= 0 violates the pricing_update schema (INV-PO-002) → I-3 rejection,
    # never propagated to the world (R10.1).
    res = handler.execute(_params([_update("sku_0", 0.0)]))
    assert actuator.calls == []
    assert res["status"] == "diverged"
    assert res["reason"] == "invalid_payload"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_without_producer_is_honest_false() -> None:
    handler = PricingOracleA2AHandler(actuator=FakeActuator(), kafka_producer=None)
    res = handler.execute(_params([_update("sku_0", 1.1)]))
    assert res["status"] == "executed"
    assert res["kafka_published"] is False  # honest: nothing was published


def test_execute_world_unavailable_degrades_without_crash() -> None:
    actuator, producer = FakeActuator(applied=False), FakeProducer()
    handler = PricingOracleA2AHandler(actuator=actuator, kafka_producer=producer)
    res = handler.execute(_params([_update("sku_0", 1.3)]))
    assert res["status"] == "diverged"  # the world applied nothing
    assert res["reason"] == "no_effect"
    assert res["world_effects"][0]["applied"] is False
    assert res["kafka_published"] is False  # no applied update → nothing to publish


def test_execute_raising_actuator_degrades_honestly() -> None:
    handler = PricingOracleA2AHandler(actuator=RaisingActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([_update("sku_0", 1.4)]))
    assert res["status"] == "diverged"
    assert res["kafka_published"] is False


def test_execute_missing_city_diverges() -> None:
    handler = PricingOracleA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([_update("sku_0", 1.2)], city=None))
    assert res["status"] == "diverged"
    assert res["reason"] == "unknown_city"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_no_actionable_item_diverges() -> None:
    handler = PricingOracleA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([]))
    assert res["status"] == "diverged"
    assert res["reason"] == "no_actionable_item"
    assert res["world_effects"] == []


def test_execute_world_applies_nothing_logs_degradation() -> None:
    # R7.3: when the world applies no effect, the degradation is logged honestly with
    # the agent name and the reason, alongside the honest "diverged" status.
    actuator = FakeActuator(applied=False)
    handler = PricingOracleA2AHandler(actuator=actuator, kafka_producer=FakeProducer())
    with capture_logs() as logs:
        res = handler.execute(_params([_update("sku_0", 1.2)]))

    assert res["status"] == "diverged"
    assert res["reason"] == "no_effect"
    assert len(actuator.calls) == 1  # the action was attempted on the world
    degraded = [e for e in logs if e.get("event") == "actuation_degraded"]
    assert degraded, "expected an actuation_degraded log entry"
    assert degraded[-1]["agent"] == "pricing_oracle"
    assert degraded[-1]["reason"] == "no_effect"


def test_handle_request_routes_execute() -> None:
    handler = PricingOracleA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    resp = handler.handle_request(
        {"method": "execute", "id": "x", "params": _params([_update("sku_0", 1.2)])}
    )
    assert resp["result"]["status"] == "executed"
    assert resp["result"]["kafka_published"] is True
