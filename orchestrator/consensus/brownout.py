"""
SYNAPSE Orchestrator — Brownout Policy (Sprint 7, WS-1).

Under SLO-burn or dependency saturation, automatically shed expensive
decision tiers down to cheaper ones rather than fail outright. The
brownout state is consulted by the Tier Router at the start of every
decision; tagging a decision ``essential=true`` bypasses the policy so
critical-path operations are never silently degraded.

Levels (ladder, in order of severity)
-------------------------------------
    NONE             — route as classified.
    SHED_T4          — route Tier 4 -> Tier 3 (skip Monte Carlo).
    SHED_T4_T3       — also route Tier 3 -> Tier 2 (skip multi-agent debate).
    SHED_LLM_ONLY    — collapse everything to Tier 1 (RL-only, no LLM).

Signals
-------
The policy is signal-driven so it stays unit-testable: callers feed in a
``BrownoutSignal`` snapshot built from Prometheus queries, the Ollama
client's queue depth, the named circuit breakers, and the orchestrator's
recent error rate. Thresholds are tunable per deployment.

The policy is *deterministic* per signal so the same Prometheus snapshot
always produces the same brownout level — replays under the eval harness
(WS-5) reproduce the same routing decisions.
"""

from __future__ import annotations

from enum import Enum

import structlog
from prometheus_client import Counter, Gauge
from pydantic import BaseModel, Field
from synapse_common.models import DecisionTier

logger = structlog.get_logger(__name__)


class BrownoutLevel(str, Enum):
    NONE = "none"
    SHED_T4 = "shed_t4"
    SHED_T4_T3 = "shed_t4_t3"
    SHED_LLM_ONLY = "shed_llm_only"


_LEVEL_ORDER: dict[BrownoutLevel, int] = {
    BrownoutLevel.NONE: 0,
    BrownoutLevel.SHED_T4: 1,
    BrownoutLevel.SHED_T4_T3: 2,
    BrownoutLevel.SHED_LLM_ONLY: 3,
}


BROWNOUT_LEVEL_GAUGE: Gauge = Gauge(
    "synapse_brownout_level",
    "Current brownout level (0=none, 1=shed_t4, 2=shed_t4_t3, 3=shed_llm_only)",
)

BROWNOUT_DECISIONS_TOTAL: Counter = Counter(
    "synapse_brownout_decisions_total",
    "Decisions routed under a brownout (counted by original->applied tier)",
    ["level", "original_tier", "applied_tier", "essential"],
)


class BrownoutSignal(BaseModel):
    """Snapshot of saturation signals consulted by the policy."""

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


class BrownoutPolicy:
    """Pure-function policy: signal -> level; (tier, signal, essential) -> tier."""

    def __init__(self, thresholds: BrownoutThresholds | None = None) -> None:
        self._thresholds = thresholds or BrownoutThresholds()
        self._current_level: BrownoutLevel = BrownoutLevel.NONE
        BROWNOUT_LEVEL_GAUGE.set(_LEVEL_ORDER[self._current_level])

    @property
    def current_level(self) -> BrownoutLevel:
        return self._current_level

    def evaluate(self, signal: BrownoutSignal) -> BrownoutLevel:
        """Compute the level mandated by the given signal snapshot."""
        t = self._thresholds

        # Hardest signal first: LLM dependency is saturated or down.
        if signal.ollama_breaker_open:
            return BrownoutLevel.SHED_LLM_ONLY
        if signal.ollama_queue_depth >= t.ollama_queue_shed_llm_only:
            return BrownoutLevel.SHED_LLM_ONLY

        # SLO-burn ladder.
        p99 = signal.tier1_p99_ms
        err = signal.error_rate

        if (p99 is not None and p99 >= t.tier1_p99_shed_t4_t3_ms) or (
            err is not None and err >= t.error_rate_shed_t4_t3
        ):
            return BrownoutLevel.SHED_T4_T3

        if (p99 is not None and p99 >= t.tier1_p99_shed_t4_ms) or (
            err is not None and err >= t.error_rate_shed_t4
        ):
            return BrownoutLevel.SHED_T4

        return BrownoutLevel.NONE

    def update(self, signal: BrownoutSignal) -> BrownoutLevel:
        """Re-evaluate from a signal and persist the new current level."""
        new_level = self.evaluate(signal)
        if new_level is not self._current_level:
            logger.warning(
                "brownout_level_changed",
                from_level=self._current_level.value,
                to_level=new_level.value,
                signal=signal.model_dump(),
            )
            self._current_level = new_level
            BROWNOUT_LEVEL_GAUGE.set(_LEVEL_ORDER[new_level])
        return new_level

    def apply(
        self,
        requested_tier: DecisionTier,
        *,
        essential: bool = False,
    ) -> DecisionTier:
        """Return the tier the orchestrator should *actually* run.

        Critical-path decisions (``essential=True``) bypass brownout —
        they always run at their requested tier. Otherwise the requested
        tier is collapsed downward according to the current level.
        """
        applied = self._reduce(requested_tier) if not essential else requested_tier
        BROWNOUT_DECISIONS_TOTAL.labels(
            level=self._current_level.value,
            original_tier=requested_tier.value,
            applied_tier=applied.value,
            essential=str(essential).lower(),
        ).inc()
        return applied

    def _reduce(self, requested: DecisionTier) -> DecisionTier:
        level = self._current_level
        if level is BrownoutLevel.NONE:
            return requested
        if level is BrownoutLevel.SHED_LLM_ONLY:
            return DecisionTier.TIER_1
        if level is BrownoutLevel.SHED_T4_T3:
            if requested in (DecisionTier.TIER_4, DecisionTier.TIER_3):
                return DecisionTier.TIER_2
            return requested
        # SHED_T4
        if requested is DecisionTier.TIER_4:
            return DecisionTier.TIER_3
        return requested
