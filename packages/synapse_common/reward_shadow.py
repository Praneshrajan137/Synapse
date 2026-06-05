"""
SYNAPSE reward-weights shadow-mode helper (WS-3 §5, ADR-031).

Each agent's ``rewards.py`` accepts named-kwarg weights for backward
compatibility. Sprint 8 introduces ``agents/<name>/training/reward_config.py``
auto-generated from ``agents/<name>/spec.yaml``. At runtime, the reward
function compares the kwargs it received against the spec-generated
``WEIGHTS`` dict and increments
``synapse_reward_weight_divergence_total{agent, key}`` on any mismatch.

This is **shadow mode only** — the runtime kwargs still win. The Sprint-9
follow-up cuts over: spec becomes source-of-truth, kwargs become optional
overrides. See ADR-031 for the phased plan.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, TypeAlias

import structlog

from synapse_common.metrics import REWARD_WEIGHT_DIVERGENCE_TOTAL

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = structlog.get_logger(__name__)


_TOLERANCE = 1e-9
WeightValue: TypeAlias = float | int | None


def assert_shadow_match(agent: str, runtime: dict[str, float], spec: dict[str, float]) -> None:
    """Compare runtime kwarg weights to the spec-generated config.

    Logs a structured warning and increments
    ``synapse_reward_weight_divergence_total{agent, key}`` for each key whose
    value differs by more than ``_TOLERANCE``. Missing keys on either side
    count as divergences.
    """
    keys = sorted(set(runtime.keys()) | set(spec.keys()))
    for key in keys:
        runtime_value = runtime.get(key)
        spec_value = spec.get(key)
        if runtime_value is None or spec_value is None:
            REWARD_WEIGHT_DIVERGENCE_TOTAL.labels(agent=agent, key=key).inc()
            logger.warning(
                "reward_weight_divergence",
                agent=agent,
                key=key,
                runtime=runtime_value,
                spec=spec_value,
                reason="missing_in_one_side",
            )
            continue
        if not math.isfinite(runtime_value) or not math.isfinite(spec_value):
            REWARD_WEIGHT_DIVERGENCE_TOTAL.labels(agent=agent, key=key).inc()
            logger.warning(
                "reward_weight_divergence",
                agent=agent,
                key=key,
                runtime=runtime_value,
                spec=spec_value,
                reason="non_finite",
            )
            continue
        if abs(runtime_value - spec_value) > _TOLERANCE:
            REWARD_WEIGHT_DIVERGENCE_TOTAL.labels(agent=agent, key=key).inc()
            logger.warning(
                "reward_weight_divergence",
                agent=agent,
                key=key,
                runtime=runtime_value,
                spec=spec_value,
                reason="value_mismatch",
            )


def shadow_check(
    agent: str,
    spec_weights: dict[str, float],
    **runtime_kwargs: Any,  # noqa: ANN401
) -> None:
    """Convenience wrapper for the common pattern.

    Usage in ``rewards.py``::

        from agents.demand_prophet.training import reward_config
        shadow_check(
            "demand_prophet",
            reward_config.WEIGHTS,
            crps_weight=crps_weight,
            calibration_weight=calibration_weight,
            event_weight=event_weight,
        )
    """
    runtime: dict[str, float] = {
        key: float(value)
        for key, value in runtime_kwargs.items()
        if isinstance(value, (int, float))
    }
    assert_shadow_match(agent, runtime, {k: float(v) for k, v in spec_weights.items()})


def resolve_weights(
    agent: str,
    spec_weights: Mapping[str, float],
    **runtime_kwargs: WeightValue,
) -> dict[str, float]:
    """Resolve optional runtime reward kwargs against spec-generated defaults.

    ``None`` means "use the spec value" and therefore does not emit divergence.
    Any explicit numeric override still wins at runtime but is compared against
    the spec value, preserving ADR-031 shadow-mode observability.
    """
    spec = {key: float(value) for key, value in spec_weights.items()}
    resolved: dict[str, float] = {}

    for key, value in runtime_kwargs.items():
        if value is None:
            if key not in spec:
                assert_shadow_match(agent, {key: math.nan}, spec)
                raise KeyError(f"{agent} reward spec has no weight named {key!r}")
            resolved[key] = spec[key]
            continue
        resolved[key] = float(value)

    assert_shadow_match(agent, resolved, spec)
    return resolved
