# Feature: decision-quality-proof, Property 92: The structure-aware arm orders up to the
# critical-ratio Poisson quantile of its protection window on inventory position, and sees
# nothing of the future
"""Arm O orders up to its window's critical-ratio Poisson quantile and cannot see the future.

Leaf 16.1 (W2-T10). Subject: ``uplift/oracle_arm.py`` -- ``poisson_quantile``,
``critical_ratio``, ``StructureAwareBaseStock`` and ``build_structure_aware_arm``.

**What would make the subject wrong**, one clause each: (a) a quantile that disagrees with a
direct scan of the Poisson CDF; (b) a target that falls when expected demand or the assumed lead
time rises; (c) an order that is negative, ignores the pipeline, or does not top inventory
position up to the target; (d) identical observations decided differently, or a ``decide`` able
to receive anything but an ``Observation``; (e) a lead time or a window conjured where structure
3 is off; (f) a cost ratio that is not the committed objective's. The critical ratio, the
lead-time estimate and every refusal path have clauses of their own.

**Domain of exactness, stated (R2.10).** Clause (a)'s reference is a scan over 50-digit
decimals, independent of the subject's floats. The subject's log pmf cancels three terms of size
about ``k |log(lam)|`` -- an error of order ``1e-12`` at ``lam <= 400`` -- so equality with the
scan is asserted wherever ``cr`` lies more than ``_BAND`` (``1e-9``) from the CDF at the step
deciding it; inside that band the level is asserted to be a quantile to within ``_BAND``, and a
refusal is admitted only within ``_BAND`` of one. Clause (b) holds ``cr`` at least ``1e-6`` from
one, where no refusal can happen.

World and objective values are READ (``load_world``, ``load_policy``), never restated. Pure
arithmetic: no twin, no clock, no subprocess, no network. Budget inherited from
``HYPOTHESIS_PROFILE``; no ``max_examples`` literal. Locus: ``ci.yml::uplift-verify-fast-2``
(``tests/uplift/test_[pqrstuvwxyz]*.py``, ``ci`` profile). Not slow-marked.
"""

from __future__ import annotations

import dataclasses
import inspect
import math
import random
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import cache
from typing import Final, get_type_hints

import pytest
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.config import TwinConfig
from digital_twin.simulation.policy import load_policy, require
from digital_twin.simulation.world import (
    DAYS_PER_WEEK,
    HOURS_PER_DAY,
    HOURS_PER_WEEK,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    ResolvedWorld,
    WorldSpec,
    load_world,
)
from uplift.interfaces import DecisionPolicy, Observation, PolicyAction
from uplift.oracle_arm import (
    STRUCTURE_AWARE_ARM,
    CostRatio,
    StructureAwareBaseStock,
    build_structure_aware_arm,
    critical_ratio,
    poisson_quantile,
)

#: Digits the reference scan carries -- far beyond double precision, so it is a reference.
_DIGITS: Final[int] = 50
#: Relative distance from a CDF value inside which rounding may legitimately decide the step:
#: about three orders of magnitude above the log pmf's estimated error at lam <= 400.
_BAND: Final[Decimal] = Decimal("1e-9")
#: Relative agreement asserted between a float critical ratio and its value over the rationals.
_RATIO_TOLERANCE: Final[Fraction] = Fraction(1, 10**14)

_LAMBDAS = st.floats(min_value=0.0, max_value=400.0)
_RATIOS = st.floats(min_value=0.0, max_value=1.0, exclude_min=True, exclude_max=True)
#: At least 1e-6 from one, where the float CDF always resolves the quantile.
_RESOLVED_RATIOS = st.floats(min_value=0.0, max_value=1.0 - 1e-6, exclude_min=True)
_HORIZONS = st.sampled_from((1.0, float(HOURS_PER_DAY), float(HOURS_PER_WEEK)))
_REVIEWS = st.floats(min_value=1.0, max_value=float(4 * MINUTES_PER_HOUR))
_TIMES = st.floats(min_value=0.0, max_value=float(DAYS_PER_WEEK * MINUTES_PER_DAY))
_WEEKDAYS = st.integers(min_value=0, max_value=DAYS_PER_WEEK - 1)
_LEADS = st.floats(min_value=0.0, max_value=float(MINUTES_PER_DAY))
#: Realised-to-declared lead-time ratios a landed order might show.
_FACTORS = st.floats(min_value=0.5, max_value=2.0)
_SEEDS = st.integers(min_value=0, max_value=2**32 - 1)
_UNITS = st.integers(min_value=0, max_value=500)


