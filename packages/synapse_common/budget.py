"""SYNAPSE tier-budget decorator (Sprint 8 §M13 + Sprint 9 §M1, ADR-032).

``@tier_budget(ms=100, on_exceed="brownout", city="bengaluru")`` wraps a
Tier-1 handler with a stopwatch. If wall-clock latency exceeds the
budget the decorator increments
``synapse_tier_budget_exceeded_total{tier}`` and emits a structured
warning.

Sprint 9 unblocks ``on_exceed="brownout"``: the decorator now consults
``orchestrator.consensus.brownout.get_controller(city)`` and calls
``set_manual_override(BrownoutLevel.SHED_T4)`` on a sustained breach.
The registry returns ``None`` when no controller is registered yet
(startup race) — the decorator no-ops with a structured warning in
that window.

Both sync and async callables are supported; the decorator picks the
right wrapper via ``asyncio.iscoroutinefunction``.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

from synapse_common.metrics import TIER_BUDGET_EXCEEDED_TOTAL
from synapse_common.models import DecisionTier

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

T = TypeVar("T")


_VALID_ACTIONS = {"metric_only", "brownout"}


def tier_budget(
    ms: float,
    tier: DecisionTier | str = DecisionTier.TIER_1,
    on_exceed: str = "metric_only",
    city: str | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator factory.

    Args:
        ms: budget in milliseconds.
        tier: the tier this handler belongs to (used as metric label).
        on_exceed:
            - ``"metric_only"``: increment counter + log (Sprint 8 default).
            - ``"brownout"``: Sprint 9 — calls
              ``BrownoutController.set_manual_override(SHED_T4)`` for the
              registered ``city`` on a single breach. Successive breaches
              escalate (T4 → T4_T3 → LLM_ONLY).
        city: required when ``on_exceed="brownout"``. The decorator looks
            up ``orchestrator.consensus.brownout.get_controller(city)``.
            When the lookup returns ``None`` (registry not yet wired) the
            decorator no-ops with a structured warning.
    """
    if on_exceed not in _VALID_ACTIONS:
        raise ValueError(f"on_exceed must be one of {_VALID_ACTIONS}; got {on_exceed!r}")
    if on_exceed == "brownout" and city is None:
        raise ValueError("on_exceed='brownout' requires city=<bengaluru|mumbai>")

    tier_value = tier.value if isinstance(tier, DecisionTier) else str(tier)
    budget_seconds = ms / 1000.0

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    _emit(func, tier_value, ms, budget_seconds, start, on_exceed, city)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                _emit(func, tier_value, ms, budget_seconds, start, on_exceed, city)

        return sync_wrapper

    return decorator


def _emit(
    func: Callable[..., Any],
    tier_value: str,
    budget_ms: float,
    budget_seconds: float,
    start: float,
    on_exceed: str,
    city: str | None,
) -> None:
    elapsed = time.perf_counter() - start
    if elapsed <= budget_seconds:
        return
    TIER_BUDGET_EXCEEDED_TOTAL.labels(tier=tier_value).inc()
    logger.warning(
        "tier_budget_exceeded",
        tier=tier_value,
        handler=_func_name(func),
        budget_ms=budget_ms,
        elapsed_ms=round(elapsed * 1000, 3),
        on_exceed=on_exceed,
        city=city,
    )
    if on_exceed == "brownout" and city is not None:
        _signal_brownout(city, tier_value)


def _signal_brownout(city: str, tier_value: str) -> None:
    """Look up the registered BrownoutController and escalate the level.

    Falls back to a structured warning when:
      - no controller is registered for ``city`` (startup race),
      - the import fails (orchestrator package not on the path).
    """
    try:
        from orchestrator.consensus.brownout import (
            BrownoutLevel,
            get_controller,
        )
    except ImportError:
        logger.debug(
            "tier_budget_brownout_orchestrator_missing",
            city=city,
            tier=tier_value,
        )
        return

    controller = get_controller(city)
    if controller is None:
        logger.warning(
            "tier_budget_brownout_controller_missing",
            city=city,
            tier=tier_value,
            hint="register a BrownoutController during service startup",
        )
        return

    current = controller.current_level()
    # Escalate by one level on each sustained breach. SHED_LLM_ONLY is the cap.
    next_level = BrownoutLevel(min(int(current) + 1, int(BrownoutLevel.SHED_LLM_ONLY)))
    if next_level != current:
        controller.set_manual_override(next_level)
        logger.warning(
            "tier_budget_brownout_escalated",
            city=city,
            tier=tier_value,
            from_level=current.name,
            to_level=next_level.name,
        )


def _func_name(func: Callable[..., Any]) -> str:
    module = inspect.getmodule(func)
    return f"{module.__name__}.{func.__qualname__}" if module else func.__qualname__
