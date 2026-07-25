"""Property-based test that an unavailable arm yields an honest failed run.

Feature: core-purpose-uplift, Property 3: Unavailable consensus is an honest failed run,
never a fabricated decision.

    *For any* arm whose ``decide`` raises (e.g.
    :class:`~uplift.consensus_arm.ConsensusArmUnavailable`),
    :func:`uplift.harness.run_closed_loop` returns a
    :class:`~uplift.interfaces.ScenarioRun` with ``failed=True``, ``kpis=None``, and a
    non-empty ``error``, and never a completed run — so the command degrades to honest
    failure rather than crashing or fabricating a decision.

The generator covers the whole failure surface the CLI can hit in a plain environment:
the unavailability exception the real consensus arm raises, plus arbitrary other policy
exceptions; a raise on the very first step (the ``_UnavailableConsensusArm`` case, where
*every* ``decide`` fails) as well as a raise part-way through the horizon (a mid-run
network loss); shocked and cold-start scenarios; and empty exception messages, so the
``error`` string must stay non-empty on its own (the harness prefixes the exception type).

Kept fast by using a stub policy whose ``decide`` raises: the twin is built and started,
the stub raises, and the loop exits immediately — no real models, no sockets, no paid
services (I-1).

Validates: Requirements 1.5, 7.5, 9.6
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams

from uplift.consensus_arm import ConsensusArmUnavailable
from uplift.harness import DEFAULT_CONSENSUS_ARM, LoopConfig, run_closed_loop
from uplift.interfaces import Observation, PolicyAction, Scenario, ScenarioRun


# The exception types a decide call can realistically raise: the honest-unavailability
# signal the assembled consensus arm raises (R1.5), plus unrelated failures that must be
# handled identically (R7.5).
_EXCEPTION_TYPES = (
    ConsensusArmUnavailable,
    RuntimeError,
    ValueError,
    TimeoutError,
    KeyError,
)


class _RaisingPolicy:
    """A ``DecisionPolicy`` whose ``decide`` raises, mimicking an unavailable arm.

    ``fail_at_step`` selects which ``decide`` call raises: ``0`` reproduces
    ``cli._UnavailableConsensusArm`` (every decision fails), a later index reproduces an
    arm that loses its network mid-horizon. Calls before the failing step return an empty
    (no-op) :class:`PolicyAction` so the loop really does reach the failing step.
    """

    def __init__(
        self,
        name: str,
        exc_type: type[BaseException],
        message: str,
        fail_at_step: int,
    ) -> None:
        self.name = name
        self.exc_type = exc_type
        self._message = message
        self._fail_at_step = fail_at_step
        self.calls = 0

    def decide(self, obs: Observation) -> PolicyAction:
        index = self.calls
        self.calls += 1
        if index >= self._fail_at_step:
            raise self.exc_type(self._message)
        return PolicyAction()


@st.composite
def _failing_runs(draw: st.DrawFn) -> tuple[Scenario, _RaisingPolicy, int, LoopConfig]:
    """A scenario, a raising policy, a replicate seed, and a short loop cadence."""
    multiplier = st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False)
    scenario = Scenario(
        name=draw(st.sampled_from(["demand-spike", "supplier-default", "cold-start-city"])),
        seed=draw(st.integers(min_value=0, max_value=2**31 - 1)),
        shock=ShockParams(
            demand_multiplier=draw(multiplier),
            lead_time_multiplier=draw(multiplier),
            failure_rate_multiplier=draw(multiplier),
            spoilage_rate_multiplier=draw(multiplier),
        ),
        cold_start=draw(st.booleans()),
    )
    # A short horizon keeps every example cheap; 1-3 steps is enough to cover both an
    # immediate failure and a mid-horizon one.
    loop_config = LoopConfig(
        duration_hours=float(draw(st.integers(min_value=1, max_value=3))), step_hours=1.0
    )
    policy = _RaisingPolicy(
        name=draw(st.sampled_from([DEFAULT_CONSENSUS_ARM, "consensus-unavailable"])),
        exc_type=draw(st.sampled_from(_EXCEPTION_TYPES)),
        # An empty message is included on purpose: ``error`` must still be non-empty.
        message=draw(st.sampled_from(["", "transport unavailable", "no proposals"])),
        fail_at_step=draw(st.integers(min_value=0, max_value=loop_config.n_steps - 1)),
    )
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    return scenario, policy, seed, loop_config


# ``max_examples`` is deliberately NOT hardcoded: every example builds and starts the
# real seeded twin, so the count is inherited from the active Hypothesis profile (see the
# root ``conftest.py``) — ``dev`` = 10 for light local runs, ``ci``/``default`` = 500 for
# the CI budget that satisfies the >= 100-iteration obligation.
@pytest.mark.slow
@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case=_failing_runs())
def test_raising_arm_yields_honest_failed_run(
    case: tuple[Scenario, _RaisingPolicy, int, LoopConfig],
) -> None:
    """A raising ``decide`` always produces a failed, KPI-free, diagnosed run.

    **Validates: Requirements 1.5, 7.5, 9.6**
    """
    scenario, policy, seed, loop_config = case

    run = run_closed_loop(
        scenario,
        policy,
        seed=seed,
        arm_name=policy.name,
        loop_config=loop_config,
    )

    # The loop never crashes: it returns a ScenarioRun for the attempted arm/seed.
    assert isinstance(run, ScenarioRun)
    assert run.arm == policy.name
    assert run.seed == seed

    # Honest failure: recorded as failed, with no fabricated KPIs and a diagnostic reason.
    assert run.failed is True
    assert run.kpis is None
    assert run.error is not None
    assert run.error.strip() != ""
    # The reason names the underlying failure so the operator can diagnose it.
    assert policy.exc_type.__name__ in run.error

    # Never a completed run: the raising arm contributes no sample.
    assert not (run.failed is False and run.kpis is not None)
