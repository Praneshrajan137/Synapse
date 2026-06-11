"""
SYNAPSE Brownout Policy (WS-1 §5, ADR-028).

Under sustained burn — measured as Ollama breaker state, Postgres
breaker state, or a Prometheus-derived p99 burn-rate — the orchestrator
sheds work tier-by-tier so the Tier-1 fast path stays inside its 100 ms
budget. ``essential=true`` decisions are never shed.

Levels (monotone, increasing severity):

    NONE          — full service
    SHED_T4       — Tier-4 falls back to Tier-3 (degraded=true)
    SHED_T4_T3    — Tier-3 + Tier-4 fall back to Tier-2
    SHED_LLM_ONLY — LLM-mediated decisions disabled; RL-only Tier-1/2

State is keyed by ``(city, tier)`` so a Mumbai outage cannot shed
Bengaluru traffic. The controller exposes Prometheus counter
``synapse_brownout_decisions_total`` for postmortem traceability.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

import structlog
from synapse_common.metrics import BROWNOUT_DECISIONS_TOTAL
from synapse_common.models import DecisionTier

if TYPE_CHECKING:
    from synapse_common.breakers import AsyncBreaker

logger = structlog.get_logger(__name__)


class BrownoutLevel(IntEnum):
    """Brownout severity levels — monotonic, comparable by integer ordering."""

    NONE = 0
    SHED_T4 = 1
    SHED_T4_T3 = 2
    SHED_LLM_ONLY = 3


# Tier ordering used to compute fallback under shedding.
_TIER_ORDER: list[DecisionTier] = [
    DecisionTier.TIER_1,
    DecisionTier.TIER_2,
    DecisionTier.TIER_3,
    DecisionTier.TIER_4,
]


class BrownoutController:
    """Per-(city, tier) brownout decisions consulted by the tier router."""

    def __init__(
        self,
        city: str,
        ollama_breaker: AsyncBreaker | None = None,
        postgres_breaker: AsyncBreaker | None = None,
    ) -> None:
        self.city = city
        self._ollama_breaker = ollama_breaker
        self._postgres_breaker = postgres_breaker
        self._manual_override: BrownoutLevel | None = None

    def set_manual_override(self, level: BrownoutLevel | None) -> None:
        """Test/admin hook — pin the brownout level. ``None`` disables override."""
        self._manual_override = level
        logger.info(
            "brownout_manual_override",
            city=self.city,
            level=level.name if level is not None else None,
        )

    def current_level(self) -> BrownoutLevel:
        """Compute the active brownout level from breaker state + manual override."""
        if self._manual_override is not None:
            return self._manual_override
        ollama_state = self._breaker_state(self._ollama_breaker)
        postgres_state = self._breaker_state(self._postgres_breaker)
        # Both critical paths down → kill LLM, RL-only operation
        if ollama_state >= 2 and postgres_state >= 2:
            return BrownoutLevel.SHED_LLM_ONLY
        # Ollama open and not recovering → shed T3 + T4
        if ollama_state >= 2:
            return BrownoutLevel.SHED_T4_T3
        # Ollama half-open or postgres degraded → shed only T4
        if ollama_state == 1 or postgres_state >= 1:
            return BrownoutLevel.SHED_T4
        return BrownoutLevel.NONE

    def should_shed(self, tier: DecisionTier, essential: bool) -> bool:
        """Return True when the caller must accept a lower-tier route."""
        if essential:
            return False
        level = self.current_level()
        if level == BrownoutLevel.NONE:
            return False
        if level == BrownoutLevel.SHED_T4 and tier == DecisionTier.TIER_4:
            self._record(level)
            return True
        if level == BrownoutLevel.SHED_T4_T3 and tier in (
            DecisionTier.TIER_3,
            DecisionTier.TIER_4,
        ):
            self._record(level)
            return True
        if level == BrownoutLevel.SHED_LLM_ONLY and tier in (
            DecisionTier.TIER_2,
            DecisionTier.TIER_3,
            DecisionTier.TIER_4,
        ):
            self._record(level)
            return True
        return False

    def fallback_tier(self, tier: DecisionTier) -> DecisionTier:
        """Return the next-lower tier; never drops below Tier-1."""
        idx = _TIER_ORDER.index(tier)
        return _TIER_ORDER[max(0, idx - 1)]

    def _record(self, level: BrownoutLevel) -> None:
        BROWNOUT_DECISIONS_TOTAL.labels(level=level.name, city=self.city).inc()

    @staticmethod
    def _breaker_state(breaker: AsyncBreaker | None) -> int:
        """Map BreakerState to a comparable int.

        AsyncBreaker.state is a ``BreakerState`` *string* enum (CLOSED/
        OPEN/HALF_OPEN), so a raw ``int(...)`` would attempt
        ``int('closed')`` and raise ValueError. Translate explicitly:
        CLOSED=0 < HALF_OPEN=1 < OPEN=2.
        """
        if breaker is None:
            return 0
        # Import lazily to avoid a circular module load with breakers.py.
        from synapse_common.breakers import BreakerState

        state = breaker.state
        if state is BreakerState.OPEN:
            return 2
        if state is BreakerState.HALF_OPEN:
            return 1
        return 0


# ----------------------------------------------------------------------------
# Sprint 9 (ADR-032 follow-up) — per-city controller registry.
#
# `@tier_budget(on_exceed="brownout")` from packages/synapse_common/budget.py
# needs a way to find the active BrownoutController for the request's city.
# Sprint 8 deferred this until a registry existed; Sprint 9 provides it.
# ----------------------------------------------------------------------------

_REGISTRY: dict[str, BrownoutController] = {}


def register(controller: BrownoutController) -> None:
    """Register a controller for its city. Re-registration replaces the prior one."""
    _REGISTRY[controller.city] = controller
    logger.info("brownout_controller_registered", city=controller.city)


def get_controller(city: str) -> BrownoutController | None:
    """Return the registered controller for ``city`` or ``None`` if not yet wired."""
    return _REGISTRY.get(city)


def registered_controllers() -> dict[str, BrownoutController]:
    """Snapshot of every registered controller, keyed by city (ADR-044).

    Read-only posture surface for ``GET /api/v1/status/posture`` — lets the
    operator UI report the live brownout level per city. Returns a copy.
    """
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Test-only helper; production code never clears the registry mid-flight."""
    _REGISTRY.clear()
