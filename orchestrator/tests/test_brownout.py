"""Tests for the brownout policy (Sprint 7, WS-1)."""

from __future__ import annotations

import pytest
from synapse_common.models import DecisionTier

from orchestrator.consensus.brownout import (
    BrownoutLevel,
    BrownoutPolicy,
    BrownoutSignal,
    BrownoutThresholds,
)


def _signal(**kwargs: object) -> BrownoutSignal:
    return BrownoutSignal(**kwargs)  # type: ignore[arg-type]


class TestEvaluate:
    def test_quiet_signal_returns_none(self) -> None:
        p = BrownoutPolicy()
        assert p.evaluate(_signal()) is BrownoutLevel.NONE

    def test_open_breaker_jumps_straight_to_llm_only(self) -> None:
        p = BrownoutPolicy()
        assert (
            p.evaluate(_signal(ollama_breaker_open=True))
            is BrownoutLevel.SHED_LLM_ONLY
        )

    def test_high_queue_depth_jumps_to_llm_only(self) -> None:
        p = BrownoutPolicy()
        assert p.evaluate(_signal(ollama_queue_depth=51)) is BrownoutLevel.SHED_LLM_ONLY

    def test_p99_burn_ladder(self) -> None:
        p = BrownoutPolicy()
        assert p.evaluate(_signal(tier1_p99_ms=149.9)) is BrownoutLevel.NONE
        assert p.evaluate(_signal(tier1_p99_ms=150.0)) is BrownoutLevel.SHED_T4
        assert p.evaluate(_signal(tier1_p99_ms=199.9)) is BrownoutLevel.SHED_T4
        assert p.evaluate(_signal(tier1_p99_ms=200.0)) is BrownoutLevel.SHED_T4_T3

    def test_error_rate_ladder(self) -> None:
        p = BrownoutPolicy()
        assert p.evaluate(_signal(error_rate=0.04)) is BrownoutLevel.NONE
        assert p.evaluate(_signal(error_rate=0.06)) is BrownoutLevel.SHED_T4
        assert p.evaluate(_signal(error_rate=0.11)) is BrownoutLevel.SHED_T4_T3

    def test_thresholds_are_configurable(self) -> None:
        p = BrownoutPolicy(BrownoutThresholds(tier1_p99_shed_t4_ms=80.0))
        assert p.evaluate(_signal(tier1_p99_ms=85.0)) is BrownoutLevel.SHED_T4


class TestApply:
    def test_no_brownout_passes_tier_through(self) -> None:
        p = BrownoutPolicy()
        for t in DecisionTier:
            assert p.apply(t) is t

    def test_shed_t4_only_collapses_t4(self) -> None:
        p = BrownoutPolicy()
        p.update(_signal(tier1_p99_ms=160.0))
        assert p.current_level is BrownoutLevel.SHED_T4
        assert p.apply(DecisionTier.TIER_4) is DecisionTier.TIER_3
        assert p.apply(DecisionTier.TIER_3) is DecisionTier.TIER_3
        assert p.apply(DecisionTier.TIER_2) is DecisionTier.TIER_2
        assert p.apply(DecisionTier.TIER_1) is DecisionTier.TIER_1

    def test_shed_t4_t3_collapses_t3_and_t4(self) -> None:
        p = BrownoutPolicy()
        p.update(_signal(tier1_p99_ms=210.0))
        assert p.current_level is BrownoutLevel.SHED_T4_T3
        assert p.apply(DecisionTier.TIER_4) is DecisionTier.TIER_2
        assert p.apply(DecisionTier.TIER_3) is DecisionTier.TIER_2
        assert p.apply(DecisionTier.TIER_2) is DecisionTier.TIER_2
        assert p.apply(DecisionTier.TIER_1) is DecisionTier.TIER_1

    def test_shed_llm_only_collapses_everything_to_t1(self) -> None:
        p = BrownoutPolicy()
        p.update(_signal(ollama_breaker_open=True))
        for t in DecisionTier:
            assert p.apply(t) is DecisionTier.TIER_1

    def test_essential_bypasses_brownout(self) -> None:
        p = BrownoutPolicy()
        p.update(_signal(ollama_breaker_open=True))
        assert p.apply(DecisionTier.TIER_4, essential=True) is DecisionTier.TIER_4


class TestUpdate:
    def test_update_persists_level(self) -> None:
        p = BrownoutPolicy()
        assert p.current_level is BrownoutLevel.NONE
        p.update(_signal(tier1_p99_ms=160.0))
        assert p.current_level is BrownoutLevel.SHED_T4

    def test_update_with_quiet_signal_clears(self) -> None:
        p = BrownoutPolicy()
        p.update(_signal(tier1_p99_ms=210.0))
        assert p.current_level is BrownoutLevel.SHED_T4_T3
        p.update(_signal(tier1_p99_ms=10.0))
        assert p.current_level is BrownoutLevel.NONE


class TestSignalValidation:
    def test_negative_queue_depth_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017, BLE001 — Pydantic ValidationError
            BrownoutSignal(ollama_queue_depth=-1)

    def test_error_rate_above_one_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017, BLE001
            BrownoutSignal(error_rate=1.5)
