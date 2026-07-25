"""Property-based test that identical seeds reproduce within the noise tolerance.

Feature: core-purpose-uplift, Property 11: Identical seeds reproduce within the
committed noise tolerance.

    *For any* seed configuration, two runs of the harness on the identical seeds produce
    ``headline_uplift`` values that differ by no more than 1.0 percentage point (and,
    being seed-deterministic, by 0.0 under identical stubs).

    Requirement 3.3: "WHEN the same proof configuration and seeds are run twice, THE
    Uplift_Harness SHALL produce Headline_Uplift values differing by no more than the
    committed noise tolerance of 1.0 percentage point."

Cost control (design "Cost management"): this property deliberately does **not** stand
up the real four-tier consensus network and does **not** perform a powered
(``MIN_SCENARIOS`` = 1000) run — both are far too slow for a 100-example property. It
instead drives the real seeded SimPy twin through the real
:class:`~uplift.harness.UpliftHarness` loop with *deterministic stub policies* over a
short horizon and a handful of replicates, with the INV-TW-002 power floor bypassed on a
test-only subclass (that floor is Property 10's subject). The measured quantity is the
same one the reproduction commits to: ``UpliftResult.headline_uplift`` produced by the
real :func:`~uplift.harness.assemble_uplift_result` under the pre-registered metric
contract. Everything runs in-process on synthetic seeds, no sockets, $0.

**Validates: Requirements 3.3**
"""
from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams

from uplift.cli import NOISE_TOLERANCE_PP
from uplift.contract import load_contract
from uplift.fidelity import FidelityReport
from uplift.harness import (
    DEFAULT_CONSENSUS_ARM,
    LoopConfig,
    UpliftHarness,
    assemble_uplift_result,
)
from uplift.interfaces import Observation, PolicyAction, Scenario

# Reduced-cost configuration: one seeded scenario, two arms, two replicates each, over a
# short closed-loop horizon. Each Hypothesis example therefore drives the twin 8 times
# (2 runs x 1 scenario x 2 arms x 2 replicates).
_REPLICATES = 2
_LOOP = LoopConfig(duration_hours=0.6, step_hours=0.3)

# The pre-registered contract is fixed input to the measurement; load it once.
_CONTRACT = load_contract()

# A fixed fidelity report so the headline number depends only on the seeds and the
# stub policies (the live C34 gauge is Property 20's subject, not this one).
_FIDELITY = FidelityReport(kl_divergence=0.05, threshold=0.1)

_BASELINE_ARM = "stub_baseline"

# Shock multipliers kept in a modest band: the shock must be real (it feeds TwinConfig
# and the engine constructor) without exploding the event count per run.
_multiplier = st.floats(min_value=0.8, max_value=1.5, allow_nan=False, allow_infinity=False)


class _DeterministicStub:
    """A deterministic ``DecisionPolicy`` — a pure function of the observation.

    Stands in for a real arm: it prices off the observed unit costs and reorders a fixed
    quantity for every SKU at or below a threshold. It holds no RNG and no mutable
    state, so two runs at the same seed see the identical decision sequence and any
    run-to-run headline difference must come from the harness/twin, not the policy.
    """

    def __init__(self, name: str, price_factor: float, reorder_qty: float) -> None:
        self.name = name
        self._price_factor = price_factor
        self._reorder_qty = reorder_qty

    def decide(self, obs: Observation) -> PolicyAction:
        costs = obs.unit_costs
        mean_cost = math.fsum(costs.values()) / len(costs) if costs else 1.0
        price = round(mean_cost * self._price_factor, 6)
        reorders = {
            sku: self._reorder_qty
            for sku in sorted(obs.inventory)
            if obs.inventory[sku] <= 100
        }
        return PolicyAction(price=price, reorder_quantities=reorders)


class _UnpoweredHarness(UpliftHarness):
    """Harness with the INV-TW-002 power floor bypassed for reduced-cost runs.

    Only the ``n >= MIN_SCENARIOS`` guard is relaxed (Property 10 owns that guard); the
    seed derivation, the closed loop, the twin, and the aggregation all run verbatim.
    """

    @staticmethod
    def _check_power(n: int) -> None:  # type: ignore[override]
        return None


def _headline_for_seeds(
    scenario: Scenario, consensus_factor: float, baseline_factor: float
) -> float:
    """Run the reduced-cost harness once on ``scenario`` and return the headline number."""
    arms = [
        _DeterministicStub(DEFAULT_CONSENSUS_ARM, consensus_factor, 8.0),
        _DeterministicStub(_BASELINE_ARM, baseline_factor, 4.0),
    ]
    harness = _UnpoweredHarness(loop_config=_LOOP)
    harness_result = harness.run([scenario], arms, _REPLICATES, parallel=False)
    result = assemble_uplift_result(
        harness_result,
        _CONTRACT,
        fidelity=_FIDELITY,
        consensus_arm=DEFAULT_CONSENSUS_ARM,
    )
    return float(result.headline_uplift)


# Feature: core-purpose-uplift, Property 11: Identical seeds reproduce within the
# committed noise tolerance.
# ``max_examples`` is deliberately NOT hardcoded: this property drives the real seeded
# twin twice per example, so it inherits the active Hypothesis profile (see the root
# ``conftest.py``) — ``dev`` = 10 examples for light local runs, ``ci``/``default`` = 500
# for the CI budget that actually satisfies the >= 100-iteration obligation.
@pytest.mark.slow
@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    demand_multiplier=_multiplier,
    lead_time_multiplier=_multiplier,
    cold_start=st.booleans(),
    consensus_factor=st.floats(min_value=0.5, max_value=3.0, allow_nan=False),
    baseline_factor=st.floats(min_value=0.5, max_value=3.0, allow_nan=False),
)
def test_identical_seeds_reproduce_within_noise_tolerance(
    seed: int,
    demand_multiplier: float,
    lead_time_multiplier: float,
    cold_start: bool,
    consensus_factor: float,
    baseline_factor: float,
) -> None:
    """Two runs of the same seed configuration agree within the committed tolerance.

    **Validates: Requirements 3.3**
    """
    scenario = Scenario(
        name="prop11",
        seed=seed,
        shock=ShockParams(
            demand_multiplier=demand_multiplier,
            lead_time_multiplier=lead_time_multiplier,
        ),
        cold_start=cold_start,
    )

    first = _headline_for_seeds(scenario, consensus_factor, baseline_factor)
    second = _headline_for_seeds(scenario, consensus_factor, baseline_factor)

    # The headline is always a real number, so the comparison below is meaningful.
    assert math.isfinite(first) and math.isfinite(second)

    delta = abs(first - second)

    # R3.3 — the committed tolerance, read from the version-controlled constant.
    assert NOISE_TOLERANCE_PP <= 1.0
    assert delta <= NOISE_TOLERANCE_PP, (
        f"run-to-run headline delta {delta} pp exceeds the committed noise tolerance "
        f"{NOISE_TOLERANCE_PP} pp for seed {seed}"
    )

    # Being seed-deterministic under identical stubs, the two runs agree exactly.
    assert delta == 0.0, (
        f"identical seeds produced different headlines: {first} vs {second} "
        f"(seed {seed})"
    )
