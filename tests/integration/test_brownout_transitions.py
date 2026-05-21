"""Brownout transitions test (WS-1 §5 acceptance, ADR-028).

Exercises the four brownout levels by directly driving breaker state.
Per-city isolation is verified by running two controllers with
independent breakers and asserting one city's degradation does NOT
shed traffic from the other.
"""

from __future__ import annotations

import pytest
from synapse_common.breakers import BreakerState, CircuitBreaker
from synapse_common.models import DecisionTier

from orchestrator.consensus.brownout import BrownoutController, BrownoutLevel


def _make_breaker(state: BreakerState) -> CircuitBreaker:
    cb = CircuitBreaker(name=f"test-{state.name}", fail_max=1, reset_timeout=60.0)
    cb._state = state  # noqa: SLF001 — test seam
    return cb


@pytest.mark.integration
def test_no_brownout_when_breakers_closed() -> None:
    ctl = BrownoutController(
        city="bengaluru",
        ollama_breaker=_make_breaker(BreakerState.CLOSED),
        postgres_breaker=_make_breaker(BreakerState.CLOSED),
    )
    assert ctl.current_level() == BrownoutLevel.NONE
    assert not ctl.should_shed(DecisionTier.TIER_4, essential=False)


@pytest.mark.integration
def test_shed_t4_when_ollama_half_open() -> None:
    ctl = BrownoutController(
        city="bengaluru",
        ollama_breaker=_make_breaker(BreakerState.HALF_OPEN),
        postgres_breaker=_make_breaker(BreakerState.CLOSED),
    )
    assert ctl.current_level() == BrownoutLevel.SHED_T4
    assert ctl.should_shed(DecisionTier.TIER_4, essential=False)
    assert not ctl.should_shed(DecisionTier.TIER_3, essential=False)


@pytest.mark.integration
def test_shed_t3_t4_when_ollama_open() -> None:
    ctl = BrownoutController(
        city="bengaluru",
        ollama_breaker=_make_breaker(BreakerState.OPEN),
        postgres_breaker=_make_breaker(BreakerState.CLOSED),
    )
    assert ctl.current_level() == BrownoutLevel.SHED_T4_T3
    assert ctl.should_shed(DecisionTier.TIER_3, essential=False)
    assert ctl.should_shed(DecisionTier.TIER_4, essential=False)


@pytest.mark.integration
def test_shed_llm_only_when_both_breakers_open() -> None:
    ctl = BrownoutController(
        city="bengaluru",
        ollama_breaker=_make_breaker(BreakerState.OPEN),
        postgres_breaker=_make_breaker(BreakerState.OPEN),
    )
    assert ctl.current_level() == BrownoutLevel.SHED_LLM_ONLY
    assert ctl.should_shed(DecisionTier.TIER_2, essential=False)


@pytest.mark.integration
def test_essential_decisions_never_shed() -> None:
    ctl = BrownoutController(
        city="bengaluru",
        ollama_breaker=_make_breaker(BreakerState.OPEN),
        postgres_breaker=_make_breaker(BreakerState.OPEN),
    )
    assert ctl.should_shed(DecisionTier.TIER_4, essential=True) is False
    assert ctl.should_shed(DecisionTier.TIER_2, essential=True) is False


@pytest.mark.integration
def test_per_city_isolation() -> None:
    """Mumbai breaker open must not shed Bengaluru traffic."""
    bengaluru = BrownoutController(
        city="bengaluru",
        ollama_breaker=_make_breaker(BreakerState.CLOSED),
        postgres_breaker=_make_breaker(BreakerState.CLOSED),
    )
    mumbai = BrownoutController(
        city="mumbai",
        ollama_breaker=_make_breaker(BreakerState.OPEN),
        postgres_breaker=_make_breaker(BreakerState.CLOSED),
    )
    assert bengaluru.current_level() == BrownoutLevel.NONE
    assert mumbai.current_level() == BrownoutLevel.SHED_T4_T3
    assert not bengaluru.should_shed(DecisionTier.TIER_4, essential=False)
    assert mumbai.should_shed(DecisionTier.TIER_4, essential=False)


@pytest.mark.integration
def test_fallback_tier_drops_one_step() -> None:
    ctl = BrownoutController(city="bengaluru")
    assert ctl.fallback_tier(DecisionTier.TIER_4) == DecisionTier.TIER_3
    assert ctl.fallback_tier(DecisionTier.TIER_3) == DecisionTier.TIER_2
    assert ctl.fallback_tier(DecisionTier.TIER_2) == DecisionTier.TIER_1
    assert ctl.fallback_tier(DecisionTier.TIER_1) == DecisionTier.TIER_1
