"""ADR-052 R5/R7 edge cases: disruption_shield.execute() honest divergence + degradation.

The handler maps the ratified alert's ``alert_level`` (1-10) to a ``lead_time_mult`` lever
and applies one ``SET_POLICY`` ``WorldAction``. These tests cover the honest edges:

* a missing/unknown city is never routed to a World_Runtime (R5.9);
* an empty/absent proposal yields no actionable item and reports no world effect (R5.10);
* a world that applies nothing is logged honestly with the agent name + reason (R7.3).

Note: a schema-valid ``disruption_alert`` always carries an ``alert_level`` >= 1, so the
only way to reach "no actionable item" through the handler is an empty/absent proposal,
which the I-3 schema check rejects honestly before actuation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog.testing import capture_logs

from agents.disruption_shield.a2a.handler import DisruptionShieldA2AHandler

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


def _alert(alert_level: int = 5) -> dict[str, Any]:
    """A schema-valid disruption_alert payload (one actionable mitigation)."""
    return {
        "alert_id": "11111111-1111-1111-1111-111111111111",
        "alert_level": alert_level,
        "anomaly_scores": {
            "isolation_forest": 0.6,
            "lstm_autoencoder": 0.5,
            "gnn_structural": 0.4,
            "ensemble_weighted": 0.55,
        },
        "affected_nodes": ["node-1"],
        "disruption_type": "weather",
        "playbook_id": "PB-1",
        "playbook_actions": "reroute",
        "reasoning_chain": "anomaly detected",
        "timestamp": "2025-01-01T00:00:00Z",
        "confidence": 0.8,
    }


def _params(
    payload: dict[str, Any], decision_id: str = "d1", city: str | None = "bengaluru"
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "decision_id": decision_id,
        "ratified_proposal": {"payload": payload},
    }
    if city is not None:
        params["city"] = city
    return params


def _handler(actuator: FakeActuator | None = None) -> DisruptionShieldA2AHandler:
    # Inject a stub pipeline: execute() never touches it, keeping the test independent
    # of the heavy detector / optional-dep construction.
    return DisruptionShieldA2AHandler(
        pipeline=object(),  # type: ignore[arg-type]
        actuator=actuator or FakeActuator(),
        kafka_producer=FakeProducer(),
    )


def test_execute_missing_city_diverges() -> None:
    # R5.9: a missing city cannot be routed to a known World_Runtime.
    res = _handler().execute(_params(_alert(), city=None))
    assert res["status"] == "diverged"
    assert res["reason"] == "unknown_city"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False


def test_execute_empty_proposal_has_no_actionable_item() -> None:
    # R5.10: an empty proposal carries no actionable mitigation; the handler diverges
    # honestly and applies nothing to the world.
    actuator = FakeActuator()
    res = _handler(actuator).execute(_params({}))
    assert res["status"] == "diverged"
    assert res["world_effects"] == []
    assert res["kafka_published"] is False
    assert actuator.calls == []  # nothing was applied to the world


def test_execute_world_applies_nothing_logs_degradation() -> None:
    # R7.3: when the world applies no effect, the degradation is logged honestly with
    # the agent name and the reason, and the status is an honest "diverged".
    actuator = FakeActuator(applied=False)
    with capture_logs() as logs:
        res = _handler(actuator).execute(_params(_alert()))

    assert res["status"] == "diverged"
    assert res["reason"] == "no_effect"
    assert res["kafka_published"] is False
    assert len(actuator.calls) == 1  # the mitigation was attempted on the world
    degraded = [e for e in logs if e.get("event") == "actuation_degraded"]
    assert degraded, "expected an actuation_degraded log entry"
    assert degraded[-1]["agent"] == "disruption_shield"
    assert degraded[-1]["reason"] == "no_effect"
