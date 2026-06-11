"""Degradation-posture computation (ADR-044 D4).

A pure read over two in-process registries — the per-city brownout
controllers and the shared circuit-breaker registry. Kept import-light
(no consensus/pymoo dependencies) so the posture surface is testable and
cheap enough for the frontend's 15s poll.
"""

from __future__ import annotations

from typing import Any

from synapse_common.breakers import BreakerState, all_breakers

from orchestrator.consensus.brownout import BrownoutLevel, registered_controllers


def compute_posture() -> dict[str, Any]:
    """Live degradation posture: brownout level per city + breaker states.

    ``degraded`` is True iff ANY city is shedding work or ANY dependency
    breaker is not CLOSED — the single bit the DegradedBanner keys on; the
    maps tell the operator *which* dependency is responsible.
    """
    brownout = {
        city: controller.current_level().name
        for city, controller in registered_controllers().items()
    }
    breakers = {name: breaker.state.value for name, breaker in all_breakers().items()}
    degraded = any(level != BrownoutLevel.NONE.name for level in brownout.values()) or any(
        state != BreakerState.CLOSED.value for state in breakers.values()
    )
    return {
        "brownout": brownout,
        "breakers": breakers,
        "degraded": degraded,
    }


__all__ = ["compute_posture"]