# ---------------------------------------------------------------------------
# The committed world and objective, each read once
# ---------------------------------------------------------------------------


@cache
def _world() -> WorldSpec:
    return load_world()


@cache
def _resolved(cell: str) -> ResolvedWorld:
    return _world().resolve(cell)


@cache
def _policy_document() -> dict[str, object]:
    return load_policy()


@cache
def _cell_names(structure_3: bool | None) -> tuple[str | None, ...]:
    """Committed cells by structure 3 (``None``: all), plus HEAD's world unless it must be on.

    Read from ``world.cells``, never listed here, and refused when empty: a property drawn from
    an empty grid would pass by never running.
    """
    cells = _world().cells
    committed = sorted(cells)
    if structure_3 is None:
        names: tuple[str | None, ...] = (None, *committed)
    elif structure_3:
        names = tuple(name for name in committed if cells[name].structure_3)
    else:
        names = (None, *(name for name in committed if not cells[name].structure_3))
    assert names, f"world.cells declares no cell with structure_3={structure_3}"
    return names


@cache
def _committed_rate() -> float:
    """The engine's demand rate per minute, read where the arm reads it."""
    return TwinConfig().order_arrival_rate


@cache
def _committed_cost(hours: float) -> CostRatio:
    """The cost ratio ``build_structure_aware_arm`` derives for a horizon, read once per horizon.

    Clause (f) proves it depends on the horizon alone, so the world, review period, SKU count and
    seed passed here change nothing.
    """
    return build_structure_aware_arm(
        None, seed=0, hours=hours, review_min=float(MINUTES_PER_HOUR), n_skus=1
    ).cost


def _arm(
    world: ResolvedWorld | None, *, hours: float, review_min: float, n_skus: int, seed: int
) -> StructureAwareBaseStock:
    """Arm O as ``build_structure_aware_arm`` builds it (clause (f) proves the identity),
    without parsing the policy file once per example."""
    return StructureAwareBaseStock(
        world=world,
        cost=_committed_cost(hours),
        review_min=review_min,
        rate_per_sku_per_min=_committed_rate() / n_skus,
        seed=seed,
    )


def _scaled(mean: float, factors: list[float]) -> tuple[float, ...]:
    """Realised lead times at each ``factor`` times a declared mean."""
    return tuple(mean * factor for factor in factors)


@dataclasses.dataclass(frozen=True)
class _Case:
    """A world the engine could run, arm O built for it, and a clock -- what ``observe`` sees."""

    world: ResolvedWorld | None
    arm: StructureAwareBaseStock
    skus: tuple[str, ...]
    sim_time: float
    start_weekday: int | None
    sku_supplier: dict[str, str]
    history: dict[str, tuple[float, ...]]

    def observe(self, *, inventory: dict[str, int], on_order: dict[str, float]) -> Observation:
        """The snapshot ``uplift/harness.py::observe`` builds, at this case's world and clock."""
        return Observation(
            inventory=inventory,
            sim_time=self.sim_time,
            delivery_count=0,
            spoilage_count=0,
            stockout_count=0,
            unit_costs=dict.fromkeys(inventory, 1.0),
            on_order=on_order,
            supplier_lead_time_history=self.history,
            sku_supplier=self.sku_supplier,
            start_weekday=self.start_weekday,
        )


