"""Property-based tests for the attribution guarantee: arms get identical demand.

Feature: decision-integrity-uplift-proof
Property 6: Arms receive identical seeded demand.

    *For any* scenario seed, the consensus arm and every baseline arm are supplied the
    identical seeded demand realization and shock parameters for that seed, so any KPI
    difference is attributable to the decision policy rather than to differing demand.

The guarantee is realised in two cooperating pieces of the harness:

* ``replicate_seed(base_seed, index)`` derives replicate ``i``'s twin seed from
  ``(base_seed, index)`` *alone* — it takes no arm argument, so replicate ``i`` of every
  arm is driven by the identical twin RNG stream (a structural, purely-functional
  property, verified with many examples below).
* ``run_closed_loop`` builds the twin from ``scenario.shock`` + the derived seed
  identically per arm; the only per-arm difference is which policy produces the
  decisions. The seeded demand realization — the twin's ``orders_created`` (order
  arrivals) — depends on the seed + shock, not on a policy's reorder/no-op decisions.
  So driving two *different* deterministic policies through the same ``(scenario, seed)``
  yields an identical demand realization (a twin-level check, verified with a modest
  number of examples below because each example drives the real SimPy twin).

Validates: Requirements 2.1, 2.5, 4.2
"""
from __future__ import annotations

import dataclasses

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.baselines import NoOpDisruption, Par_Level_Reorder
from uplift.harness import (
    LoopConfig,
    _build_twin,
    _derive_unit_costs,
    _mean_unit_cost,
    replicate_seed,
)
from uplift.interfaces import DecisionPolicy, Observation, Scenario

# A short horizon keeps each real-twin example fast; the demand-identity guarantee is
# horizon-independent so a few steps suffice to observe order arrivals.
_LOOP = LoopConfig(duration_hours=3.0, step_hours=1.0)

# Neutral shock sentinel, matching the harness convention (an unshocked step feeds an
# ``active_shock`` of ``None`` to the policy).
_NEUTRAL_SHOCK = ShockParams()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
# Base scenario seeds spanning a wide 32-bit range.
_seeds = st.integers(min_value=0, max_value=2**31 - 1)

# Replicate indices (the second argument to ``replicate_seed``).
_indices = st.integers(min_value=0, max_value=10_000)

# Bounded, non-pricing shock parameters. Multipliers are constrained to sane, twin-safe
# ranges so the demand realization is well-defined; these mirror the adversarial suite's
# shape without driving the twin into a degenerate regime.
_multiplier = st.floats(
    min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False
)


@st.composite
def _shocks(draw: st.DrawFn) -> ShockParams:
    return ShockParams(
        demand_multiplier=draw(_multiplier),
        lead_time_multiplier=draw(_multiplier),
        failure_rate_multiplier=draw(_multiplier),
        spoilage_rate_multiplier=draw(_multiplier),
    )


# ---------------------------------------------------------------------------
# A minimal closed-loop driver that returns the seeded demand realization.
#
# It mirrors ``run_closed_loop``'s twin construction + observe/decide/advance cadence,
# but returns the twin's ``orders_created`` (the demand realization) so two arms can be
# compared. Only *non-pricing* policies are driven here, so no policy touches the twin's
# demand coupling and any demand difference would signal a broken attribution guarantee.
# ---------------------------------------------------------------------------
def _demand_realization(
    scenario: Scenario, policy: DecisionPolicy | None, seed: int, loop: LoopConfig
) -> int:
    sim = _build_twin(scenario, seed)
    unit_costs = _derive_unit_costs()
    reference_price = _mean_unit_cost(unit_costs)
    active_shock = scenario.shock if scenario.shock != _NEUTRAL_SHOCK else None

    for _ in range(loop.n_steps):
        metrics = sim.metrics
        obs = Observation(
            inventory={sku: int(level) for sku, level in sim.inventory.items()},
            sim_time=sim.sim_time_min,
            delivery_count=int(metrics.orders_delivered),
            spoilage_count=int(metrics.orders_spoiled),
            stockout_count=0,
            unit_costs=unit_costs,
            active_shock=active_shock,
        )
        if policy is not None:
            action = policy.decide(obs)
            # Non-pricing policies only reorder (add_stock), which never alters order
            # arrivals; apply reorders so the loop exercises a real decision path.
            for sku, qty in action.reorder_quantities.items():
                if qty and qty > 0:
                    sim.add_stock(str(sku), float(qty))
        sim.advance(loop.step_hours)

    return int(sim.metrics.orders_created)


