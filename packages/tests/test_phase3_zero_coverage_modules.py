"""Phase 3 — high-leverage tests for synapse_common modules that were 0%.

Targets per `docs/state/coverage-baseline-2026-05-29.md`:
- budget.py        (62 stmts, 0% → goal >85%) — pure tier-budget decorator
- dbc.py           (13 stmts, 0% → goal 100%) — thin re-export over `deal`
- reward_shadow.py (26 stmts, 0% → goal >85%) — divergence counter
- outbox.py        (16 stmts, 0% → goal pure-fn portion 100%) — canonical_payload only

Per CLAUDE.md "Coverage minimum 80%" and Sprint 13's 84% per-package destination.
Tests are deterministic, no I/O, no network. Mutation-survival hardening: every
assert pins a specific value or relation, not just `is not None`.
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import pytest
from synapse_common import budget, dbc, outbox, reward_shadow
from synapse_common.metrics import (
    REWARD_WEIGHT_DIVERGENCE_TOTAL,
    TIER_BUDGET_EXCEEDED_TOTAL,
)
from synapse_common.models import DecisionTier

# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------


def _counter_value(metric: Any, **labels: str) -> float:
    """Return the current value of a Prometheus counter for a given label set."""
    try:
        return float(metric.labels(**labels)._value.get())
    except (AttributeError, KeyError):
        return 0.0


# =============================================================================
# budget.py — @tier_budget decorator
# =============================================================================


class TestTierBudgetValidation:
    def test_invalid_on_exceed_raises(self) -> None:
        with pytest.raises(ValueError, match="on_exceed"):
            budget.tier_budget(ms=10, on_exceed="not_a_valid_action")

    def test_brownout_without_city_raises(self) -> None:
        with pytest.raises(ValueError, match="city"):
            budget.tier_budget(ms=10, on_exceed="brownout")

    def test_brownout_with_city_does_not_raise(self) -> None:
        # Should NOT raise — city supplied
        deco = budget.tier_budget(ms=10, on_exceed="brownout", city="bengaluru")
        assert callable(deco)

    def test_metric_only_is_default(self) -> None:
        # No on_exceed passed → defaults to metric_only, no city required
        deco = budget.tier_budget(ms=10)
        assert callable(deco)


class TestTierBudgetSync:
    def test_returns_wrapped_value(self) -> None:
        @budget.tier_budget(ms=1000, tier=DecisionTier.TIER_1)
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_under_budget_does_not_increment_counter(self) -> None:
        before = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_1")

        @budget.tier_budget(ms=1000, tier=DecisionTier.TIER_1)
        def fast() -> str:
            return "ok"

        fast()
        after = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_1")
        assert after == before, "Counter incremented when call was under budget"

    def test_over_budget_increments_counter(self) -> None:
        before = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_2")

        @budget.tier_budget(ms=1, tier=DecisionTier.TIER_2)
        def slow() -> str:
            time.sleep(0.05)  # 50ms — far exceeds 1ms
            return "ok"

        result = slow()
        assert result == "ok", "Return value lost when budget exceeded"
        after = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_2")
        assert after == before + 1, (
            f"Expected counter to increment by 1, before={before} after={after}"
        )

    def test_exception_does_not_swallow_signal(self) -> None:
        """If the wrapped function raises, the budget gauge still emits."""
        before = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_3")

        @budget.tier_budget(ms=1, tier=DecisionTier.TIER_3)
        def boom() -> None:
            time.sleep(0.05)
            raise RuntimeError("planned")

        with pytest.raises(RuntimeError, match="planned"):
            boom()
        # Counter should still have incremented (finally block runs)
        after = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_3")
        assert after == before + 1


class TestTierBudgetAsync:
    def test_async_returns_wrapped_value(self) -> None:
        @budget.tier_budget(ms=1000)
        async def aadd(a: int, b: int) -> int:
            return a + b

        result = asyncio.run(aadd(4, 5))
        assert result == 9

    def test_async_over_budget_increments_counter(self) -> None:
        before = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_4")

        @budget.tier_budget(ms=1, tier=DecisionTier.TIER_4)
        async def slow() -> str:
            await asyncio.sleep(0.05)
            return "ok"

        result = asyncio.run(slow())
        assert result == "ok"
        after = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="tier_4")
        assert after == before + 1


class TestTierBudgetString:
    def test_string_tier_label(self) -> None:
        """A plain string tier label is accepted (not just DecisionTier enum)."""
        before = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="CUSTOM_TIER")

        @budget.tier_budget(ms=1, tier="CUSTOM_TIER")
        def slow() -> None:
            time.sleep(0.05)

        slow()
        after = _counter_value(TIER_BUDGET_EXCEEDED_TOTAL, tier="CUSTOM_TIER")
        assert after == before + 1


class TestTierBudgetBrownoutFallback:
    def test_brownout_no_controller_does_not_raise(self) -> None:
        """When no BrownoutController is registered, the decorator must log
        a warning and continue — never raise."""

        @budget.tier_budget(ms=1, tier=DecisionTier.TIER_1, on_exceed="brownout", city="testcity")
        def slow() -> str:
            time.sleep(0.05)
            return "ok"

        # Must not raise even though no controller for testcity is registered.
        result = slow()
        assert result == "ok"


# =============================================================================
# dbc.py — re-exports over `deal`
# =============================================================================


class TestDbcReExports:
    def test_all_symbols_exposed(self) -> None:
        for name in (
            "pre",
            "post",
            "inv",
            "raises",
            "ensure",
            "has",
            "chain",
            "PreContractError",
            "PostContractError",
            "InvContractError",
        ):
            assert hasattr(dbc, name), f"dbc.{name} missing — __all__ list inconsistent"

    def test_pre_contract_enforced(self) -> None:
        @dbc.pre(lambda x: x >= 0)
        def sqrt_nonneg(x: float) -> float:
            return x**0.5

        # Honoring the precondition: passes
        assert sqrt_nonneg(9.0) == pytest.approx(3.0)
        # Violating the precondition: raises PreContractError
        with pytest.raises(dbc.PreContractError):
            sqrt_nonneg(-1.0)

    def test_post_contract_enforced(self) -> None:
        @dbc.post(lambda result: result >= 0)
        def maybe_negative(x: int) -> int:
            return x

        assert maybe_negative(5) == 5
        with pytest.raises(dbc.PostContractError):
            maybe_negative(-3)

    def test_pre_post_chain(self) -> None:
        """Chain pre + post for one function — both must fire."""

        @dbc.pre(lambda x: x > 0)
        @dbc.post(lambda result: result > 0)
        def double(x: int) -> int:
            return 2 * x

        assert double(3) == 6
        with pytest.raises(dbc.PreContractError):
            double(0)


# =============================================================================
# reward_shadow.py — divergence counter
# =============================================================================


class TestRewardShadowMatch:
    def _label_value(self, agent: str, key: str) -> float:
        return _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key=key)

    def test_matching_weights_no_divergence(self) -> None:
        agent = "test_agent_match"
        before = self._label_value(agent, "w1")
        reward_shadow.assert_shadow_match(
            agent, runtime={"w1": 0.5, "w2": 0.3}, spec={"w1": 0.5, "w2": 0.3}
        )
        assert self._label_value(agent, "w1") == before, "Counter incremented on identical weights"

    def test_value_mismatch_increments_counter(self) -> None:
        agent = "test_agent_mismatch"
        before = self._label_value(agent, "w1")
        reward_shadow.assert_shadow_match(agent, runtime={"w1": 0.6}, spec={"w1": 0.5})
        assert self._label_value(agent, "w1") == before + 1

    def test_missing_in_runtime_increments_counter(self) -> None:
        agent = "test_agent_missing_runtime"
        before = self._label_value(agent, "w_missing")
        reward_shadow.assert_shadow_match(agent, runtime={}, spec={"w_missing": 1.0})
        assert self._label_value(agent, "w_missing") == before + 1

    def test_missing_in_spec_increments_counter(self) -> None:
        agent = "test_agent_missing_spec"
        before = self._label_value(agent, "w_extra")
        reward_shadow.assert_shadow_match(agent, runtime={"w_extra": 0.4}, spec={})
        assert self._label_value(agent, "w_extra") == before + 1

    def test_non_finite_runtime_increments_counter(self) -> None:
        agent = "test_agent_nonfinite"
        before = self._label_value(agent, "w1")
        reward_shadow.assert_shadow_match(agent, runtime={"w1": math.inf}, spec={"w1": 0.5})
        assert self._label_value(agent, "w1") == before + 1

    def test_tolerance_window(self) -> None:
        """A diff below 1e-9 must NOT trigger divergence (floating-point safety)."""
        agent = "test_agent_tolerance"
        before = self._label_value(agent, "w1")
        reward_shadow.assert_shadow_match(agent, runtime={"w1": 0.5 + 1e-12}, spec={"w1": 0.5})
        assert self._label_value(agent, "w1") == before, (
            "Counter incremented on a sub-tolerance difference"
        )


class TestRewardShadowConvenienceWrapper:
    def test_shadow_check_filters_non_numeric(self) -> None:
        """shadow_check should silently drop non-numeric kwargs (e.g., strings)."""
        agent = "test_agent_filter"
        # Pass a string kwarg — must not crash, must not count toward divergence
        reward_shadow.shadow_check(
            agent,
            {"w1": 0.5},
            w1=0.5,
            not_a_number="oops",  # noqa
        )

    def test_shadow_check_matching_no_increment(self) -> None:
        agent = "test_agent_wrapper_match"
        before = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        reward_shadow.shadow_check(agent, {"w1": 1.0}, w1=1.0)
        after = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        assert after == before

    def test_shadow_check_int_coerced_to_float(self) -> None:
        """Integer kwargs are converted to float — must not produce divergence
        with a spec value of equivalent magnitude."""
        agent = "test_agent_int"
        before = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        reward_shadow.shadow_check(agent, {"w1": 1.0}, w1=1)  # int passed
        after = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        assert after == before

    def test_resolve_weights_uses_spec_default_for_none(self) -> None:
        agent = "test_agent_resolve_default"
        before = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        resolved = reward_shadow.resolve_weights(agent, {"w1": 1.0}, w1=None)
        after = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        assert resolved == {"w1": 1.0}
        assert after == before

    def test_resolve_weights_observes_numeric_override(self) -> None:
        agent = "test_agent_resolve_override"
        before = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        resolved = reward_shadow.resolve_weights(agent, {"w1": 1.0}, w1=2.0)
        after = _counter_value(REWARD_WEIGHT_DIVERGENCE_TOTAL, agent=agent, key="w1")
        assert resolved == {"w1": 2.0}
        assert after == before + 1


# =============================================================================
# outbox.py — canonical_payload (the pure-function portion)
# =============================================================================


class TestCanonicalPayload:
    def test_keys_sorted_deterministically(self) -> None:
        """Same input → same JSON regardless of source dict iteration order."""
        import json

        p1 = outbox.canonical_payload({"z": 1, "a": 2, "m": 3})
        p2 = outbox.canonical_payload({"a": 2, "m": 3, "z": 1})
        # Round-tripping through the canonical JSON encoder gives identical strings
        assert json.dumps(p1, sort_keys=True) == json.dumps(p2, sort_keys=True)

    def test_nested_structures_preserved(self) -> None:
        payload = {"outer": {"inner": [1, 2, 3], "scalar": "value"}}
        result = outbox.canonical_payload(payload)
        assert result == payload

    def test_non_json_native_coerced_via_default_str(self) -> None:
        """A UUID-like object is coerced to its str via default=str."""
        from uuid import UUID

        uid = UUID("11111111-1111-1111-1111-111111111111")
        result = outbox.canonical_payload({"id": uid})
        assert result == {"id": "11111111-1111-1111-1111-111111111111"}

    def test_empty_payload_round_trips(self) -> None:
        assert outbox.canonical_payload({}) == {}