@st.composite
def _cases(draw: st.DrawFn, structure_3: bool | None) -> _Case:
    """A case drawn per :func:`_cell_names`, reported as the engine would report it.

    With structure 3 on, the SKUs and roster are the committed ``sku_supplier`` and every
    declared supplier gets a landed history (possibly empty); with it off both are empty, as the
    engine reports them. ``start_weekday`` is drawn only where structure 1 is on.
    """
    cell = draw(st.sampled_from(_cell_names(structure_3)))
    world = None if cell is None else _resolved(cell)
    supply = None if world is None else world.supply
    history: dict[str, tuple[float, ...]] = {}
    if supply is None:
        skus = tuple(f"sku_{index}" for index in range(draw(st.integers(1, 10))))
        roster: dict[str, str] = {}
    else:
        skus = tuple(sorted(supply.sku_supplier))
        roster = dict(supply.sku_supplier)
        for supplier, spec in sorted(supply.suppliers.items()):
            history[supplier] = _scaled(
                spec.mean_lead_time_min, draw(st.lists(_FACTORS, max_size=4))
            )
    shaped = world is not None and world.demand is not None
    return _Case(
        world=world,
        arm=_arm(
            world,
            hours=draw(_HORIZONS),
            review_min=draw(_REVIEWS),
            n_skus=len(skus),
            seed=draw(_SEEDS),
        ),
        skus=skus,
        sim_time=draw(_TIMES),
        start_weekday=draw(_WEEKDAYS) if shaped else None,
        sku_supplier=roster,
        history=history,
    )


# ---------------------------------------------------------------------------
# (a) The quantile is the one a direct scan of the CDF finds
# ---------------------------------------------------------------------------


def _exact_cdf(lam: float, ratio: Decimal, through: int) -> list[Decimal]:
    """``P(N <= k)`` over 50-digit decimals for ``k = 0, 1, ...`` until it reaches ``ratio`` and
    ``k >= through``: the brute-force scan, ``P(N = k) = P(N = k - 1) lam / k`` summed directly.

    ``Decimal(lam)`` is the binary float's exact value, so the scan and the subject see one lam.
    """
    with localcontext() as context:
        context.prec = _DIGITS
        rate = Decimal(lam)
        pmf = (-rate).exp()
        cdf = [pmf]
        while cdf[-1] < ratio or len(cdf) <= through:
            pmf = pmf * rate / len(cdf)
            cdf.append(cdf[-1] + pmf)
    return cdf


def _assert_is_the_scans_quantile(lam: float, cr: float, got: int) -> None:
    """``got`` is the scan's quantile: exactly, unless ``cr`` is within ``_BAND`` of the CDF."""
    # Checked before scanning, so a runaway level fails rather than hanging the scan: past
    # 40 standard deviations plus 100 the Poisson tail is below 1e-250, which no ratio under one
    # can need.
    assert 0 <= got <= lam + 40.0 * math.sqrt(lam) + 100.0, f"lam={lam!r} cr={cr!r}: got {got}"
    ratio = Decimal(cr)
    cdf = _exact_cdf(lam, ratio, got)
    expected = next(k for k, value in enumerate(cdf) if value >= ratio)
    with localcontext() as context:
        context.prec = _DIGITS
        low, high = ratio * (1 - _BAND), ratio * (1 + _BAND)
    assert cdf[got] >= low, f"lam={lam!r} cr={cr!r}: P(N <= {got}) is below cr; {got} is too low"
    assert got == 0 or cdf[got - 1] < high, (
        f"lam={lam!r} cr={cr!r}: P(N <= {got - 1}) already reaches cr; {got} is too high"
    )
    deciding = [cdf[k] for k in (expected - 1, expected) if k >= 0]
    if not any(low <= value <= high for value in deciding):
        assert got == expected, f"lam={lam!r} cr={cr!r}: got {got}, the scan finds {expected}"


