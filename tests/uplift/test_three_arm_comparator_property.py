"""The comparator's judged contrast and its bound are different quantities (conflict M).

Feature: decision-quality-proof, session 5. Subject: ``uplift/foresight.py``,
``digital_twin/simulation/policy.py::comparator_reference_policy`` (R5.1, R5.2, R5.36).

**WHY THIS FILE EXISTS AT ALL, AND IT IS THE FIRST TEST ``uplift/foresight.py`` HAS EVER
HAD.** ``run_two_pass`` had exactly one consumer (``uplift/regret.py::_measure``) and no
test in the tree imported ``uplift.foresight``. So the instrument at the centre of
checkpoint A -- the one whose verdict can end this spec -- was unasserted, and three
things went unnoticed for four sessions:

* the reference arm was a NO-OP while the report called the result ``(s, S)`` regret;
* ``regret`` and ``comparator_headroom`` were the SAME subtraction, so
  ``must_be_below_measured_headroom`` admitted exactly the margins below the regret they
  would be judged against and every margin in ADR-055 D2.5's bracket forced ``material``;
* ``NoOpRecordingPolicy`` was never instantiated and ``ForesightPolicy.decide`` was never
  called, so both documented arms were prose rather than behaviour.

**The load-bearing property is the third one below.** ``headroom >= regret`` was a
tautology under the two-arm comparator -- the same subtraction on both sides -- and an
assertion that cannot fail is not an assertion (finding 26). It is a real claim only
because the two sides are now different pairs of arms, and asserting it is what keeps the
margin guard meaningful.

**And the fourth is what stops the third being vacuous.** A reference arm that never
reorders would satisfy ``headroom >= regret`` trivially by being a second no-op, and the
whole repair would be decorative. Non-emptiness is asserted for the same reason session 3
asserted it in ``test_cognition_phase``: ``set() <= anything`` is vacuously true, and a
filter that empties its subject turns a real assertion into a passing one.

**I-0.** The three twin-driving properties are ``@pytest.mark.slow``: they construct the
real SimPy twin, which is category 4 on a development machine. They are selected by
``ci.yml::uplift-verify``'s slow step, whose path list contains ``tests/uplift``. The
reader and predicate tests are NOT slow -- they read a YAML file or construct a frozen
dataclass, and they run in the local sweep.

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal here**
(CF-13), and no total is asserted.

**Validates: Requirements 5.1, 5.2, 5.36 (conflict M's repair).**
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
import structlog
import yaml
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.engine import DemandTrace, SupplyChainSimulation
from digital_twin.simulation.policy import (
    POLICY_PATH,
    PolicyUnavailableError,
    ReferencePolicySpec,
    comparator_reference_policy,
    comparator_restock_threshold,
)
from uplift.baselines.par_level_reorder import Par_Level_Reorder
from uplift.foresight import NoOpRecordingPolicy, ThreePassResult, run_three_pass
from uplift.interfaces import Observation
from uplift.regret import load_objective

if TYPE_CHECKING:
    from pathlib import Path

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

_SEEDS = st.integers(min_value=0, max_value=2**31 - 1)

#: One simulated hour is enough for every clause here: the arms are compared on the SHAPE
#: of the contrast, not on a powered estimate. The powered run is `uplift.yml::twin-regret`
#: at 200 replicates x 24 hours, and I-0 keeps that off any development machine.
_PROBE_HOURS = 1.0


def _reference_arm(seed: int) -> Par_Level_Reorder:
    """The committed reference arm, resolved from the policy file rather than invented."""
    spec = comparator_reference_policy()
    return Par_Level_Reorder(s=spec.reorder_point, S=spec.order_up_to, seed=seed)


def _cost(sim: SupplyChainSimulation) -> float:
    """The committed scalar objective for one arm -- the same call `_measure` makes."""
    objective = load_objective()
    metrics = sim.metrics
    return objective.cost(
        stockout_rate=metrics.stockout_rate,
        spoilage_rate=metrics.spoilage_rate,
        fill_rate=metrics.fill_rate,
        avg_on_hand_units=metrics.avg_on_hand_units(sim.sim_time_min),
        avg_delivery_time_min=metrics.avg_delivery_time_min,
    )


# ---------------------------------------------------------------------------
# Fast: the reader refuses rather than defaults, in four distinct ways
# ---------------------------------------------------------------------------
def _mutated_policy_file(tmp_path: Path, **overrides: object) -> Path:
    """Write a copy of the committed policy file with ``comparator.reference_policy`` edited.

    A key set to ``None`` is DELETED, which is how the missing-key clause is exercised
    without hand-writing a whole policy document that would drift from the real one.
    """
    document = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    block = document["comparator"]["reference_policy"]
    for key, value in overrides.items():
        if value is None:
            block.pop(key, None)
        else:
            block[key] = value
    target = tmp_path / "policy.yaml"
    target.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    return target


def test_the_committed_reference_arm_resolves_to_the_twins_own_levels() -> None:
    """The arm is read, and both levels trace to a literal in ``engine.py``.

    ``s`` is the twin's own ``_restock_threshold`` default and ``S`` its opening stock per
    SKU. Asserted as an equality against the committed file rather than against transcribed
    numbers, so a change to the file fails here instead of drifting silently.
    """
    spec = comparator_reference_policy()
    assert isinstance(spec, ReferencePolicySpec)
    assert spec.name == "Par_Level_Reorder"
    assert 0 <= spec.reorder_point < spec.order_up_to
    assert spec.describe() == (f"Par_Level_Reorder(s={spec.reorder_point}, S={spec.order_up_to})")
    # The arm must be constructible from what the reader returns; `Par_Level_Reorder`
    # enforces `0 <= s < S` itself, so this is the two invariants agreeing.
    # Compared as a pair rather than two separate asserts: `assert arm.S == spec.order_up_to`
    # trips ruff's SIM300 "Yoda condition", which reads an upper-case attribute as a
    # constant. Repaired at the expression rather than silenced with a `noqa`.
    arm = Par_Level_Reorder(s=spec.reorder_point, S=spec.order_up_to, seed=0)
    assert (arm.s, arm.S) == (spec.reorder_point, spec.order_up_to)


def test_the_endogenous_restock_stays_disabled_for_every_arm() -> None:
    """R5.36 is satisfied by the committed ``0.0``, unchanged by conflict M's repair.

    Recorded as a test because the temptation when adding an ``(s, S)`` arm is to also turn
    the twin's own restock back on, which would measure the arm STACKED on the twin's -- the
    exact bias ``comparator.restock_threshold`` exists to remove.
    """
    assert comparator_restock_threshold() == 0.0


def test_a_missing_reference_level_is_refused_not_defaulted(tmp_path: Path) -> None:
    """A default reorder point would substitute an unreviewed number into the subject arm."""
    path = _mutated_policy_file(tmp_path, reorder_point_s=None)
    with pytest.raises(PolicyUnavailableError, match="reorder_point_s"):
        comparator_reference_policy(path)


def test_an_unimplemented_policy_name_is_refused(tmp_path: Path) -> None:
    """Resolving an unknown name to *something* would change the measurement's subject."""
    path = _mutated_policy_file(tmp_path, name="Some_Other_Policy")
    with pytest.raises(PolicyUnavailableError, match="does not implement"):
        comparator_reference_policy(path)


