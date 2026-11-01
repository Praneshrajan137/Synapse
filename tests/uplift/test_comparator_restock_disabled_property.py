"""The comparator runs with the twin's own restock disabled and recorded.

Feature: decision-quality-proof, Property 53: The comparator runs with the twin's own
restock disabled and recorded.

Task 9.12. Subject: ``uplift/harness.py::_build_twin`` and
``digital_twin/simulation/policy.py`` (R5.36).

**The bias this exists to prevent.** ``SupplyChainSimulation.start()`` leaves
``_restock_threshold`` at its constructor default of ``50.0``. So a compared ``(s, S)`` policy
reaching the twin through the uplift harness was measured **stacked on top of the twin's own
endogenous ``(s, S)`` restock**. That biases regret toward zero *independently of whether the
world is easy* -- which would make E2b's null result uninterpretable in exactly the way this
entire phase exists to prevent. A measurement whose instrument silently helps the baseline
cannot distinguish "the baseline is near-optimal" from "we replenished for it".

Two clauses, and the second is the one that makes the first enforceable:

1. The comparator's twin runs with the endogenous restock **disabled**, not merely lowered.
   ``set_policy`` clamps with ``max(0.0, ...)`` so ``0.0`` is reachable, and at ``0.0`` the
   engine's ``if level < safety_stock`` guard is false for every clamped level.
2. The value is **read from the committed policy file**, never inlined (AD-13), and the reader
   **refuses to default a missing key**. A default would substitute an unreviewed number for a
   committed one -- reintroducing at the reader precisely the defect the policy file removes.

``@pytest.mark.slow`` -- constructs the real twin through the harness seam. Selected by
``ci.yml::uplift-verify``'s slow step (``tests/uplift`` is in that step's path list).

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal here.**
"""

from __future__ import annotations

import logging

import pytest
import structlog
from hypothesis import given, settings
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from digital_twin.simulation.policy import (
    POLICY_PATH,
    PolicyUnavailableError,
    comparator_restock_threshold,
    load_policy,
    require,
)
from uplift.harness import _build_twin
from uplift.interfaces import Scenario

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

pytestmark = pytest.mark.slow

_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)


def _scenario(seed: int, *, cold_start: bool = False) -> Scenario:
    return Scenario(name="prop53", seed=seed, shock=ShockParams(), cold_start=cold_start)


def test_the_committed_threshold_disables_rather_than_lowers() -> None:
    """``0.0`` is not merely a small threshold -- it turns the endogenous restock off."""
    assert comparator_restock_threshold() == 0.0


@settings(deadline=None)
@given(seed=_SEEDS)
def test_a_comparator_twin_never_restocks_itself(seed: int) -> None:
    """The behavioural consequence: no endogenous restock fires during a comparator run.

    Asserted on behaviour rather than on the private attribute, because a threshold that is set
    but not honoured would satisfy an attribute check and still bias the measurement.
    """
    sim = _build_twin(_scenario(seed), seed)
    sim.advance(24.0)

    assert sim.metrics.restocks_triggered == 0, (
        "the twin replenished itself during a comparator run, so any regret measured here is "
        "biased toward zero by the twin's own (s, S) policy"
    )


@settings(deadline=None)
@given(seed=_SEEDS)
def test_the_comparator_twin_can_run_out_of_stock(seed: int) -> None:
    """With replenishment off, a 24h run exhausts the opening 1000 units and says so.

    This is the positive control for clause 1: if the endogenous restock were still active, the
    shelf would refill and this assertion would fail -- which is exactly the silent condition
    that previously made the comparison meaningless.
    """
    sim = _build_twin(_scenario(seed), seed)
    sim.advance(24.0)
    metrics = sim.metrics

    assert metrics.demand_events > 0
    assert metrics.unmet_demand_events > 0, "a starved twin must record unmet demand"
    assert metrics.fill_rate < 1.0
    assert metrics.orders_delivered <= 1000.0, (
        "deliveries exceeded the opening stock, so something replenished it"
    )


@settings(deadline=None)
@given(seed=_SEEDS)
def test_cold_start_measures_total_stockout_rather_than_silence(seed: int) -> None:
    """The cold-start scenario keeps its catalogue, so a total stockout is reportable.

    This pins the defect task 9.6 found: ``_apply_cold_start`` used to ``.clear()`` the
    inventory, which -- once a stockout cost something -- meant no demand event was recorded at
    all and BOTH ``fill_rate`` and ``stockout_rate`` reported ``0.0`` for a city where every
    order fails. Zeroing the levels while keeping the keys is what makes the truth sayable.
    """
    sim = _build_twin(_scenario(seed, cold_start=True), seed)
    assert sim.inventory, "cold start must keep the catalogue, only zero the levels"
    assert all(level == 0.0 for level in sim.inventory.values())

    sim.advance(8.0)
    metrics = sim.metrics

    assert metrics.demand_events > 0, "demand must be observed against a known catalogue"
    assert metrics.unmet_demand_events == metrics.demand_events
    assert metrics.stockout_rate == pytest.approx(1.0)
    assert metrics.fill_rate == pytest.approx(0.0)


def test_the_threshold_is_read_from_the_committed_file_not_inlined() -> None:
    """AD-13: the number lives in the declaration, and the code resolves it."""
    document = load_policy()
    assert require(document, "comparator.restock_threshold") == 0.0
    assert POLICY_PATH.name == "policy.yaml"


def test_a_missing_committed_value_is_refused_never_defaulted() -> None:
    """The reader raises naming the key rather than substituting a plausible number.

    A silent default is how a run ends up judged against a value nobody committed, which is the
    whole failure mode the policy file and its pins exist to close. The error must name the key
    so the repair is obvious from the message alone.
    """
    with pytest.raises(PolicyUnavailableError, match="comparator.absent_key"):
        require(load_policy(), "comparator.absent_key")

    with pytest.raises(PolicyUnavailableError, match="not defaulted|NOT defaulted"):
        require(load_policy(), "comparator.absent_key")


def test_the_deferred_thresholds_are_named_rather_than_placeheld() -> None:
    """R5.2's deferral is recorded, and no placeholder value stands in for a measurement.

    A placeholder would be *judged against*, which is precisely what R5.2 forbids: the
    materiality margin may only be committed after task 10.3 measures it.
    """
    deferred = require(load_policy(), "deferred")

    assert "materiality_margin" in deferred
    # Each deferred entry is prose naming its owning task, not a number.
    for key, value in deferred.items():
        assert isinstance(value, str), f"deferred.{key} holds a value, not a deferral note"
        assert "task" in value.lower(), f"deferred.{key} does not name its owning task"