@given(lam=_LAMBDAS, cr=_RATIOS)
def test_the_quantile_is_the_level_a_fifty_digit_scan_of_the_poisson_cdf_finds(
    lam: float, cr: float
) -> None:
    """Clause (a): the log-space scan is the direct scan, in the domain the module states."""
    try:
        got = poisson_quantile(lam, cr)
    except ValueError:
        assert 1 - Decimal(cr) <= _BAND, f"refused cr={cr!r} at lam={lam!r}, which is resolvable"
        return
    _assert_is_the_scans_quantile(lam, cr, got)


@pytest.mark.parametrize("cr", [0.5, 0.95, 0.99])
def test_an_expected_demand_of_two_thousand_neither_underflows_nor_overflows(cr: float) -> None:
    """Clause (a) at the scale the module promises, where ``exp(-2000)`` is zero in floats.

    A linear-space scan would start from ``P(N = 0) = 0.0``, and every later term, a multiple of
    it, would be zero too; in log space that term is ``-2000`` and the scan reaches the decimal
    scan's level.
    """
    lam = 2000.0
    assert math.exp(-lam) == 0.0, "the premise: the first term underflows in linear space"
    _assert_is_the_scans_quantile(lam, cr, poisson_quantile(lam, cr))


# ---------------------------------------------------------------------------
# (b) The target never falls as demand or the assumed lead time rises
# ---------------------------------------------------------------------------


@given(first=_LAMBDAS, second=_LAMBDAS, cr=_RESOLVED_RATIOS)
def test_the_target_never_falls_as_expected_demand_rises(
    first: float, second: float, cr: float
) -> None:
    """Clause (b), in ``lam``: Poisson demand is stochastically increasing in its mean."""
    low, high = sorted((first, second))
    assert poisson_quantile(low, cr) <= poisson_quantile(high, cr)


@given(case=_cases(None), first=_LEADS, second=_LEADS)
def test_the_target_never_falls_as_the_assumed_lead_time_rises(
    case: _Case, first: float, second: float
) -> None:
    """Clause (b), in ``L_hat``: a longer lead time widens the window and raises the ratio."""
    shorter, longer = sorted((first, second))
    near, far = (
        case.arm.target(
            sku=case.skus[0],
            t_min=case.sim_time,
            lead_time_min=lead,
            start_weekday=case.start_weekday,
            position=0.0,
        )
        for lead in (shorter, longer)
    )
    assert near.window_min <= far.window_min
    assert near.expected_demand <= far.expected_demand
    assert near.order_up_to <= far.order_up_to, (
        f"L_hat {shorter} -> {longer} lowered the target {near.order_up_to} -> {far.order_up_to}"
    )


@given(hours=_HORIZONS, review=_REVIEWS, first=_LEADS, second=_LEADS)
def test_the_critical_ratio_is_huh_et_als_and_rises_with_the_lead_time(
    hours: float, review: float, first: float, second: float
) -> None:
    """``(b + tau h) / (b + (tau + 1) h)``, held against its own value over the rationals.

    Over the reals it lies strictly inside ``(0, 1)`` and strictly rises with the lead time; in
    floats it agrees with that value to within ``1e-14`` relative, where any other formula that
    weights the lead time differently would miss by far more once ``tau > 0``.
    """
    cost = _committed_cost(hours)
    shortage = Fraction(cost.shortage_per_unit)
    holding = Fraction(cost.holding_per_unit_min) * Fraction(review)

    def exact(lead: float) -> Fraction:
        tau = Fraction(lead) / Fraction(review)
        return (shortage + tau * holding) / (shortage + (tau + 1) * holding)

    shorter, longer = sorted((first, second))
    for lead in (shorter, longer):
        ratio = critical_ratio(cost, lead_time_min=lead, review_min=review)
        assert 0 < exact(lead) < 1
        assert abs(Fraction(ratio) - exact(lead)) <= exact(lead) * _RATIO_TOLERANCE, (
            f"lead {lead}: {ratio} is not (b + tau h) / (b + (tau + 1) h)"
        )
    if shorter < longer:
        assert exact(shorter) < exact(longer)


# ---------------------------------------------------------------------------
# (c) The order tops inventory position up to the target
# ---------------------------------------------------------------------------


