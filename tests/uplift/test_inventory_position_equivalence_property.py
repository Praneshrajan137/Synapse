# Feature: decision-quality-proof, Property 89: (s, S) on inventory position equals (s, S) on
# hand whenever nothing is on order, and never re-orders what is already in the pipeline
"""The (s, S) arm reads inventory position, so a lead time cannot make it order the pipeline twice.

Task 13.1, operator decision Q1=a (session 11). Subject:
``uplift/baselines/par_level_reorder.py::Par_Level_Reorder.decide``.

**Why (finding 67).** Under any lead time, an (s, S) rule on ON-HAND stock still sees the level
at or below ``s`` at the next cadence -- the order is in transit, not on the shelf -- and orders
``S - level`` again, every cadence until the first order lands. Inventory position (on hand plus
on order) is the textbook trigger, and it is identical to the on-hand rule whenever nothing is on
order, which is every step of every run the twin has measured so far: with structure 3 off,
``place_order`` IS ``add_stock`` and ``on_order`` stays empty.

**Domains, stated (R2.10).** Levels are integral, as ``uplift/harness.py::observe`` makes them.
The top-up identity ``level + on_order + order == S`` is asserted EXACTLY over integral
pipelines, where every operation involved is exact; over real-valued pipelines only claims that
survive rounding are asserted -- the sign, the zero/non-zero pattern, and never ordering more than
the on-hand rule would.

**The on-hand rule is restated here from HEAD, not imported**, so clause 1 compares the new code
against the rule it replaced rather than against itself.

Pure arithmetic: no twin, no clock. Budget inherited from ``HYPOTHESIS_PROFILE``; no
``max_examples`` literal. Locus: ``ci.yml::uplift-verify-fast-1``. Property 1's file
(``test_par_level_reorder_properties.py``) is not edited: it builds every ``Observation`` without
``on_order``, which is the empty-pipeline case clause 1 covers.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.policy import comparator_reference_policy
from uplift.baselines.par_level_reorder import Par_Level_Reorder
from uplift.interfaces import Observation

_REORDER_POINT = st.integers(min_value=0, max_value=10_000)
_GAP = st.integers(min_value=1, max_value=10_000)
_LEVEL = st.integers(min_value=0, max_value=25_000)
_SKU = st.text(alphabet="abcdefghij_0123456789", min_size=1, max_size=6)
_INVENTORY = st.dictionaries(keys=_SKU, values=_LEVEL, min_size=1, max_size=6)
_REAL_UNITS = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)


def _observation(inventory: dict[str, int], on_order: dict[str, float]) -> Observation:
    """The snapshot ``observe`` builds, reduced to the two fields this rule reads."""
    return Observation(
        inventory=inventory,
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs=dict.fromkeys(inventory, 1.0),
        on_order=on_order,
    )


def _on_hand_rule(level: int, reorder_point: int, order_up_to: int) -> float:
    """HEAD's rule, restated: order ``S - level`` at or below ``s``, else nothing."""
    return float(order_up_to - level) if level <= reorder_point else 0.0


