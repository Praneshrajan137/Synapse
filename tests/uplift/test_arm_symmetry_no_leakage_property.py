"""Property-based test that both arms run under identical cadence, costs, and twin.

Feature: core-purpose-uplift, Property 18: Arms run under identical cadence, costs, and
twin construction (no asymmetry, no leakage).

    *For any* scenario, seed, and arm, ``run_closed_loop`` applies the identical
    ``LoopConfig`` cadence, the identical ``_derive_unit_costs`` unit costs, and the
    identical seeded twin construction, and presents the consensus and baseline arms an
    ``Observation`` exposing the identical field set — so no arm-asymmetry favors one arm
    and no arm receives privileged information.

    Requirement 6.3: "THE Uplift_Harness SHALL apply the identical closed-loop cadence,
    unit-cost derivation, and twin construction to the Consensus_Arm and every
    Baseline_Arm, so that no arm-asymmetry favors one arm."

    Requirement 6.8: "THE Consensus_Arm and Baseline_Arm SHALL observe only the same twin
    state fields, so that no arm receives privileged information (no leakage)."

The two arms are recording stub policies — one named ``consensus`` (the name result
assembly identifies the consensus arm by), one named as a pre-registered baseline — that
capture every ``Observation`` they are handed and return the identical neutral
``PolicyAction``. Because the decisions are identical, any per-step difference between the
two captured observation streams can only come from arm-asymmetric cadence, costs, or twin
construction. Horizons are short (2–3 steps), no consensus is assembled, and no socket is
opened, so the property stays fast and $0.

**Validates: Requirements 6.3, 6.8**
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams

from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    LoopConfig,
    _derive_unit_costs,
    replicate_seed,
    run_closed_loop,
)
from uplift.interfaces import Observation, PolicyAction, Scenario

# The pre-registered baseline arm names; the consensus arm is ``DEFAULT_CONSENSUS_ARM``.
_BASELINE_ARMS: tuple[str, ...] = (
    "par_level_reorder",
    "static_pricing",
    "greedy_routing",
    "no_op_disruption",
)

# The exact field set an ``Observation`` exposes — the whole of what any arm may see.
_OBSERVATION_FIELDS: frozenset[str] = frozenset(f.name for f in dataclasses.fields(Observation))


class _RecordingPolicy:
    """A ``DecisionPolicy`` that captures each ``Observation`` and decides neutrally.

    Returning the identical neutral ``PolicyAction()`` for both arms holds the *decision*
    constant, so the captured observation streams isolate exactly what the harness itself
    supplies each arm (cadence, unit costs, twin state).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.observations: list[Observation] = []

    def decide(self, obs: Observation) -> PolicyAction:
        self.observations.append(obs)
        return PolicyAction()


def _snapshot(obs: Observation) -> dict[str, object]:
    """A comparable, field-complete view of an ``Observation``."""
    return {
        "inventory": dict(obs.inventory),
        "sim_time": obs.sim_time,
        "delivery_count": obs.delivery_count,
        "spoilage_count": obs.spoilage_count,
        "stockout_count": obs.stockout_count,
        "unit_costs": dict(obs.unit_costs),
        "active_shock": obs.active_shock,
        "pending_order": obs.pending_order,
        "eligible_stores": obs.eligible_stores,
    }


# ---------------------------------------------------------------------------
# Strategies — bounded, twin-safe shocks over short horizons
# ---------------------------------------------------------------------------
_multiplier = st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False)


@st.composite
def _shocks(draw: st.DrawFn) -> ShockParams:
    return ShockParams(
        demand_multiplier=draw(_multiplier),
        lead_time_multiplier=draw(_multiplier),
        failure_rate_multiplier=draw(_multiplier),
        spoilage_rate_multiplier=draw(_multiplier),
    )


def test_unit_cost_derivation_takes_no_arm_argument() -> None:
    """Structural half of R6.3: unit costs cannot depend on which arm is running."""
    assert list(inspect.signature(_derive_unit_costs).parameters) == []
    assert _derive_unit_costs() == _derive_unit_costs()