@given(case=_cases(None), data=st.data())
def test_the_order_tops_inventory_position_up_to_the_target_and_never_orders_the_pipeline_twice(
    case: _Case, data: st.DataObject
) -> None:
    """Clause (c): ``position + order == max(position, S_t)``, exactly, over integral stock.

    The targets are read first from a bare shelf, and the identity is then asserted against THOSE
    targets, so a target that moved with the stock would break it. One SKU is drawn strictly below
    its target, so every example exercises the top-up rather than only some.
    """
    bare = case.observe(inventory=dict.fromkeys(case.skus, 0), on_order={})
    levels = {target.sku: target.order_up_to for target in case.arm.targets(bare)}
    short = max(sorted(levels), key=levels.__getitem__)
    assert levels[short] >= 1, (
        "every drawn world demands more than P(N = 0) allows at the committed ratio; a zero "
        "target everywhere would leave nothing to top up and prove nothing"
    )
    inventory: dict[str, int] = {}
    on_order: dict[str, float] = {}
    for sku in case.skus:
        ceiling = levels[sku] - 1 if sku == short else 2 * levels[sku] + 5
        drawn = data.draw(st.integers(min_value=0, max_value=ceiling))
        queued = data.draw(st.integers(min_value=0, max_value=drawn))
        inventory[sku] = drawn - queued
        on_order[sku] = float(queued)

    orders = case.arm.decide(case.observe(inventory=inventory, on_order=on_order))

    assert set(orders.reorder_quantities) == set(case.skus)
    for sku in case.skus:
        position = inventory[sku] + on_order[sku]
        order = orders.reorder_quantities[sku]
        assert order >= 0.0, f"{sku}: a negative order"
        assert position + order == max(position, float(levels[sku])), (
            f"{sku}: position {position} plus order {order} is not max(position, {levels[sku]})"
        )
    assert orders.reorder_quantities[short] > 0.0, f"{short} sits below its target, unordered"

    covering = {
        sku: float(max(0, levels[sku] - inventory[sku]) + data.draw(_UNITS)) for sku in case.skus
    }
    again = case.arm.decide(case.observe(inventory=inventory, on_order=covering))
    assert set(again.reorder_quantities.values()) == {0.0}, (
        "a pipeline that already covers the target was ordered again"
    )


# ---------------------------------------------------------------------------
# (d) Determinism, and the future is out of reach by construction
# ---------------------------------------------------------------------------


@given(case=_cases(None), other_seed=_SEEDS, data=st.data())
def test_identical_observations_get_identical_actions_whatever_the_seed(
    case: _Case, other_seed: int, data: st.DataObject
) -> None:
    """Clause (d): no randomness and no hidden state -- the seed is held, never drawn from."""
    inventory = {sku: data.draw(_UNITS) for sku in case.skus}
    on_order = {sku: float(data.draw(_UNITS)) for sku in case.skus}
    first = case.observe(inventory=inventory, on_order=on_order)
    again = case.observe(inventory=dict(inventory), on_order=dict(on_order))
    reseeded = StructureAwareBaseStock(
        world=case.world,
        cost=case.arm.cost,
        review_min=case.arm.review_min,
        rate_per_sku_per_min=case.arm.rate_per_sku_per_min,
        seed=other_seed,
    )

    decided = case.arm.decide(first)

    assert case.arm.decide(again) == decided
    assert reseeded.decide(again) == decided
    assert list(decided.reorder_quantities) == sorted(case.skus)


