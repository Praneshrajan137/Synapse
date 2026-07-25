"""Property-based test that the INV-TW-002 under-power guard is total over ``n``.

Feature: core-purpose-uplift, Property 10: The under-power guard is total over n.

    *For any* ``n`` in ``[0, MIN_SCENARIOS)``, ``run_arm``/``_check_power`` raises the
    INV-TW-002 under-power ``ValueError``; *for any* ``n >= MIN_SCENARIOS`` it does not
    raise.

    Requirement 3.2: "IF fewer than ``MIN_SCENARIOS`` completed scenarios per arm are
    requested through ``run_arm`` or ``run``, THEN THE Uplift_Harness SHALL raise the
    INV-TW-002 under-power error and SHALL NOT produce a proof-grade aggregation."

Totality here means the guard partitions the whole request domain with no gap and no
overlap: every ``n`` either raises (strictly below the floor) or does not (at or above
it), and the outcome is exactly ``n < MIN_SCENARIOS``.

The property is pure and fast: it exercises the guard itself. The execution seam
(``_run_sequential``) is stubbed, so no twin is built, no consensus arm is assembled, no
socket is opened, $0.

**Validates: Requirements 3.2**
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.harness import MIN_SCENARIOS, UpliftHarness, replicate_seed
from uplift.interfaces import Observation, PolicyAction, Scenario, ScenarioRun

from digital_twin.simulation.monte_carlo import ShockParams

# Under-powered requests: the half-open interval the design names, [0, MIN_SCENARIOS).
_under_powered = st.integers(min_value=0, max_value=MIN_SCENARIOS - 1)

# Powered requests: at the floor and above. Kept to a narrow band above the floor so the
# seed-derivation work per example stays bounded (the twin itself is never run).
_powered = st.integers(min_value=MIN_SCENARIOS, max_value=MIN_SCENARIOS + 32)

# Boundary values get explicit weight so the exact floor is always exercised.
_boundaries = st.sampled_from([0, 1, MIN_SCENARIOS - 1, MIN_SCENARIOS, MIN_SCENARIOS + 1])

_requests = st.one_of(_under_powered, _powered, _boundaries)


class _StubPolicy:
    """Minimal ``DecisionPolicy``; never invoked because the loop seam is stubbed."""

    name = "stub_arm"

    def decide(self, obs: Observation) -> PolicyAction:  # pragma: no cover — not run
        return PolicyAction()


class _NoTwinHarness(UpliftHarness):
    """Harness whose execution seam is stubbed out, leaving the guard intact.

    Only ``_run_sequential`` is overridden, so ``run_arm`` -> ``_run_arm_runs`` ->
    ``_check_power`` executes verbatim while no twin is ever constructed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.seed_counts: list[int] = []

    def _run_sequential(  # type: ignore[override]
        self, scenario, policy, policy_factory, arm_name, seeds
    ) -> list[ScenarioRun]:
        self.seed_counts.append(len(seeds))
        return []


def _scenario() -> Scenario:
    return Scenario(name="prop10", seed=7, shock=ShockParams())


def _assert_under_power_error(exc: pytest.ExceptionInfo[ValueError], n: int) -> None:
    """The raised error must be the INV-TW-002 under-power error, naming the numbers."""
    message = str(exc.value)
    assert "INV-TW-002" in message
    assert f"n={n}" in message
    assert str(MIN_SCENARIOS) in message


@settings(max_examples=200, deadline=None)
@given(n=_requests)
def test_under_power_guard_is_total_over_n(n: int) -> None:
    """Property 10: the guard's outcome is exactly ``n < MIN_SCENARIOS``, everywhere.

    **Validates: Requirements 3.2**
    """
    should_raise = n < MIN_SCENARIOS
    harness = _NoTwinHarness()
    policy = _StubPolicy()
    scenario = _scenario()

    # -- the guard predicate itself -------------------------------------------------
    if should_raise:
        with pytest.raises(ValueError) as exc:
            UpliftHarness._check_power(n)
        _assert_under_power_error(exc, n)
    else:
        assert UpliftHarness._check_power(n) is None

    # -- run_arm: raises iff under-powered, and produces no aggregation when it does --
    if should_raise:
        with pytest.raises(ValueError) as exc:
            harness.run_arm(scenario, policy, n, parallel=False)
        _assert_under_power_error(exc, n)
        # SHALL NOT produce a proof-grade aggregation: execution never started.
        assert harness.seed_counts == []

        # The same guard covers the full matrix entry point (``run``).
        with pytest.raises(ValueError) as exc:
            harness.run([scenario], [policy], n, parallel=False)
        _assert_under_power_error(exc, n)
        assert harness.seed_counts == []
    else:
        result = harness.run_arm(scenario, policy, n, parallel=False)
        assert result.arm == policy.name
        # Exactly ``n`` replicate seeds were derived and handed to the execution seam.
        assert harness.seed_counts == [n]


def test_guard_boundary_is_exactly_min_scenarios() -> None:
    """The partition point is the INV-TW-002 floor, not one either side of it."""
    with pytest.raises(ValueError, match="INV-TW-002"):
        UpliftHarness._check_power(MIN_SCENARIOS - 1)
    assert UpliftHarness._check_power(MIN_SCENARIOS) is None

    harness = _NoTwinHarness()
    harness.run_arm(_scenario(), _StubPolicy(), MIN_SCENARIOS, parallel=False)
    assert harness.seed_counts == [MIN_SCENARIOS]
    # The derived sequence is the standard per-scenario one (no special-casing at the floor).
    assert replicate_seed(7, 0) == replicate_seed(_scenario().seed, 0)