# ``max_examples`` is deliberately NOT hardcoded: every example drives the real seeded
# twin twice (once per arm), so the count is inherited from the active Hypothesis profile
# (see the root ``conftest.py``) — ``dev`` = 10 for light local runs, ``ci``/``default`` =
# 500 for the CI budget that satisfies the >= 100-iteration obligation.
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(
    base_seed=st.integers(min_value=0, max_value=2**31 - 1),
    index=st.integers(min_value=0, max_value=10_000),
    shock=_shocks(),
    cold_start=st.booleans(),
    n_steps=st.integers(min_value=2, max_value=3),
    baseline_name=st.sampled_from(_BASELINE_ARMS),
)
def test_arms_share_cadence_costs_twin_and_observation_fields(
    base_seed: int,
    index: int,
    shock: ShockParams,
    cold_start: bool,
    n_steps: int,
    baseline_name: str,
) -> None:
    """Property 18: no arm-asymmetry in cadence/costs/twin, and no privileged fields.

    **Validates: Requirements 6.3, 6.8**
    """
    scenario = Scenario(
        name="prop18", seed=base_seed, shock=shock, cold_start=cold_start
    )
    seed = replicate_seed(scenario.seed, index)
    loop = LoopConfig(duration_hours=float(n_steps), step_hours=1.0)

    consensus = _RecordingPolicy(DEFAULT_CONSENSUS_ARM)
    baseline = _RecordingPolicy(baseline_name)

    consensus_run = run_closed_loop(
        scenario, consensus, seed=seed, arm_name=consensus.name, loop_config=loop
    )
    baseline_run = run_closed_loop(
        scenario, baseline, seed=seed, arm_name=baseline.name, loop_config=loop
    )

    # Both arms completed, so the comparison below is over real runs (no fabrication).
    assert consensus_run.failed is False, consensus_run.error
    assert baseline_run.failed is False, baseline_run.error
    assert consensus_run.arm == DEFAULT_CONSENSUS_ARM
    assert baseline_run.arm == baseline_name

    # R6.3 — identical cadence: each arm is asked to decide exactly ``n_steps`` times.
    assert len(consensus.observations) == loop.n_steps
    assert len(baseline.observations) == loop.n_steps

    expected_costs = _derive_unit_costs()
    for obs in (*consensus.observations, *baseline.observations):
        # R6.8 — the observation exposes exactly the declared field set: no arm is handed
        # an extra channel, and none is denied one.
        assert frozenset(f.name for f in dataclasses.fields(obs)) == _OBSERVATION_FIELDS
        # R6.3 — identical unit-cost derivation for every arm at every step.
        assert dict(obs.unit_costs) == expected_costs

    # R6.3/R6.8 — step by step, the two arms see the identical twin state: the same
    # seeded twin construction, the same shock, and the same field values throughout.
    for step, (from_consensus, from_baseline) in enumerate(
        zip(consensus.observations, baseline.observations)
    ):
        assert _snapshot(from_consensus) == _snapshot(from_baseline), (
            f"arm-asymmetric observation at step {step}"
        )

    # R6.8 — no leakage: the arm identity never reaches the observation, so a policy
    # cannot condition on which arm it is (nor on the other arm's state).
    for obs in (*consensus.observations, *baseline.observations):
        snapshot_text = repr(_snapshot(obs))
        assert DEFAULT_CONSENSUS_ARM not in snapshot_text
        assert baseline_name not in snapshot_text
        assert not any("arm" in name for name in _OBSERVATION_FIELDS)

    # R6.3 — identical seeded twin construction: same derived seed in, and with the
    # decisions held identical the resulting KPI vectors coincide exactly.
    assert consensus_run.seed == baseline_run.seed == seed
    assert dataclasses.asdict(consensus_run.kpis) == dataclasses.asdict(baseline_run.kpis)