def test_decide_takes_only_an_observation_and_the_arm_holds_no_engine() -> None:
    """Clause (d): the future is out of reach by construction, not by convention.

    ``decide`` accepts exactly one ``Observation``, so it cannot be handed the engine, its
    lead-time path or the demand trace; the arm's own state is the declared world, the cost ratio,
    three scalars and an undrawn generator, none of which can carry a realisation. The signatures
    pinned here are the fixed interface the comparator wiring codes against.
    """
    assert get_type_hints(StructureAwareBaseStock.decide) == {
        "obs": Observation,
        "return": PolicyAction,
    }
    assert list(inspect.signature(StructureAwareBaseStock.decide).parameters) == ["self", "obs"]
    init = inspect.signature(StructureAwareBaseStock.__init__).parameters
    assert list(init) == ["self", "world", "cost", "review_min", "rate_per_sku_per_min", "seed"]
    assert {init[name].kind for name in list(init)[1:]} == {inspect.Parameter.KEYWORD_ONLY}
    built = inspect.signature(build_structure_aware_arm).parameters
    assert list(built) == ["world", "seed", "hours", "review_min", "n_skus"]
    assert built["world"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert {built[name].kind for name in list(built)[1:]} == {inspect.Parameter.KEYWORD_ONLY}

    world = _resolved(_world().primary_cell)
    assert world.supply is not None
    arm = _arm(
        world,
        hours=float(HOURS_PER_DAY),
        review_min=float(MINUTES_PER_HOUR),
        n_skus=len(world.supply.sku_supplier),
        seed=0,
    )
    assert isinstance(arm, DecisionPolicy)
    assert arm.name == STRUCTURE_AWARE_ARM == "structure_aware"
    held = {type(value) for value in vars(arm).values()}
    assert held <= {ResolvedWorld, CostRatio, float, int, random.Random}, (
        f"the arm holds {sorted(kind.__name__ for kind in held)}; only declared structure, "
        "committed numbers and an undrawn generator are admissible"
    )


# ---------------------------------------------------------------------------
# (e) No lead time and no window are conjured where structure 3 is off
# ---------------------------------------------------------------------------


@given(case=_cases(False), landed=st.lists(_LEADS, min_size=1, max_size=4))
def test_with_structure_3_off_the_lead_time_is_zero_and_the_window_one_review_period(
    case: _Case, landed: list[float]
) -> None:
    """Clause (e), over HEAD's world and every committed cell with structure 3 off.

    The observation is handed a supplier roster and a landed history anyway -- what a structure-3
    engine would report, ending in a zero lead time the arm refuses whenever it reads one -- and
    an arm whose world has structure 3 off must read neither.
    """
    obs = dataclasses.replace(
        case.observe(inventory=dict.fromkeys(case.skus, 0), on_order={}),
        sku_supplier=dict.fromkeys(case.skus, "supplier_elsewhere"),
        supplier_lead_time_history={"supplier_elsewhere": (*landed, 0.0)},
    )
    arm, review = case.arm, case.arm.review_min
    shortage, holding = arm.cost.shortage_per_unit, arm.cost.holding_per_unit_min * review
    demand = None if case.world is None else case.world.demand

    targets = arm.targets(obs)

    assert [target.sku for target in targets] == sorted(case.skus)
    for target in targets:
        assert arm.lead_time_estimate(obs, target.sku) == 0.0
        assert target.lead_time_min == 0.0
        assert target.window_min == review, "the window must be exactly one review period"
        assert target.critical_ratio == shortage / (shortage + holding), "tau must be zero"
        if demand is None:
            assert target.expected_demand == arm.rate_per_sku_per_min * review
        else:
            assert case.start_weekday is not None
            assert target.expected_demand == demand.expected_units(
                t0_min=case.sim_time,
                t1_min=case.sim_time + review,
                start_weekday=case.start_weekday,
                rate_per_min=arm.rate_per_sku_per_min,
            )


# ---------------------------------------------------------------------------
# The lead-time estimate reads declared values and LANDED history only
# ---------------------------------------------------------------------------


@given(
    case=_cases(True),
    factor=_FACTORS,
    landed=st.integers(min_value=0, max_value=4),
    data=st.data(),
)
def test_the_lead_time_estimate_is_the_declared_prior_scaled_by_landed_history_alone(
    case: _Case, factor: float, landed: int, data: st.DataObject
) -> None:
    """``L_hat`` = declared mean x coupling at ``I(t)`` x ``f_hat``, floored at the minimum.

    Equal to within ``1e-12`` relative, because ``exp(mean(log(ratio)))`` round-trips a constant
    ratio to a few ulps. Then the half that keeps the future out: an order in transit and the
    demand seen so far are not landed history, so neither moves the estimate.
    """
    world = case.world
    assert world is not None and world.supply is not None
    supply = world.supply
    sku = data.draw(st.sampled_from(case.skus))
    supplier = supply.sku_supplier[sku]
    mean = supply.suppliers[supplier].mean_lead_time_min
    obs = dataclasses.replace(
        case.observe(inventory=dict.fromkeys(case.skus, 0), on_order={}),
        supplier_lead_time_history={**case.history, supplier: (mean * factor,) * landed},
    )
    if world.demand is None:
        intensity = 1.0
    else:
        assert case.start_weekday is not None
        intensity = world.demand.intensity(case.sim_time, case.start_weekday)
    coupling = max(supply.coupling_floor, 1.0 + supply.demand_coupling * (intensity - 1.0))
    expected = max(supply.min_lead_time_min, mean * coupling * (factor if landed else 1.0))

    estimate = case.arm.lead_time_estimate(obs, sku)

    assert estimate == pytest.approx(expected, rel=1e-12)
    used = {target.sku: target.lead_time_min for target in case.arm.targets(obs)}
    assert used[sku] == estimate, "the target must protect over the estimate the rule states"
    in_transit = dataclasses.replace(obs, on_order={sku: 1e4}, demand_to_date={sku: 10**6})
    assert case.arm.lead_time_estimate(in_transit, sku) == estimate


# ---------------------------------------------------------------------------
# (f) The cost ratio is the committed objective's
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hours", [1.0, 2.5, float(HOURS_PER_DAY), float(HOURS_PER_WEEK)])
@pytest.mark.parametrize("review_min", [1.0, 15.0, float(MINUTES_PER_HOUR)])
@pytest.mark.parametrize("n_skus", [1, 10])
def test_the_cost_ratio_is_the_committed_objectives_and_depends_on_the_horizon_alone(
    hours: float, review_min: float, n_skus: int
) -> None:
    """Clause (f), computed from the policy file itself rather than through ``load_objective``.

    ``b / h = (w_unmet / (rate H)) / (w_on_hand R / (normaliser H))``: the horizon cancels, so
    the shortage-to-holding ratio is the weights' ratio times ``normaliser / (rate R)``.
    """
    document = _policy_document()
    w_unmet = float(require(document, "regret_objective.weights.unmet_service"))
    w_on_hand = float(require(document, "regret_objective.weights.on_hand"))
    normaliser = float(require(document, "regret_objective.normalisers.on_hand_units"))
    rate = TwinConfig().order_arrival_rate
    minutes = hours * MINUTES_PER_HOUR
    shortage = w_unmet / (rate * minutes)
    holding = w_on_hand * review_min / (normaliser * minutes)
    world = _resolved(_world().primary_cell)

    arm = build_structure_aware_arm(
        world, seed=7, hours=hours, review_min=review_min, n_skus=n_skus
    )
    other = build_structure_aware_arm(
        None, seed=11, hours=hours, review_min=2.0 * review_min, n_skus=n_skus + 3
    )

    assert arm.cost.shortage_per_unit == pytest.approx(shortage, rel=1e-12)
    assert arm.cost.holding_per_unit_min * review_min == pytest.approx(holding, rel=1e-12)
    assert arm.cost.shortage_per_unit / (arm.cost.holding_per_unit_min * review_min) == (
        pytest.approx((w_unmet / w_on_hand) * normaliser / (rate * review_min), rel=1e-12)
    )
    assert other.cost == arm.cost, "the cost moved with the world, review, SKU count or seed"
    assert arm.rate_per_sku_per_min == rate / n_skus
    assert (arm.world, arm.review_min, arm.seed) == (world, review_min, 7)
    helper = _arm(world, hours=hours, review_min=review_min, n_skus=n_skus, seed=7)
    assert (helper.cost, helper.rate_per_sku_per_min) == (arm.cost, arm.rate_per_sku_per_min)


# ---------------------------------------------------------------------------
# Refusals, each proven by construction and each naming what it refuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lam", "cr", "refused"),
    [
        (10.0, 0.0, "critical ratio"),
        (10.0, 1.0, "critical ratio"),
        (10.0, -0.25, "critical ratio"),
        (10.0, math.nan, "critical ratio"),
        (-1.0, 0.5, "expected demand"),
        (math.nan, 0.5, "expected demand"),
        (math.inf, 0.5, "expected demand"),
    ],
)
def test_the_quantile_refuses_a_ratio_outside_the_open_interval_and_an_impossible_demand(
    lam: float, cr: float, refused: str
) -> None:
    """``cr = 1`` would order without bound and ``cr = 0`` order nothing; neither is a quantile."""
    with pytest.raises(ValueError, match=refused):
        poisson_quantile(lam, cr)


