"""ADR-052 R5/R7: demand_prophet.execute() actuates the world (no more status-dict stub).

The handler maps each ratified forecast to one ``SET_POLICY`` ``WorldAction`` on the
``demand_mult`` lever (a real demand-policy change) and event-sources only what the world
actually applied. Degradation (absent/raising actuator, missing city, no actionable
forecast, absent producer) returns an honest status — never a fabricated success.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog.testing import capture_logs

from agents.demand_prophet.a2a.handler import DemandProphetA2AHandler

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction


class FakeActuator:
    """In-memory actuator that records actions and reports a non-empty policy effect."""

    def __init__(self, applied: bool = True) -> None:
        self.calls: list[WorldAction] = []
        self._applied = applied

    def apply(self, action: WorldAction) -> dict[str, Any]:
        self.calls.append(action)
        if self._applied:
            policy = {k: float(v) for k, v in action.params.items()}
            return {"applied": True, "result": {"effect": {"policy": policy}}}
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


def _forecast(sku_id: str, point: float, lower: float, *, horizon: str = "1h") -> dict[str, Any]:
    """A schema-valid demand_forecast sub-object."""
    return {
        "sku_id": sku_id,
        "store_id": "STORE_BLR_001",
        "forecast_timestamp": "2025-01-01T00:00:00Z",
        "horizons": {horizon: point},
        "lower_90": {horizon: lower},
        "upper_90": {horizon: point * 1.5},
        "confidence": 0.8,
        "drift_detected": False,
    }


def _params(
    forecasts: list[dict[str, Any]], decision_id: str = "d1", city: str | None = "bengaluru"
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "decision_id": decision_id,
        "ratified_proposal": {
            "payload": {"forecasts": forecasts, "store_id": "STORE_BLR_001", "num_skus": 1}
        },
    }
    if city is not None:
        params["city"] = city
    return params


def test_execute_actuates_world_and_publishes() -> None:
    actuator, producer = FakeActuator(), FakeProducer()
    handler = DemandProphetA2AHandler(actuator=actuator, kafka_producer=producer)

    res = handler.execute(_params([_forecast("sku_0", 20.0, 10.0), _forecast("sku_1", 30.0, 30.0)]))

    assert res["status"] == "executed"
    assert len(actuator.calls) == 2  # one SET_POLICY per actionable forecast
    act = actuator.calls[0]
    assert act.kind.value == "set_policy"
    assert act.city == "bengaluru"
    assert act.sku_id == "sku_0"
    # demand_mult is the surge factor point/lower_90 = 20/10 = 2.0, within range (>= 0.01).
    assert act.params["demand_mult"] == 2.0
    # second forecast: point == lower → neutral 1.0.
    assert actuator.calls[1].params["demand_mult"] == 1.0
    # kafka_published is a REAL produce, not a bare True (the old stub).
    assert res["kafka_published"] is True
    assert producer.produced[0][0] == "synapse.demand.forecast"
    # world_effects reflects the real applied effect.
    assert res["world_effects"][0]["applied"] is True
    assert "effect" in res["world_effects"][0]


def test_demand_mult_clamped_to_lever_minimum() -> None:
    # point/lower would be tiny; the lever's accepted range floors it at 0.01.
    actuator = FakeActuator()
    handler = DemandProphetA2AHandler(actuator=actuator, kafka_producer=FakeProducer())
    handler.execute(_params([_forecast("sku_0", 0.001, 100.0)]))
    assert actuator.calls[0].params["demand_mult"] >= 0.01


def test_execute_rejects_schema_invalid_payload() -> None:
    actuator = FakeActuator()
    handler = DemandProphetA2AHandler(actuator=actuator, kafka_producer=FakeProducer())
    # An unknown horizon key violates the demand_forecast schema → I-3 rejection,
    # never propagated to the world (R10.1).
    bad = _forecast("sku_0", 10.0, 5.0)
    bad["horizons"] = {"99z": 10.0}
    res = handler.execute(_params([bad]))
    assert actuator.calls == []
    assert res["status"] == "diverged"
    assert res["reason"] == "invalid_payload"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_without_producer_is_honest_false() -> None:
    handler = DemandProphetA2AHandler(actuator=FakeActuator(), kafka_producer=None)
    res = handler.execute(_params([_forecast("sku_0", 20.0, 10.0)]))
    assert res["status"] == "executed"
    assert res["kafka_published"] is False  # honest: nothing was published


def test_execute_world_unavailable_degrades_without_crash() -> None:
    actuator, producer = FakeActuator(applied=False), FakeProducer()
    handler = DemandProphetA2AHandler(actuator=actuator, kafka_producer=producer)
    res = handler.execute(_params([_forecast("sku_0", 20.0, 10.0)]))
    assert res["status"] == "diverged"  # the world applied nothing
    assert res["reason"] == "no_effect"
    assert res["world_effects"][0]["applied"] is False
    assert res["kafka_published"] is False  # no applied forecast → nothing to publish


def test_execute_raising_actuator_degrades_honestly() -> None:
    handler = DemandProphetA2AHandler(actuator=RaisingActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([_forecast("sku_0", 20.0, 10.0)]))
    assert res["status"] == "diverged"
    assert res["kafka_published"] is False


def test_execute_missing_city_diverges() -> None:
    handler = DemandProphetA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([_forecast("sku_0", 20.0, 10.0)], city=None))
    assert res["status"] == "diverged"
    assert res["reason"] == "unknown_city"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_no_actionable_item_diverges() -> None:
    handler = DemandProphetA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([]))
    assert res["status"] == "diverged"
    assert res["reason"] == "no_actionable_item"
    assert res["world_effects"] == []


def test_execute_zero_point_forecast_not_actionable() -> None:
    handler = DemandProphetA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    res = handler.execute(_params([_forecast("sku_0", 0.0, 0.0)]))
    # A non-positive point demand is not an actionable item.
    assert res["status"] == "diverged"
    assert res["reason"] == "no_actionable_item"


def test_execute_world_applies_nothing_logs_degradation() -> None:
    # R7.3: when the world applies no effect, the degradation is logged honestly with
    # the agent name and the reason, alongside the honest "diverged" status.
    actuator = FakeActuator(applied=False)
    handler = DemandProphetA2AHandler(actuator=actuator, kafka_producer=FakeProducer())
    with capture_logs() as logs:
        res = handler.execute(_params([_forecast("sku_0", 20.0, 10.0)]))

    assert res["status"] == "diverged"
    assert res["reason"] == "no_effect"
    assert len(actuator.calls) == 1  # the action was attempted on the world
    degraded = [e for e in logs if e.get("event") == "actuation_degraded"]
    assert degraded, "expected an actuation_degraded log entry"
    assert degraded[-1]["agent"] == "demand_prophet"
    assert degraded[-1]["reason"] == "no_effect"


def test_handle_request_routes_execute() -> None:
    handler = DemandProphetA2AHandler(actuator=FakeActuator(), kafka_producer=FakeProducer())
    resp = handler.handle_request(
        {"method": "execute", "id": "x", "params": _params([_forecast("sku_0", 20.0, 10.0)])}
    )
    assert resp["result"]["status"] == "executed"
    assert resp["result"]["kafka_published"] is True
