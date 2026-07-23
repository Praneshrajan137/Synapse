"""
Unit (example-based) tests for the closed-loop cadence and the INV-TW-002 under-power
guard (task 7.6).

Two behaviors are pinned down here:

* **Closed-loop cadence (R2.2).** ``uplift.harness.run_closed_loop`` must run the
  observe → decide → apply → advance loop exactly ``LoopConfig.n_steps`` times, calling
  ``DecisionPolicy.decide`` once per step with an ``Observation`` reflecting the *current*
  twin state (state advances between steps), and it must apply the returned
  ``PolicyAction`` *before* advancing the twin. A spy policy records every observation it
  sees and every action it returns so the ordering and freshness can be asserted directly.

* **INV-TW-002 under-power guard (R2.4).** ``UpliftHarness`` must refuse to aggregate an
  arm from fewer than ``MIN_SCENARIOS`` (1000) scenarios: requesting ``n < 1000`` raises
  ``ValueError`` whose message references INV-TW-002, while ``n >= 1000`` passes the guard.
  The guard is exercised directly via the static ``_check_power`` (so we never have to run
  1000 twin simulations) plus one integration-style assertion that ``run_arm`` with a small
  ``n`` raises before doing any work.
"""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams

from uplift.harness import LoopConfig, UpliftHarness, run_closed_loop
from uplift.interfaces import Observation, PolicyAction, Scenario


# A tiny, neutral (unshocked) scenario: the twin warms ``sku_0..sku_9`` to 100 units each,
# so a handful of steps run fast and inventory is well-defined for the apply-before-advance
# assertion.
TINY_SCENARIO = Scenario(name="tiny-cadence", seed=7_777, shock=ShockParams())


class _SpyPolicy:
    """A ``DecisionPolicy`` that records every ``Observation`` it is handed.

    ``decide`` appends the incoming observation to ``observations`` and the action it
    returns to ``actions`` (same index), so the test can assert the loop's per-step
    cadence and ordering after the run. ``reorder_sku``/``reorder_qty`` let a test drive a
    concrete twin lever whose effect is observable at the *next* step (proving the action
    was applied before the twin advanced).
    """

    def __init__(self, reorder_sku: str | None = None, reorder_qty: float = 0.0) -> None:
        self.name = "spy"
        self.observations: list[Observation] = []
        self.actions: list[PolicyAction] = []
        self._reorder_sku = reorder_sku
        self._reorder_qty = reorder_qty

    def decide(self, obs: Observation) -> PolicyAction:
        self.observations.append(obs)
        if self._reorder_sku is not None:
            action = PolicyAction(reorder_quantities={self._reorder_sku: self._reorder_qty})
        else:
            action = PolicyAction()
        self.actions.append(action)
        return action


# ---------------------------------------------------------------------------
# Closed-loop cadence (R2.2)
# ---------------------------------------------------------------------------
def test_run_closed_loop_calls_decide_once_per_step_with_fresh_state() -> None:
    """decide is called exactly ``n_steps`` times with monotonically advancing state (R2.2).

    A ``duration_hours=3 / step_hours=1`` loop is 3 steps. The spy must be asked to decide
    exactly 3 times, and the ``sim_time`` / ``delivery_count`` observed at each call must be
    non-decreasing — the twin advances between steps, so each ``decide`` sees fresh current
    state rather than a stale snapshot.

    **Validates: Requirements 2.2**
    """
    loop = LoopConfig(duration_hours=3.0, step_hours=1.0)
    assert loop.n_steps == 3

    spy = _SpyPolicy()
    run = run_closed_loop(
        TINY_SCENARIO, spy, seed=TINY_SCENARIO.seed, arm_name="spy", loop_config=loop
    )

    # The run completed (the spy raised nothing), so no fabricated failure occurred.
    assert run.failed is False
    assert run.kpis is not None

    # observe -> decide happened exactly once per step.
    assert len(spy.observations) == loop.n_steps
    assert len(spy.actions) == loop.n_steps

    # State observed at each step advances (twin advanced between decide calls).
    sim_times = [obs.sim_time for obs in spy.observations]
    assert sim_times == sorted(sim_times), f"sim_time not monotonic: {sim_times}"
    assert sim_times[-1] > sim_times[0], "twin never advanced across steps"

    delivery_counts = [obs.delivery_count for obs in spy.observations]
    assert delivery_counts == sorted(delivery_counts), (
        f"delivery_count not monotonic: {delivery_counts}"
    )


def test_run_closed_loop_applies_action_before_advancing() -> None:
    """The returned action is applied *before* ``advance`` (R2.2).

    The spy issues a large ``reorder_quantities`` for ``sku_0`` on every step. If the loop
    applies the action before advancing (the required order), then the observation handed to
    the *next* ``decide`` must reflect the added stock: ``sku_0`` starts at 100 units, so a
    reorder of 100000 units applied before the next advance leaves the next observed level
    far above the starting level even after that step's consumption. If the action were
    dropped or applied after advancing, the next observation would still be near 100.

    **Validates: Requirements 2.2**
    """
    loop = LoopConfig(duration_hours=3.0, step_hours=1.0)
    spy = _SpyPolicy(reorder_sku="sku_0", reorder_qty=100_000.0)

    run = run_closed_loop(
        TINY_SCENARIO, spy, seed=TINY_SCENARIO.seed, arm_name="spy", loop_config=loop
    )
    assert run.failed is False

    first_level = spy.observations[0].inventory["sku_0"]
    second_level = spy.observations[1].inventory["sku_0"]

    # The first step sees the warm-start level (~100); the reorder is applied before the
    # advance that produces the second observation, so the second level is far higher.
    assert first_level <= 200, f"unexpected warm-start level: {first_level}"
    assert second_level > first_level + 50_000, (
        f"reorder not applied before advance: first={first_level}, second={second_level}"
    )


# ---------------------------------------------------------------------------
# INV-TW-002 under-power guard (R2.4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [0, 1, 10, 500, 999])
def test_check_power_rejects_underpowered_n(n: int) -> None:
    """``_check_power`` raises ``ValueError`` referencing INV-TW-002 for ``n < 1000`` (R2.4).

    **Validates: Requirements 2.4**
    """
    with pytest.raises(ValueError, match="INV-TW-002"):
        UpliftHarness._check_power(n)


@pytest.mark.parametrize("n", [MIN_SCENARIOS, MIN_SCENARIOS + 1, 5_000])
def test_check_power_accepts_powered_n(n: int) -> None:
    """``_check_power`` does not raise for ``n >= 1000`` — the guard is satisfied (R2.4).

    **Validates: Requirements 2.4**
    """
    # No exception is the assertion; a raise here would fail the test.
    UpliftHarness._check_power(n)


def test_run_arm_raises_before_running_when_underpowered() -> None:
    """``run_arm`` enforces the guard up front: ``n < 1000`` raises before any twin runs (R2.4).

    Using ``n=10`` proves the guard fires early — no 1000-scenario execution is needed to
    observe the refusal.

    **Validates: Requirements 2.4**
    """
    spy = _SpyPolicy()
    with pytest.raises(ValueError, match="INV-TW-002"):
        UpliftHarness().run_arm(TINY_SCENARIO, spy, n=10)

    # The guard fired before the loop ran, so the spy was never asked to decide.
    assert spy.observations == []
