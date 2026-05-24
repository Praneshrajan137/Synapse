"""
SYNAPSE Brownout Policy (Sprint 7, WS-1, ADR-028).

Under sustained burn — measured as Ollama / Postgres circuit-breaker state
or a Prometheus-derived saturation snapshot — the orchestrator sheds work
tier-by-tier so the Tier-1 fast path stays inside its 100 ms budget.
``essential=true`` decisions are never shed.

Two cooperating surfaces:

1.  **Production path** — ``BrownoutController(city, ollama_breaker,
    postgres_breaker)`` is the per-city stateful controller consulted by
    the tier router. It reads live breaker state and decides whether to
    shed; state is keyed by ``(city, tier)`` so a Mumbai outage cannot
    shed Bengaluru traffic (preserves E-S6 multi-city isolation).
2.  **Replay / test path** — ``compute_level_from_signal(signal,
    thresholds)`` is a pure function: a frozen ``BrownoutSignal``
    snapshot produces a deterministic ``BrownoutLevel``. Used by the
    evaluation harness (WS-5) and by unit tests that want to drive the
    ladder without instantiating breakers.

Levels (monotone, increasing severity):

    NONE          — full service
    SHED_T4       — Tier-4 falls back to Tier-3 (degraded=true)
    SHED_T4_T3    — Tier-3 + Tier-4 fall back to Tier-2
    SHED_LLM_ONLY — LLM-mediated decisions disabled; RL-only Tier-1/2

The controller exposes ``synapse_brownout_decisions_total`` (labelled by
level + city) for postmortem traceability.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field
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


# ----------------------------------------------------------------------------
# Signal-based, pure-function ladder (Franklin's BrownoutSignal model).
#
# Used by tests and the replay harness; production code uses
# ``BrownoutController`` below which reads live breaker state.
# ----------------------------------------------------------------------------


class BrownoutSignal(BaseModel):
    """Snapshot of saturation signals consulted by the policy.

    Frozen so a snapshot is reproducible. The same snapshot always
    produces the same brownout level, which is the determinism property
    the WS-5 replay harness relies on.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    tier1_p99_ms: float | None = Field(
        default=None,
        description="Recent Tier 1 p99 latency in ms; None if unknown.",
    )
    ollama_breaker_open: bool = Field(
        default=False,
        description="True when the Ollama circuit breaker is currently OPEN.",
    )
    ollama_queue_depth: int = Field(
        default=0,
        ge=0,
        description="Approximate in-flight Ollama requests; high values indicate saturation.",
    )
    postgres_breaker_open: bool = Field(
        default=False,
        description="True when the Postgres circuit breaker is currently OPEN.",
    )
    error_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Decision error rate over the recent window (0-1); None if unknown.",
    )


class BrownoutThresholds(BaseModel):
    """Threshold ladder for promoting through brownout levels."""

    model_config = {"frozen": True, "extra": "forbid"}

    tier1_p99_shed_t4_ms: float = 150.0
    tier1_p99_shed_t4_t3_ms: float = 200.0
    ollama_queue_shed_llm_only: int = 50
    error_rate_shed_t4: float = 0.05
    error_rate_shed_t4_t3: float = 0.10


DEFAULT_THRESHOLDS = BrownoutThresholds()


def compute_level_from_signal(
    signal: BrownoutSignal,
    thresholds: BrownoutThresholds = DEFAULT_THRESHOLDS,
) -> BrownoutLevel:
    """Pure function: signal snapshot -> level. Deterministic for replay.

    Ladder (most-severe wins):
        Ollama or Postgres breaker OPEN + queue saturated  -> SHED_LLM_ONLY
        Ollama queue >= shed-LLM-only threshold            -> SHED_LLM_ONLY
        p99 >= shed-T4-T3 or err >= shed-T4-T3             -> SHED_T4_T3
        p99 >= shed-T4    or err >= shed-T4                -> SHED_T4
        else                                                -> NONE
    """
    # LLM dependency saturated or down — disable LLM-mediated tiers entirely.
    # Conservative: a tripped Ollama breaker means LLM calls fail immediately,
    # so SHED_LLM_ONLY is the correct response (not a half-measure shed).
    if signal.ollama_breaker_open:
        return BrownoutLevel.SHED_LLM_ONLY
    if signal.ollama_queue_depth >= thresholds.ollama_queue_shed_llm_only:
        return BrownoutLevel.SHED_LLM_ONLY

    p99 = signal.tier1_p99_ms
    err = signal.error_rate

    if (p99 is not None and p99 >= thresholds.tier1_p99_shed_t4_t3_ms) or (
        err is not None and err >= thresholds.error_rate_shed_t4_t3
    ):
        return BrownoutLevel.SHED_T4_T3

    if (p99 is not None and p99 >= thresholds.tier1_p99_shed_t4_ms) or (
        err is not None and err >= thresholds.error_rate_shed_t4
    ):
        return BrownoutLevel.SHED_T4

    # Postgres-only degradation: shed Tier-4 (Monte Carlo) which is the most
    # DB-hungry tier; Tier-1/2/3 remain available.
    if signal.postgres_breaker_open:
        return BrownoutLevel.SHED_T4

    return BrownoutLevel.NONE