@st.composite
def _stock_and_pipeline(
    draw: st.DrawFn, reorder_point: int, order_up_to: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Integral stock and pipeline with at least one SKU on EACH side of the reorder point.

    Built per branch rather than filtered, so every example exercises both the top-up and the
    hold, and the clauses below cannot pass on a sample that never reached one of them.
    """
    names = draw(st.lists(_SKU, min_size=2, max_size=6, unique=True))
    inventory: dict[str, int] = {}
    pipeline: dict[str, int] = {}
    for index, sku in enumerate(names):
        at_or_below = index == 0 or (index > 1 and draw(st.booleans()))
        if at_or_below:
            level = draw(st.integers(min_value=0, max_value=reorder_point))
            queued = draw(st.integers(min_value=0, max_value=reorder_point - level))
        else:
            level = draw(st.integers(min_value=0, max_value=order_up_to + 1_000))
            least = max(0, reorder_point + 1 - level)
            queued = draw(st.integers(min_value=least, max_value=least + 10_000))
        inventory[sku] = level
        pipeline[sku] = queued
    return inventory, pipeline


@given(reorder_point=_REORDER_POINT, gap=_GAP, inventory=_INVENTORY, foreign=_INVENTORY)
def test_with_nothing_on_order_the_position_rule_decides_exactly_as_the_on_hand_rule(
    reorder_point: int, gap: int, inventory: dict[str, int], foreign: dict[str, int]
) -> None:
    """Three spellings of "nothing on order" -- empty, zeros, other SKUs only -- one decision."""
    order_up_to = reorder_point + gap
    policy = Par_Level_Reorder(reorder_point, order_up_to, seed=0)
    elsewhere = {sku: float(units) for sku, units in foreign.items() if sku not in inventory}

    for on_order in ({}, dict.fromkeys(inventory, 0.0), elsewhere):
        decided = policy.decide(_observation(inventory, on_order)).reorder_quantities
        assert set(decided) == set(inventory)
        for sku, level in inventory.items():
            assert decided[sku] == _on_hand_rule(level, reorder_point, order_up_to), (
                f"{sku}: with nothing on order the position rule must be HEAD's rule exactly"
            )


@given(reorder_point=_REORDER_POINT, gap=_GAP, data=st.data())
def test_an_integral_pipeline_is_topped_up_to_exactly_s_and_is_never_ordered_twice(
    reorder_point: int, gap: int, data: st.DataObject
) -> None:
    """At or below ``s`` the order tops the position up to ``S``; above it, nothing is ordered."""
    order_up_to = reorder_point + gap
    inventory, pipeline = data.draw(_stock_and_pipeline(reorder_point, order_up_to))
    on_order = {sku: float(units) for sku, units in pipeline.items()}
    policy = Par_Level_Reorder(reorder_point, order_up_to, seed=0)

    decided = policy.decide(_observation(inventory, on_order)).reorder_quantities

    topped_up = [sku for sku in inventory if inventory[sku] + pipeline[sku] <= reorder_point]
    held = [sku for sku in inventory if inventory[sku] + pipeline[sku] > reorder_point]
    assert topped_up and held, "the strategy guarantees both branches; an empty one proves nothing"
    for sku in topped_up:
        level, queued, order = inventory[sku], pipeline[sku], decided[sku]
        assert level + queued + order == order_up_to, (
            f"{sku}: position {level + queued} topped up by {order} does not reach S exactly"
        )
        # The pipeline is not ordered again: the on-hand rule would order exactly `queued` more.
        assert _on_hand_rule(level, reorder_point, order_up_to) - order == queued
    for sku in held:
        assert decided[sku] == 0.0, f"{sku}: position above s must order nothing"


@given(reorder_point=_REORDER_POINT, gap=_GAP, inventory=_INVENTORY, data=st.data())
def test_a_real_valued_pipeline_never_yields_a_negative_order_nor_more_than_the_on_hand_rule(
    reorder_point: int, gap: int, inventory: dict[str, int], data: st.DataObject
) -> None:
    """Only the claims that survive rounding: sign, zero pattern, and the on-hand ceiling."""
    order_up_to = reorder_point + gap
    on_order = {sku: data.draw(_REAL_UNITS) for sku in inventory}
    policy = Par_Level_Reorder(reorder_point, order_up_to, seed=0)

    decided = policy.decide(_observation(inventory, on_order)).reorder_quantities

    for sku, level in inventory.items():
        order = decided[sku]
        assert order >= 0.0
        assert (order > 0.0) == (level + on_order[sku] <= reorder_point)
        assert order <= _on_hand_rule(level, reorder_point, order_up_to)


def test_without_arrivals_only_the_on_hand_rule_orders_the_pipeline_again() -> None:
    """Finding 67 in the committed reference arm's own numbers: one order versus one per cadence.

    Six cadences pass with the first order still in transit -- a lead time longer than six
    decision intervals. The position rule orders once; the on-hand rule re-orders the whole
    pipeline at every cadence, because the shelf it reads has not changed.
    """
    reference = comparator_reference_policy()
    s, order_up_to = reference.reorder_point, reference.order_up_to
    level, cadences = s - 1, 6
    policy = Par_Level_Reorder(s, order_up_to, seed=0)
    # Every expectation below is a closed form over these inputs, never `_on_hand_rule`: an
    # expectation computed by the test's own helper asserts the helper, not the arm.
    gap = float(order_up_to - level)

    in_transit = 0.0
    orders: list[float] = []
    for _ in range(cadences):
        observation = _observation({"sku_0": level}, {"sku_0": in_transit})
        orders.append(policy.decide(observation).reorder_quantities["sku_0"])
        in_transit += orders[-1]

    # Nothing is on order at the first cadence, so the position is the shelf: S - level exactly.
    assert orders[0] == gap, "the first decision must top the position up to S exactly"
    # From then on the first order counts as on order, so the position is S > s: nothing more.
    assert orders[1:] == [0.0] * (cadences - 1), "an order in transit must never be re-ordered"
    assert in_transit == order_up_to - level, "the position rule ordered the gap exactly once"
    # The on-hand reading IS this arm shown no pipeline (clause 1), and it re-orders every time.
    blind = [
        policy.decide(_observation({"sku_0": level}, {})).reorder_quantities["sku_0"]
        for _ in range(cadences)
    ]
    assert blind == [gap] * cadences, (
        "the on-hand rule must re-order the pipeline at every cadence -- the defect it replaces"
    )