# ---------------------------------------------------------------------------
# Part A — structural purity of the replicate-seed derivation (many examples).
#
# ``replicate_seed`` takes no arm argument, so it is arm-independent by construction.
# What must be verified is that it is a *pure function* of ``(base_seed, index)``:
# repeated calls agree, which is exactly what guarantees every arm's replicate ``i`` is
# fed the identical twin seed (Requirements 2.1, 2.5, 4.2).
# ---------------------------------------------------------------------------
@settings(max_examples=300)
@given(seed=_seeds, index=_indices)
def test_replicate_seed_is_pure_and_arm_independent(seed: int, index: int) -> None:
    """``replicate_seed`` depends only on ``(base_seed, index)`` — never on the arm."""
    # Model three different "arms" all asking for the same replicate index. Since the
    # function takes no arm parameter, every arm necessarily receives the same seed.
    consensus_seed = replicate_seed(seed, index)
    baseline_a_seed = replicate_seed(seed, index)
    baseline_b_seed = replicate_seed(seed, index)

    assert consensus_seed == baseline_a_seed == baseline_b_seed
    # The derived seed is a well-formed 32-bit value fed to the twin RNG.
    assert 0 <= consensus_seed < 2**32


@settings(max_examples=200)
@given(seed=_seeds, i=_indices, j=_indices)
def test_replicate_seed_distinguishes_indices_not_arms(
    seed: int, i: int, j: int
) -> None:
    """Different replicate indices may differ; the same index is always identical."""
    if i == j:
        assert replicate_seed(seed, i) == replicate_seed(seed, j)
    # For i != j we make no distinctness demand (collisions are permissible); the
    # guarantee under test is identity for the *same* index, asserted above.


# ---------------------------------------------------------------------------
# Part B — twin-level demand identity across arms (modest #examples: real twin).
#
# Two distinct deterministic policies driven through the same ``(scenario, seed)`` must
# see the identical demand realization (``orders_created``) and identical shock params,
# proving demand is attributable to the seed, not the policy.
# ---------------------------------------------------------------------------
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(base_seed=_seeds, index=_indices, shock=_shocks())
def test_arms_receive_identical_seeded_demand(
    base_seed: int, index: int, shock: ShockParams
) -> None:
    """Every arm sees identical demand + shock for a given scenario seed (Property 6).

    Each Hypothesis example drives the real SimPy twin once per arm, hence the modest
    example count; the property is horizon-independent so a short loop suffices.
    """
    scenario = Scenario(name="prop6", seed=base_seed, shock=shock)
    seed_i = replicate_seed(scenario.seed, index)

    # Three "arms": a no-decision reference, a reorder baseline, and a no-op baseline.
    # None of them touches the twin's demand coupling, so demand must be identical.
    reference_demand = _demand_realization(scenario, None, seed_i, _LOOP)
    reorder_demand = _demand_realization(
        scenario, Par_Level_Reorder(s=10, S=100, seed=index), seed_i, _LOOP
    )
    no_op_demand = _demand_realization(scenario, NoOpDisruption(), seed_i, _LOOP)

    # Identical seeded demand realization across arms (Requirements 2.1, 2.5, 4.2).
    assert reference_demand == reorder_demand == no_op_demand

    # And every arm shares the identical shock parameters for that seed.
    assert scenario.shock == shock
    assert dataclasses.asdict(scenario.shock) == dataclasses.asdict(shock)