def test_the_arm_refuses_what_it_cannot_compute_instead_of_assuming_it() -> None:
    """Every other refusal path, by construction (I-7: no weekday, supplier or cost is assumed)."""
    cost = _committed_cost(float(HOURS_PER_DAY))
    with pytest.raises(ValueError, match="shortage_per_unit"):
        CostRatio(shortage_per_unit=0.0, holding_per_unit_min=cost.holding_per_unit_min)
    with pytest.raises(ValueError, match="holding_per_unit_min"):
        CostRatio(shortage_per_unit=cost.shortage_per_unit, holding_per_unit_min=math.inf)
    for review in (0.0, -1.0, math.nan):
        with pytest.raises(ValueError, match="review_min"):
            StructureAwareBaseStock(
                world=None, cost=cost, review_min=review, rate_per_sku_per_min=1.0, seed=0
            )
    with pytest.raises(ValueError, match="rate_per_sku_per_min"):
        StructureAwareBaseStock(
            world=None, cost=cost, review_min=1.0, rate_per_sku_per_min=0.0, seed=0
        )
    with pytest.raises(ValueError, match="hours"):
        build_structure_aware_arm(None, seed=0, hours=0.0, review_min=1.0, n_skus=1)
    with pytest.raises(ValueError, match="n_skus"):
        build_structure_aware_arm(None, seed=0, hours=1.0, review_min=1.0, n_skus=0)

    # The primary cell runs both structures, by the world reader's own rule.
    world = _resolved(_world().primary_cell)
    assert world.supply is not None and world.demand is not None
    roster = dict(world.supply.sku_supplier)
    arm = _arm(
        world,
        hours=float(HOURS_PER_DAY),
        review_min=float(MINUTES_PER_HOUR),
        n_skus=len(roster),
        seed=0,
    )
    admissible = Observation(
        inventory=dict.fromkeys(roster, 0),
        sim_time=0.0,
        delivery_count=0,
        spoilage_count=0,
        stockout_count=0,
        unit_costs=dict.fromkeys(roster, 1.0),
        sku_supplier=roster,
        start_weekday=0,
    )
    assert set(arm.decide(admissible).reorder_quantities) == set(roster)
    first = sorted(roster)[0]
    refused = {
        "start_weekday": dataclasses.replace(admissible, start_weekday=None),
        "no supplier": dataclasses.replace(admissible, sku_supplier={}),
        "does not declare": dataclasses.replace(
            admissible, sku_supplier=dict.fromkeys(roster, "undeclared_supplier")
        ),
        "realised lead time": dataclasses.replace(
            admissible, supplier_lead_time_history={roster[first]: (0.0,)}
        ),
        "simulated time": dataclasses.replace(admissible, sim_time=-1.0),
        "inventory position": dataclasses.replace(admissible, on_order={first: math.nan}),
    }
    for reason, observation in refused.items():
        with pytest.raises(ValueError, match=reason):
            arm.decide(observation)