# ----------------------------------------------------------------------------
# BrownoutPolicy — stateful single-policy shim for ladder testing / replay.
#
# Wraps ``compute_level_from_signal`` with persistent ``current_level``
# state plus a ``apply(tier)`` collapsing rule. Used by the WS-5 replay
# harness and by unit tests that drive the ladder directly without
# instantiating breakers. Production code uses ``BrownoutController``
# (defined below) which scopes by city and reads live breaker state.
# ----------------------------------------------------------------------------


class BrownoutPolicy:
    """Stateful ladder policy. Single-tenant — for replay/tests only."""

    def __init__(self, thresholds: BrownoutThresholds | None = None) -> None:
        self._thresholds = thresholds or DEFAULT_THRESHOLDS
        self._current_level: BrownoutLevel = BrownoutLevel.NONE

    @property
    def current_level(self) -> BrownoutLevel:
        return self._current_level

    def evaluate(self, signal: BrownoutSignal) -> BrownoutLevel:
        """Pure: compute the level mandated by ``signal``. No state change."""
        return compute_level_from_signal(signal, self._thresholds)

    def update(self, signal: BrownoutSignal) -> BrownoutLevel:
        """Compute the level from ``signal`` and persist it as current."""
        self._current_level = self.evaluate(signal)
        return self._current_level

    def apply(
        self,
        requested_tier: DecisionTier,
        *,
        essential: bool = False,
    ) -> DecisionTier:
        """Return the tier to actually run, given the persisted level.

        ``essential=True`` bypasses brownout — critical-path decisions
        always run at the requested tier.
        """
        if essential:
            return requested_tier
        level = self._current_level
        if level == BrownoutLevel.NONE:
            return requested_tier
        if level == BrownoutLevel.SHED_LLM_ONLY:
            return DecisionTier.TIER_1
        if level == BrownoutLevel.SHED_T4_T3:
            if requested_tier in (DecisionTier.TIER_3, DecisionTier.TIER_4):
                return DecisionTier.TIER_2
            return requested_tier
        # SHED_T4
        if requested_tier == DecisionTier.TIER_4:
            return DecisionTier.TIER_3
        return requested_tier


# ----------------------------------------------------------------------------
# Production path — BrownoutController, per-city, breaker-driven.
# Keyed by (city, tier) so a Mumbai outage cannot shed Bengaluru traffic.
# ----------------------------------------------------------------------------


class BrownoutController:
    """Per-city brownout decisions consulted by the tier router."""

    def __init__(
        self,
        city: str,
        ollama_breaker: AsyncBreaker | None = None,
        postgres_breaker: AsyncBreaker | None = None,
        thresholds: BrownoutThresholds | None = None,
    ) -> None:
        self.city = city
        self._ollama_breaker = ollama_breaker
        self._postgres_breaker = postgres_breaker
        self._thresholds = thresholds or DEFAULT_THRESHOLDS
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
        """Compute the active brownout level from live breaker state.

        Honours the manual override if set. Reads breakers synchronously.
        For deterministic, replay-friendly evaluation use
        ``current_level_from_signal`` instead.
        """
        if self._manual_override is not None:
            return self._manual_override
        # Build a snapshot from live breaker state and delegate to the
        # pure ladder. This keeps the production path and the replay
        # path on a single, unit-testable decision function.
        signal = BrownoutSignal(
            ollama_breaker_open=self._breaker_open(self._ollama_breaker),
            postgres_breaker_open=self._breaker_open(self._postgres_breaker),
        )
        return compute_level_from_signal(signal, self._thresholds)

    def current_level_from_signal(
        self,
        signal: BrownoutSignal,
        thresholds: BrownoutThresholds | None = None,
    ) -> BrownoutLevel:
        """Replay/test path — compute level from an explicit snapshot.

        Respects the manual override exactly like ``current_level``.
        Tests can call this to drive the ladder deterministically.
        """
        if self._manual_override is not None:
            return self._manual_override
        return compute_level_from_signal(signal, thresholds or self._thresholds)

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
    def _breaker_open(breaker: AsyncBreaker | None) -> bool:
        """Return True iff the given breaker is currently OPEN."""
        if breaker is None:
            return False
        # AsyncBreaker.state is a BreakerState enum; OPEN compares equal
        # to the string "open" for both Enum and IntEnum implementations.
        state = getattr(breaker, "state", None)
        state_value = getattr(state, "value", state)
        return state_value == "open" or state_value == 1


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


def clear_registry() -> None:
    """Test-only helper; production code never clears the registry mid-flight."""
    _REGISTRY.clear()