def test_a_non_integral_level_is_refused(tmp_path: Path) -> None:
    """Truncating ``50.7`` would measure a policy nobody committed."""
    path = _mutated_policy_file(tmp_path, reorder_point_s=50.7)
    with pytest.raises(PolicyUnavailableError, match="not an integer"):
        comparator_reference_policy(path)


def test_a_transposed_level_pair_is_refused(tmp_path: Path) -> None:
    """``s >= S`` would still run and would still produce a regret number."""
    path = _mutated_policy_file(tmp_path, reorder_point_s=100, order_up_to_S=50)
    with pytest.raises(PolicyUnavailableError, match="0 <= s < S"):
        comparator_reference_policy(path)


# ---------------------------------------------------------------------------
# Fast: the usability predicate, and the no-op arm's contract
# ---------------------------------------------------------------------------
@given(identical=st.booleans(), events=st.integers(min_value=0, max_value=3))
def test_a_replicate_is_usable_only_when_all_three_arms_shared_a_demand_path(
    identical: bool, events: int
) -> None:
    """``usable`` is the conjunction, and neither clause alone is sufficient.

    Constructs the sims without ``start()`` or ``advance()``, so no simulation runs and this
    is not a ``slow`` test: the predicate is pure and does not need a driven twin.
    """
    trace = DemandTrace()
    for index in range(events):
        trace.record(t_min=float(index), sku=f"sku_{index}", units=1.0)

    result = ThreePassResult(
        seed=0,
        trace=trace,
        noop=SupplyChainSimulation(seed=0),
        reference=SupplyChainSimulation(seed=0),
        foresight=SupplyChainSimulation(seed=0),
        demand_identical=identical,
    )
    assert result.usable is (identical and events > 0)


