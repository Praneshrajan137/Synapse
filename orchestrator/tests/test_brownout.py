"""Tests for the brownout policy (Sprint 7 WS-1, ADR-028).

Targets the simplified per-city BrownoutController API (no Pydantic
signal hybrid). Uses set_manual_override to drive the ladder, and a
small fake CircuitBreaker stub to exercise the breaker-driven path.
"""

from __future__ import annotations

from typing import Any

import pytest
from synapse_common.breakers import BreakerState
from synapse_common.models import DecisionTier

from orchestrator.consensus import brownout as bo
from orchestrator.consensus.brownout import (
    BrownoutController,
    BrownoutLevel,
)

# Sprint 13 fix: the production `_breaker_state()` compares `breaker.state` to
# the BreakerState string enum (not raw integers). The previous _FakeBreaker
# passed plain ints, which always resolved to "CLOSED" (state == 0) regardless
# of intent. We now expose the same BreakerState enum the real AsyncBreaker
# does, keyed by the same severity ordering: CLOSED=0 < HALF_OPEN=1 < OPEN=2.
_STATE_BY_LEVEL: dict[int, BreakerState] = {
    0: BreakerState.CLOSED,
    1: BreakerState.HALF_OPEN,
    2: BreakerState.OPEN,
}


class _FakeBreaker:
    """Minimal stand-in for AsyncBreaker — exposes ``state: BreakerState``.

    Accepts the legacy integer levels (0/1/2) for backward compatibility with
    existing test cases and translates to the proper enum.
    """

    def __init__(self, state: int | BreakerState = 0) -> None:
        if isinstance(state, BreakerState):
            self.state = state
        else:
            self.state = _STATE_BY_LEVEL[state]


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    bo.clear_registry()
    yield
    bo.clear_registry()


class TestLevelLadder:
    def test_quiet_breakers_returns_none(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(0), _FakeBreaker(0))
        assert c.current_level() is BrownoutLevel.NONE

    def test_ollama_open_sheds_t3_t4(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(2), _FakeBreaker(0))
        assert c.current_level() is BrownoutLevel.SHED_T4_T3

    def test_both_breakers_open_sheds_llm_only(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(2), _FakeBreaker(2))
        assert c.current_level() is BrownoutLevel.SHED_LLM_ONLY

    def test_ollama_half_open_sheds_t4_only(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(1), _FakeBreaker(0))
        assert c.current_level() is BrownoutLevel.SHED_T4

    def test_postgres_half_open_sheds_t4_only(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(0), _FakeBreaker(1))
        assert c.current_level() is BrownoutLevel.SHED_T4


class TestManualOverride:
    def test_manual_override_pins_level(self) -> None:
        c = BrownoutController("bengaluru")
        c.set_manual_override(BrownoutLevel.SHED_T4_T3)
        assert c.current_level() is BrownoutLevel.SHED_T4_T3

    def test_clearing_override_uses_breaker_state(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(2), _FakeBreaker(0))
        c.set_manual_override(BrownoutLevel.NONE)
        assert c.current_level() is BrownoutLevel.NONE
        c.set_manual_override(None)
        assert c.current_level() is BrownoutLevel.SHED_T4_T3


class TestShouldShed:
    def test_essential_bypasses(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(2), _FakeBreaker(2))
        for t in DecisionTier:
            assert c.should_shed(t, essential=True) is False

    def test_shed_t4_only_t4(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(1), _FakeBreaker(0))
        assert c.should_shed(DecisionTier.TIER_4, essential=False) is True
        assert c.should_shed(DecisionTier.TIER_3, essential=False) is False
        assert c.should_shed(DecisionTier.TIER_2, essential=False) is False

    def test_shed_t4_t3(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(2), _FakeBreaker(0))
        assert c.should_shed(DecisionTier.TIER_4, essential=False) is True
        assert c.should_shed(DecisionTier.TIER_3, essential=False) is True
        assert c.should_shed(DecisionTier.TIER_2, essential=False) is False
        assert c.should_shed(DecisionTier.TIER_1, essential=False) is False

    def test_shed_llm_only(self) -> None:
        c = BrownoutController("bengaluru", _FakeBreaker(2), _FakeBreaker(2))
        assert c.should_shed(DecisionTier.TIER_4, essential=False) is True
        assert c.should_shed(DecisionTier.TIER_3, essential=False) is True
        assert c.should_shed(DecisionTier.TIER_2, essential=False) is True
        assert c.should_shed(DecisionTier.TIER_1, essential=False) is False


class TestFallbackTier:
    def test_fallback_steps_down(self) -> None:
        c = BrownoutController("bengaluru")
        assert c.fallback_tier(DecisionTier.TIER_4) is DecisionTier.TIER_3
        assert c.fallback_tier(DecisionTier.TIER_3) is DecisionTier.TIER_2
        assert c.fallback_tier(DecisionTier.TIER_2) is DecisionTier.TIER_1
        assert c.fallback_tier(DecisionTier.TIER_1) is DecisionTier.TIER_1


class TestRegistry:
    def test_register_and_lookup(self) -> None:
        c = BrownoutController("bengaluru")
        bo.register(c)
        assert bo.get_controller("bengaluru") is c
        assert bo.get_controller("mumbai") is None

    def test_per_city_isolation(self) -> None:
        """E-S6 invariant: Mumbai outage cannot shed Bengaluru traffic."""
        b = BrownoutController("bengaluru", _FakeBreaker(0), _FakeBreaker(0))
        m = BrownoutController("mumbai", _FakeBreaker(2), _FakeBreaker(2))
        bo.register(b)
        bo.register(m)
        assert bo.get_controller("bengaluru").current_level() is BrownoutLevel.NONE
        assert bo.get_controller("mumbai").current_level() is BrownoutLevel.SHED_LLM_ONLY
