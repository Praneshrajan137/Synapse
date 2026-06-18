"""Shared real-actuation helpers for agent ``execute()`` (ADR-052, R5/R6/R7).

The lever agents (``pricing_oracle``, ``demand_prophet``, ``routing_navigator``,
``disruption_shield``, ``freshness_guardian``) all convert their ratified proposal into
one ``WorldAction`` per actionable item, apply it through the injected
:class:`~synapse_common.world.actuator.Actuator`, and report the result under the same
*uniform honest status rule*. Centralising that rule here means the handlers cannot drift
apart (a correctness + maintenance risk) and gives one place to test the honesty contract.

Honest by construction (I-7): every degradation path returns a truthful status
(``"diverged"``), reports the *actual* world effect (empty when none was applied), logs
the degradation with the agent name and reason (R7.3), and never raises into the caller.

Uniform honest status rule (R5.6 / R5.9 / R5.10 / R6.4 / R7.1):

* ``"executed"`` iff for at least one actionable item the actuator returned ``applied=True``
  **and** a non-empty, non-error ``effect``.
* ``"diverged"`` otherwise — a missing/unknown city, an absent actuator, an ``apply`` that
  landed no non-empty effect, or a proposal with no actionable item for the agent's lever.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from synapse_common.world.actuator import WorldActuator
from synapse_common.world.models import WorldAction, WorldActionKind

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from synapse_common.world.actuator import Actuator

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ActuationItem:
    """One actionable item: a ratified lever value applied as a single ``WorldAction``."""

    action_id: str
    params: dict[str, float]
    sku_id: str | None = None
    store_id: str | None = None


@dataclass(frozen=True)
class ActuationOutcome:
    """The honest outcome of applying a proposal's actionable items to the world."""

    status: str  # "executed" | "diverged"
    world_effects: list[dict[str, Any]]
    applied_count: int
    attempted: int
    reason: str


def effect_of(actuator_result: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the world's *actual* effect dict from an actuator result (``{}`` when none).

    The actuator returns ``{"applied": bool, "result": {...}}`` where ``result`` is the
    twin's ``apply_action`` envelope ``{"status": ..., "effect": {...}}``. We dig out the
    nested ``effect`` and never fabricate one.
    """
    result = actuator_result.get("result")
    if isinstance(result, dict):
        effect = result.get("effect")
        if isinstance(effect, dict):
            return effect
    return {}


def effect_applied(actuator_result: Mapping[str, Any]) -> bool:
    """True iff the actuator applied a non-empty, non-error effect (the uniform rule)."""
    if not actuator_result.get("applied"):
        return False
    effect = effect_of(actuator_result)
    return bool(effect) and "error" not in effect


def resolve_actuator(actuator: Actuator | None) -> Actuator:
    """Default to the production :class:`WorldActuator` when none is injected."""
    return actuator if actuator is not None else WorldActuator()


def actuate_items(
    *,
    agent_name: str,
    kind: WorldActionKind,
    city: str,
    decision_id: str,
    items: Sequence[ActuationItem],
    actuator: Actuator | None,
) -> ActuationOutcome:
    """Apply one ``WorldAction`` per actionable item and derive the uniform honest status.

    Args:
        agent_name: Canonical agent short-name, used only for honest degradation logging.
        kind: The agent's mapped :class:`WorldActionKind` lever.
        city: The city routed from the execute request (R5.8). A missing city diverges.
        decision_id: Correlates each action to its decision.
        items: The actionable items extracted from the ratified proposal (R5.1).
        actuator: The injected actuator; ``None`` degrades honestly (R7.1).

    Returns:
        An :class:`ActuationOutcome` whose ``status`` follows the uniform honest rule and
        whose ``world_effects`` always reflects the real applied effect (empty when none).
    """
    # R5.9: a missing city cannot be routed to a known World_Runtime → no fabricated effect.
    if not city:
        logger.warning("actuation_degraded", agent=agent_name, reason="unknown_city")
        return ActuationOutcome("diverged", [], 0, 0, "unknown_city")

    # R5.10: nothing actionable for this agent's lever → honest no-effect, never "executed".
    if not items:
        return ActuationOutcome("diverged", [], 0, 0, "no_actionable_item")

    # R7.1: an absent actuator degrades honestly instead of fabricating a world effect.
    if actuator is None:
        logger.warning("actuation_degraded", agent=agent_name, reason="actuator_unavailable")
        return ActuationOutcome("diverged", [], 0, len(items), "actuator_unavailable")

    world_effects: list[dict[str, Any]] = []
    applied_count = 0
    for item in items:
        result = actuator.apply(
            WorldAction(
                action_id=item.action_id,
                kind=kind,
                city=city,
                sku_id=item.sku_id,
                store_id=item.store_id,
                params=item.params,
                decision_id=decision_id,
            )
        )
        landed = effect_applied(result)
        world_effects.append(
            {**item.params, "sku_id": item.sku_id, "applied": landed, "effect": effect_of(result)}
        )
        if landed:
            applied_count += 1

    # Uniform rule: "executed" iff a non-empty effect was actually applied, else "diverged".
    if applied_count > 0:
        return ActuationOutcome("executed", world_effects, applied_count, len(items), "ok")
    logger.warning("actuation_degraded", agent=agent_name, reason="no_effect")
    return ActuationOutcome("diverged", world_effects, 0, len(items), "no_effect")


def honest_produce(
    producer: Any,
    topic: str,
    *,
    value: Mapping[str, Any],
    key: str | None,
    agent_name: str,
) -> bool:
    """Event-source a result; return ``True`` only if a produce actually happened (R5.7/R7.2).

    Mirrors the actuator's honesty premise for Kafka: an absent producer or a failing
    ``produce`` (outage / timeout) yields a truthful ``False`` and is logged with the agent
    name and reason; it never propagates an exception into the caller (I-7, R7.3).
    """
    if producer is None:
        return False
    try:
        producer.produce(topic, value=dict(value), key=key)
    except Exception as exc:  # noqa: BLE001 — a Kafka outage degrades honestly (I-7)
        logger.warning("publish_failed", agent=agent_name, topic=topic, error=str(exc))
        return False
    return True
