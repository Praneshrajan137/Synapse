"""The time-weighted on-hand measure is a correct integral.

Feature: decision-quality-proof, Property 50: The time-weighted on-hand measure is a
correct integral.

Task 9.9. Subject: ``SimulationMetrics.inventory_minutes`` / ``avg_on_hand_units`` (R5.40).

This is the **holding term** of ADR-055's regret objective and the KPI R5.28's third
single-objective policy minimises. Without it the classic ``(s, S)`` cost objective is not
derivable at all: ``SimulationMetrics`` carried six counters and no inventory-*time* term, so
"how much stock did we hold, and for how long" had no answer.

**Deliberately NOT ``@pytest.mark.slow``**, and the design follows from that. Locus is
``ci.yml::quality-gates`` (``-m "not slow"`` over ``digital_twin`` at the ``default`` budget),
so every case here must be cheap. They are: each run uses
``start(external_demand=True)`` with **no injected orders**, so the demand process is off and
inventory is constant. The integral is then exact closed-form arithmetic --
``sum(levels) * elapsed`` -- rather than an emergent property of a twin run, which makes the
assertions exact equalities instead of tolerances and costs microseconds instead of seconds.

Verified while authoring: ``ci.yml::quality-gates`` collects ``digital_twin`` without the
marker, so this file is selected there. A test placed here *with* a slow marker would be
selected by that job's ``-m "not slow"`` filter **not at all**, and by ``uplift-verify``'s slow
step only because it also collects ``digital_twin/tests`` -- so the marker decision is not
cosmetic.

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal here.**
"""

from __future__ import annotations

import logging

import pytest
import structlog
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.engine import SupplyChainSimulation

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)
_LEVELS = st.dictionaries(
    keys=st.sampled_from([f"sku_{i}" for i in range(6)]),
    values=st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=6,
)
_HOURS = st.floats(min_value=0.5, max_value=48.0, allow_nan=False, allow_infinity=False)


def _quiet_twin(levels: dict[str, float], seed: int) -> SupplyChainSimulation:
    """A twin with no demand and no replenishment, so inventory is constant.

    ``external_demand=True`` turns the endogenous Poisson arrivals off, and no order is
    injected, so nothing consumes stock. ``restock_threshold=0.0`` disables the endogenous
    restock. What remains is a clock advancing over a fixed inventory -- exactly the shape in
    which the integral has a closed form.
    """
    sim = SupplyChainSimulation(seed=seed)
    sim.start(external_demand=True, initial_inventory=levels)
    sim.set_policy(restock_threshold=0.0)
    return sim


@given(levels=_LEVELS, hours=_HOURS, seed=_SEEDS)
def test_the_integral_is_exact_over_constant_inventory(
    levels: dict[str, float], hours: float, seed: int
) -> None:
    """With inventory constant, ``inventory_minutes == sum(levels) * elapsed`` exactly."""
    sim = _quiet_twin(levels, seed)
    sim.advance(hours)

    expected = sum(levels.values()) * (hours * 60.0)
    assert sim.metrics.inventory_minutes == pytest.approx(expected, rel=1e-9, abs=1e-9)


@given(levels=_LEVELS, hours=_HOURS, seed=_SEEDS)
def test_avg_on_hand_recovers_the_mean_level(
    levels: dict[str, float], hours: float, seed: int
) -> None:
    """Dividing the integral by the horizon recovers the mean held level.

    The horizon is passed in rather than stored on the metrics object, because the integral and
    the clock belong to different objects: the engine owns the clock, and duplicating it on the
    metrics would let the two drift.
    """
    sim = _quiet_twin(levels, seed)
    sim.advance(hours)

    assert sim.metrics.avg_on_hand_units(sim.sim_time_min) == pytest.approx(
        sum(levels.values()), rel=1e-9, abs=1e-9
    )


@given(levels=_LEVELS, seed=_SEEDS)
def test_the_integral_is_monotone_non_decreasing_in_time(
    levels: dict[str, float], seed: int
) -> None:
    """Stock held for longer accrues more holding cost. It can never accrue less.

    A non-monotone integral would let a policy reduce its measured holding cost simply by
    running longer, which would invert the sign of ADR-055's holding term.
    """
    sim = _quiet_twin(levels, seed)
    readings = []
    for _ in range(4):
        sim.advance(3.0)
        readings.append(sim.metrics.inventory_minutes)

    assert all(
        a <= b for a, b in zip(readings[:-1], readings[1:], strict=True)
    ), readings
    if sum(levels.values()) > 0.0:
        assert readings[0] < readings[-1], "held stock must accrue strictly over time"


@given(hours=_HOURS, seed=_SEEDS)
def test_an_empty_shelf_accrues_no_holding_cost(hours: float, seed: int) -> None:
    """Zero stock held for any duration is zero holding cost.

    The complement of the test above, and the one that catches an off-by-one that credits
    holding cost for stock that does not exist.
    """
    sim = _quiet_twin({f"sku_{i}": 0.0 for i in range(3)}, seed)
    sim.advance(hours)

    assert sim.metrics.inventory_minutes == 0.0
    assert sim.metrics.avg_on_hand_units(sim.sim_time_min) == 0.0


@given(levels=_LEVELS, seed=_SEEDS)
def test_a_zero_horizon_reports_zero_rather_than_dividing(
    levels: dict[str, float], seed: int
) -> None:
    """Before any time passes there is no mean to report, and no division is attempted."""
    sim = _quiet_twin(levels, seed)

    assert sim.metrics.inventory_minutes == 0.0
    assert sim.metrics.avg_on_hand_units(0.0) == 0.0
    assert sim.metrics.avg_on_hand_units(-1.0) == 0.0, "a rewound clock must not report a mean"


@given(levels=_LEVELS, hours=_HOURS, seed=_SEEDS)
def test_added_stock_accrues_only_for_the_time_it_was_held(
    levels: dict[str, float], hours: float, seed: int
) -> None:
    """Stock added midway accrues over the remaining horizon, not the whole of it.

    This is what the accrue-before-mutate ordering buys. Accruing *after* the mutation would
    attribute the new, higher level to the interval during which the old level actually held --
    overstating holding cost by exactly the added quantity times the elapsed time.
    """
    sim = _quiet_twin(levels, seed)
    sim.advance(hours)
    first_half = sim.metrics.inventory_minutes

    sim.add_stock("sku_0", 100.0)
    sim.advance(hours)

    base = sum(levels.values())
    minutes = hours * 60.0
    # First interval at `base`, second at `base + 100`.
    expected = base * minutes + (base + 100.0) * minutes
    assert first_half == pytest.approx(base * minutes, rel=1e-9, abs=1e-9)
    assert sim.metrics.inventory_minutes == pytest.approx(expected, rel=1e-9, abs=1e-9)