def test_the_no_op_arm_decides_nothing_at_all() -> None:
    """``NoOpRecordingPolicy`` returns an empty action, so ``_apply_reorders`` skips it.

    This is now the MECHANISM of arm A rather than a docstring about it: the class was
    declared by task 10.2 and instantiated nowhere in the tree, which is one reason nothing
    objected when arm A became the wrong comparator.
    """
    action = NoOpRecordingPolicy().decide(
        Observation(
            inventory={"sku_0": 100},
            sim_time=0.0,
            delivery_count=0,
            spoilage_count=0,
            stockout_count=0,
            unit_costs={"sku_0": 1.0},
        )
    )
    assert not action.reorder_quantities
    assert action.price is None
    assert action.routing_assignment is None
    assert not action.disruption_actions


# ---------------------------------------------------------------------------
# Slow: the three clauses that need the real twin
# ---------------------------------------------------------------------------
@pytest.mark.slow
@given(seed=_SEEDS)
def test_the_three_arms_see_an_identical_demand_path(seed: int) -> None:
    """Arms B and C act; ``demand`` and ``sku_choice`` are independent of what they consume.

    Property 52's substream independence is what makes this hold: acting consumes from
    ``pick_pack``/``travel``/``restock`` while demand is drawn from its own substreams. If
    it ever fails, the arms were not compared on the same world and the replicate is
    excluded as unusable rather than averaged in -- so this asserts the invariant the
    exclusion rule depends on, not merely that the rule exists.
    """
    result = run_three_pass(
        seed,
        hours=_PROBE_HOURS,
        restock_threshold=comparator_restock_threshold(),
        reference_policy=_reference_arm(seed),
    )
    assert result.demand_identical, (
        f"seed {seed}: the three arms disagreed on the demand path, so the regret would be "
        "an artefact of the substreams rather than a fact about the world"
    )


@pytest.mark.slow
@given(seed=_SEEDS)
def test_the_no_op_headroom_bounds_the_reference_arms_regret(seed: int) -> None:
    """``headroom >= regret``, which was a TAUTOLOGY until the comparator gained a third arm.

    Under the two-arm form both sides were ``mean_baseline - mean_foresight``, so this could
    not fail and proved nothing (finding 26's defect class). It is a real claim about the
    world now -- doing nothing cannot cost less than running the incumbent ``(s, S)``
    policy -- and it is the claim that makes ``must_be_below_measured_headroom`` a guard
    rather than a formality, because the guard bounds the margin against this headroom.
    """
    result = run_three_pass(
        seed,
        hours=_PROBE_HOURS,
        restock_threshold=comparator_restock_threshold(),
        reference_policy=_reference_arm(seed),
    )
    if not result.usable:
        pytest.skip(f"seed {seed} produced no usable evidence; excluded, never averaged in")

    foresight_cost = _cost(result.foresight)
    regret = _cost(result.reference) - foresight_cost
    headroom = _cost(result.noop) - foresight_cost
    assert headroom >= regret, (
        f"seed {seed}: headroom {headroom!r} does not bound regret {regret!r}. The margin "
        "guard is checked against this headroom, so a headroom that does not bound the "
        "regret makes the guard meaningless"
    )


@pytest.mark.slow
@given(seed=_SEEDS)
def test_the_reference_arm_actually_reorders(seed: int) -> None:
    """The ``(s, S)`` arm reaches its reorder point and acts, so arm B is not a second no-op.

    **Without this clause the repair would be decorative.** A reference arm that never
    decides anything satisfies ``headroom >= regret`` trivially -- as equality -- and the
    comparator would be back to measuring a no-op against the oracle under a new name. This
    asserts non-emptiness of the arm's decisions, which is the same discipline session 3
    applied to ``test_cognition_phase``: a subset assertion over an empty set is vacuous.

    Asserted at the POLICY rather than through the twin's stock, because stock also moves by
    demand and delivery: the question is whether the arm decided, not whether the level rose.
    """
    arm = _reference_arm(seed)
    decisions: list[int] = []

    class _Recording:
        """Wraps the committed arm and counts the non-empty actions it returns."""

        name = arm.name

        def decide(self, obs: Observation) -> object:
            action = arm.decide(obs)
            if action.reorder_quantities:
                decisions.append(len(action.reorder_quantities))
            return action

    run_three_pass(
        seed,
        hours=_PROBE_HOURS,
        restock_threshold=comparator_restock_threshold(),
        reference_policy=_Recording(),  # type: ignore[arg-type]
    )
    assert decisions, (
        f"seed {seed}: the (s, S) reference arm never reordered over "
        f"{_PROBE_HOURS} simulated hour(s). An arm that decides nothing is a second no-op, "
        "and the headroom bound it is compared against would hold by equality rather than "
        "because the arms differ"
    )
