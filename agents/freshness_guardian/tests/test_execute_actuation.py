"""ADR-052 R5/R6/R7 edge cases: freshness_guardian.execute() honest divergence.

freshness_guardian has no direct spoilage-reduction lever, so it raises ``dispatch_speed``
via the closest ``SET_POLICY`` lever (R6.3) only for spoilage-relevant alerts
(``markdown_applied=True``). These tests cover the honest edges:

* a missing/unknown city is never routed to a World_Runtime (R5.9);
* a proposal with no spoilage-relevant alert is an Honest No-Op (R5.10/R6.1);
* a world that applies nothing is logged honestly with the agent name + reason (R7.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog.testing import capture_logs

from agents.freshness_guardian.a2a.handler import FreshnessGuardianA2AHandler

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


def _alert(
    sku_id: str = "sku_0", *, markdown_applied: bool = True, markdown_pct: float = 20.0
) -> dict[str, Any]:
    """A schema-valid freshness_alert sub-object."""
    return {
        "alert_id": "11111111-1111-1111-1111-111111111111",
        "store_id": "STORE_BLR_001",
        "sku_id": sku_id,
        "days_to_expiry": 2.0,
        "quality_score": 0.7,
        "markdown_applied": markdown_applied,
        "markdown_pct": markdown_pct,
        "fssai_compliant": True,
        "timestamp": "2025-01-01T00:00:00Z",
        "confidence": 0.8,
    }


def _params(
    alerts: list[dict[str, Any]], decision_id: str = "d1", city: str | None = "bengaluru"
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "decision_id": decision_id,
        "ratified_proposal": {"payload": {"alerts": alerts, "store_id": "STORE_BLR_001"}},
    }
    if city is not None:
        params["city"] = city
    return params


def _handler(actuator: FakeActuator | None = None) -> FreshnessGuardianA2AHandler:
    # Inject a stub pipeline: execute() never touches it, keeping the test independent
    # of the heavy survival-model / optional-dep (lifelines) construction.
    return FreshnessGuardianA2AHandler(
        pipeline=object(),  # type: ignore[arg-type]
        actuator=actuator or FakeActuator(),
        kafka_producer=FakeProducer(),
    )


def test_execute_missing_city_diverges() -> None:
    # R5.9: a missing city cannot be routed to a known World_Runtime.
    res = _handler().execute(_params([_alert()], city=None))
    assert res["status"] == "diverged"
    assert res["reason"] == "unknown_city"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_no_spoilage_relevant_alert_is_honest_noop() -> None:
    # R5.10/R6.1: alerts without markdown_applied are not actionable for the lever →
    # Honest No-Op (diverged, empty effects, nothing applied to the world).
    actuator = FakeActuator()
    res = _handler(actuator).execute(_params([_alert(markdown_applied=False)]))
    assert res["status"] == "diverged"
    assert res["reason"] == "no_actionable_item"
    assert res["world_effects"] == []
    assert actuator.calls == []


def test_execute_empty_alerts_diverges() -> None:
    # R5.10: an empty alert set has no actionable item.
    res = _handler().execute(_params([]))
    assert res["status"] == "diverged"
    assert res["reason"] == "no_actionable_item"
    assert res["world_effects"] == []


def test_execute_world_applies_nothing_logs_degradation() -> None:
    # R7.3: when the world applies no effect, the degradation is logged honestly with
    # the agent name and the reason, and the status is an honest "diverged".
    actuator = FakeActuator(applied=False)
    with capture_logs() as logs:
        res = _handler(actuator).execute(_params([_alert()]))

    assert res["status"] == "diverged"
    assert res["reason"] == "no_effect"
    assert res["kafka_published"] is False
    assert len(actuator.calls) == 1  # the action was attempted on the world
    degraded = [e for e in logs if e.get("event") == "actuation_degraded"]
    assert degraded, "expected an actuation_degraded log entry"
    assert degraded[-1]["agent"] == "freshness_guardian"
    assert degraded[-1]["reason"] == "no_effect"
