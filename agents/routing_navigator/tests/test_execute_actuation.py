"""ADR-052 R5/R7 edge cases: routing_navigator.execute() honest divergence + degradation.

The handler maps each ratified route to one ``SET_POLICY`` ``WorldAction`` on the
``dispatch_speed`` lever. These tests cover the honest-divergence edges:

* a missing/unknown city is never routed to a World_Runtime (R5.9);
* a proposal with no actionable route reports no world effect (R5.10);
* a world that applies nothing is logged honestly with the agent name + reason (R7.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog.testing import capture_logs

from agents.routing_navigator.a2a.handler import RoutingNavigatorA2AHandler

if TYPE_CHECKING:
    from synapse_common.world.models import WorldAction


class FakeActuator:
    """In-memory actuator; ``applied`` toggles whether a non-empty effect lands."""

    def __init__(self, applied: bool = True) -> None:
        self.calls: list[WorldAction] = []
        self._applied = applied

    def apply(self, action: WorldAction) -> dict[str, Any]:
        self.calls.append(action)
        if self._applied:
            return {"applied": True, "result": {"effect": {"policy": dict(action.params)}}}
        return {"applied": False, "error": "world unreachable"}


class FakeProducer:
    def __init__(self) -> None:
        self.produced: list[tuple[str, Any, str | None]] = []

    def produce(self, topic: str, value: Any, key: str | None = None, headers: Any = None) -> None:
        self.produced.append((topic, value, key))


def _route(route_id: str = "11111111-1111-1111-1111-111111111111") -> dict[str, Any]:
    """A schema-valid route_plan sub-object (one actionable route)."""
    return {
        "route_id": route_id,
        "rider_id": "R-1",
        "store_id": "STORE_BLR_001",
        "stops": [{"order_id": "ORD-1"}],
        "total_distance_km": 5.0,
        "total_time_min": 240.0,
        "confidence": 0.8,
    }


def _params(
    routes: list[dict[str, Any]], decision_id: str = "d1", city: str | None = "bengaluru"
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "decision_id": decision_id,
        "ratified_proposal": {"payload": {"routes": routes}},
    }
    if city is not None:
        params["city"] = city
    return params


def _handler(actuator: FakeActuator | None = None) -> RoutingNavigatorA2AHandler:
    # Inject a stub pipeline: execute() never touches it, and this keeps the test
    # independent of the heavy solver/optional-dep construction.
    return RoutingNavigatorA2AHandler(
        pipeline=object(),  # type: ignore[arg-type]
        actuator=actuator or FakeActuator(),
        kafka_producer=FakeProducer(),
    )


def test_execute_missing_city_diverges() -> None:
    # R5.9: a missing city cannot be routed to a known World_Runtime.
    res = _handler().execute(_params([_route()], city=None))
    assert res["status"] == "diverged"
    assert res["reason"] == "unknown_city"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_no_actionable_item_diverges() -> None:
    # R5.10: an empty route set has no actionable item for the dispatch_speed lever.
    actuator = FakeActuator()
    res = _handler(actuator).execute(_params([]))
    assert res["status"] == "diverged"
    assert res["reason"] == "no_actionable_item"
    assert res["world_effects"] == []
    assert actuator.calls == []  # nothing was applied to the world


def test_execute_world_applies_nothing_logs_degradation() -> None:
    # R7.3: when the world applies no effect, the degradation is logged honestly with
    # the agent name and the reason, and the status is an honest "diverged".
    actuator = FakeActuator(applied=False)
    with capture_logs() as logs:
        res = _handler(actuator).execute(_params([_route()]))

    assert res["status"] == "diverged"
    assert res["reason"] == "no_effect"
    assert res["kafka_published"] is False
    assert len(actuator.calls) == 1  # the action was attempted on the world
    degraded = [e for e in logs if e.get("event") == "actuation_degraded"]
    assert degraded, "expected an actuation_degraded log entry"
    assert degraded[-1]["agent"] == "routing_navigator"
    assert degraded[-1]["reason"] == "no_effect"
