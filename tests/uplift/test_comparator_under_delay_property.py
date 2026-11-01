# Feature: decision-quality-proof, Property 96: Under a replenishment delay the hindsight arm
# covers every fulfilment after its first arrival, the split is exact, and room-to-win is read
# from the two ceiling intervals alone
"""Under a delay arm D is still the floor, the split is exact, and B-prime reads two intervals.

Feature: decision-quality-proof, task 13.7b and the W2b review (R1, R2, R5). Subjects:
``uplift/foresight.py::HindsightOraclePolicy`` (its delayed rule); ``uplift/regret.py::
room_to_win``, ``::room_to_win_out_of_sample``, ``::in_sample_recheck``, ``::split_refusal``
and ``::decomposition_refusal``; and ``uplift/regret.py::_measure`` run in a declared world cell.

**What each clause would catch.** (a) a delayed arm D whose cumulative supply is not exactly
``max(I, G(min(a(t + w), H)))`` -- a held cut-off rebuilt from ``t - w`` rather than read at
``t``, a first decision that credits an order nobody placed, a cap on the wrong side; (b) any
byte of drift in the instantaneous rule every landed run was measured with; (c) a straddling
ceiling read as room to win, a room reading the in-sample recheck does not also support, or a
reading that consults anything but the two ceiling intervals; (d) a split admitted while
hindsight fails to bound the structure-aware arm, or a two-term split admitted over a search
that refused (R2); (e) an arm leaving less demand unmet than arm D at some seed under a real
delay; (f) an artifact whose split terms or in-sample ceiling are not the differences of the
means it reports, whose recheck did not reproduce arm E or keep its candidates' least mean, or
whose readings are not the rule recomputed from its own intervals and margin (R5); (g) a world
cell with both structures off that measures the judged arms differently from no cell at all;
(h) a recheck that skips a candidate or a seed, prices one twice, or breaks a tie away from the
selection (R1).

**Where exactness holds (R2.10).** Supply is integral -- ``DemandTrace.record`` defaults
``units=1.0`` -- so (a) and (b) compare over ``fractions.Fraction`` and over exact floats with
no tolerance. (f) compares single IEEE subtractions of the reported means, which are
deterministic; the split's float residual is reported by ``_measure``, not toleranced here. (h)
prices with integer-valued costs, so its means and its ties are exact.

**I-0.** (a)-(d), (h) and the pins construct no engine. (e)-(g) drive the SimPy twin and are
``@pytest.mark.slow``, selected by ``ci.yml::uplift-verify``'s slow step over ``tests/uplift``.
They run 24 simulated hours, the committed CI horizon. At 6 h -- inferred from the committed rates,
not measured -- the opening stock covers the run, no arm stocks out (so (e) would hold vacuously)
and arm D coincides with the no-op arm, leaving the judged path's margin guard a zero headroom.
Arm E's search is shrunk through ``_measure``'s two declared test seams -- three candidates per
group, one tuning seed -- and the artifact records that it was; the in-sample recheck is not
seamed, and prices its few candidates at both measurement seeds. Budget inherited from the root
``conftest.py`` profile; **no ``max_examples`` literal appears in this file**.
"""

from __future__ import annotations

import inspect
import logging
import math
import statistics
from collections import Counter
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Final

import pytest
import structlog
from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.engine import DemandTrace
from digital_twin.simulation.policy import (
    comparator_reference_policy,
    comparator_restock_threshold,
)
from digital_twin.simulation.world import load_world
from uplift import regret as regret_module
from uplift.baselines.par_level_reorder import Par_Level_Reorder
from uplift.foresight import HindsightOraclePolicy, run_three_pass, stocked_skus
from uplift.oracle_arm import STRUCTURE_AWARE_ARM
from uplift.regret import (
    ARM_LABELS,
    decomposition_refusal,
    in_sample_recheck,
    room_to_win,
    room_to_win_out_of_sample,
    split_refusal,
)
from uplift.tuned_static import TUNED_STATIC_ARM, GroupLevels, GroupParLevelReorder, sku_groups
from uplift.tuning import BOUNDARY_REFUSAL, NON_CONVERGENCE_REFUSAL, GridPoint, load_tuning_spec

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

    from digital_twin.simulation.world import ResolvedWorld

_SKU_NAMES: Final[tuple[str, ...]] = ("sku_0", "sku_1", "sku_2")
#: The split's four arms, as `_measure` names them to `split_refusal`.
_SPLIT_ARMS: Final[tuple[str, ...]] = ("reference", "hindsight", "tuned_static", "structure_aware")

#: Integral units, the domain the twin records. Bounded by construction, so nothing is filtered.
_EVENTS = st.lists(
    st.tuples(
        st.integers(min_value=0, max_value=600),
        st.sampled_from(_SKU_NAMES),
        st.integers(min_value=1, max_value=4),
    ),
    min_size=0,
    max_size=12,
)
#: Small, so generated demand outgrows the opening stock and the arm has to order.
_OPENING = st.integers(min_value=0, max_value=20)
_WINDOWS = st.integers(min_value=30, max_value=180)
_HORIZONS = st.integers(min_value=60, max_value=900)
#: Per-SKU lead times in whole minutes, one per hour of placement, cycled. Zero is allowed: an
#: order that lands at once is a legitimate point of the delayed rule's domain.
_LEADS = st.fixed_dictionaries(
    {
        sku: st.lists(st.integers(min_value=0, max_value=300), min_size=1, max_size=6)
        for sku in _SKU_NAMES
    }
)
#: One minute past the last event a trace can carry, as Property 80 uses it.
_NO_DELAY_HORIZON_MIN: Final[int] = 601

_BOUNDS = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_WIDTHS = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
_COUNTS = st.integers(min_value=1, max_value=500)
_SHORTFALLS = st.floats(min_value=1e-12, max_value=1e6, allow_nan=False, allow_infinity=False)
_NON_NEGATIVE = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
_SEARCH_REFUSALS = st.sampled_from((BOUNDARY_REFUSAL, NON_CONVERGENCE_REFUSAL))

#: The recheck's domain (h): two groups and small integral levels, so generated lists repeat a
#: member (deduplication is exercised) and integer-valued costs tie exactly (the tie-break is).
_POINTS = st.builds(
    lambda s, band: GridPoint(s=s, S=s + band),
    st.integers(min_value=0, max_value=4),
    st.integers(min_value=1, max_value=3),
)
_LEVEL_VECTORS = st.builds(
    lambda first, second: GroupLevels(levels={"sup_a": first, "sup_b": second}),
    _POINTS,
    _POINTS,
)
_RECHECK_SEEDS = st.lists(
    st.integers(min_value=0, max_value=40), min_size=1, max_size=5, unique=True
)
_WEIGHT = st.integers(min_value=0, max_value=3)

#: The slow clauses' replicate seeds and horizon. Two seeds, as the contract sizes them.
_SLOW_SEEDS: Final[tuple[int, ...]] = (0, 1)
_DAY_HOURS: Final[float] = 24.0
#: Arm E's search inputs for the slow clauses -- test inputs, not committed values.
_SMALL_CANDIDATES: Final[tuple[int, ...]] = (40, 80, 120)


def _trace(events: Sequence[tuple[int, str, int]]) -> DemandTrace:
    """A hand-built demand path, recorded at GENERATION time as the engine records it."""
    trace = DemandTrace()
    for t_min, sku, units in events:
        trace.record(t_min=float(t_min), sku=sku, units=float(units))
    return trace


def _generated_before(events: Sequence[tuple[int, str, int]], sku: str, end: float) -> Fraction:
    """``G(end)`` for one SKU, recomputed by brute force from the raw events."""
    return sum((Fraction(units) for t, s, units in events if s == sku and t < end), Fraction(0))


def _decisions(window: int, horizon: int) -> list[float]:
    """Every decision instant before ``horizon``, spaced by ``window`` from minute 0."""
    return [float(minute) for minute in range(0, horizon, window)]


def _arrival(leads_by_sku: Mapping[str, Sequence[int]]) -> Callable[[str, float], float]:
    """A synthetic arrival function, NON-DECREASING in placement time by construction.

    An order placed in whole hour ``h`` takes ``leads[h % len(leads)]`` minutes, and the running
    maximum over finished hours -- the construction ``lead_time.py`` uses -- means a later order
    never lands before an earlier one.
    """

    def arrival(sku: str, t_min: float) -> float:
        leads = leads_by_sku[sku]
        hour = int(t_min // 60)
        current = t_min + leads[hour % len(leads)]
        finished = [(done + 1) * 60.0 + leads[done % len(leads)] for done in range(hour)]
        return max([current, *finished])

    return arrival


def _lands_at_once(_sku: str, t_min: float) -> float:
    """The arrival function of a world with no replenishment delay."""
    return t_min


def _reason(
    *,
    search_refusal: str | None,
    usable: Mapping[str, int],
    decomposition: str | None,
    residual_information_value: float,
) -> str:
    """``split_refusal``'s reason, asserted to exist."""
    reason = split_refusal(
        search_refusal=search_refusal,
        usable=usable,
        decomposition=decomposition,
        residual_information_value=residual_information_value,
    )
    assert reason is not None, "this split should have been refused"
    return reason


def _binding_rule(
    out_of_sample: tuple[float, float] | None,
    in_sample: tuple[float, float] | None,
    *,
    margin: float | None,
    admissible: bool,
) -> str:
    """The rule's words, written again here so no clause compares the subject with itself."""
    if not admissible or margin is None or out_of_sample is None or in_sample is None:
        return "unavailable"
    if out_of_sample[0] > margin and in_sample[0] > margin:
        return "room_to_win"
    if out_of_sample[1] < margin:
        return "no_room_to_win"
    return "straddles"


def _out_of_sample_rule(
    out_of_sample: tuple[float, float] | None, *, margin: float | None, admissible: bool
) -> str:
    """The out-of-sample interval's reading alone, by the same strict bounds."""
    if not admissible or margin is None or out_of_sample is None:
        return "unavailable"
    if out_of_sample[0] > margin:
        return "room_to_win"
    if out_of_sample[1] < margin:
        return "no_room_to_win"
    return "straddles"


def _priced_by(weights: tuple[int, int, int]) -> Callable[[int, GroupLevels], float]:
    """An integer-valued separable cost: exact means, frequent exact ties, a per-seed drift."""
    curvature, holding, drift = weights

    def cost_of(seed: int, levels: GroupLevels) -> float:
        per_group = (
            curvature * (point.S - 3) ** 2 + holding * point.s for point in levels.levels.values()
        )
        return float(sum(per_group) + drift * seed)

    return cost_of


def _one_group(s: int, order_up_to: int) -> GroupLevels:
    """A one-group level vector, for the built recheck cases."""
    return GroupLevels(levels={"sup_a": GridPoint(s=s, S=order_up_to)})


# ---------------------------------------------------------------------------
# (a), (b) -- the delayed hindsight rule, and the instantaneous rule it leaves untouched
# ---------------------------------------------------------------------------


@given(events=_EVENTS, opening=_OPENING, window=_WINDOWS, leads=_LEADS, horizon=_HORIZONS)
def test_under_a_delay_cumulative_supply_is_exactly_the_closed_form_at_every_decision(
    events: list[tuple[int, str, int]],
    opening: int,
    window: int,
    leads: dict[str, list[int]],
    horizon: int,
) -> None:
    """After the decision at ``t``, supply placed is ``max(I, G(min(a(t + w), H)))``, exactly.

    Stock ordered at ``t`` lands at ``a(t)`` and must serve every fulfilment until the next
    order lands at ``a(t + w)``; every unit fulfilled before then was generated before then. So
    this is the coverage the floor argument needs, asserted over the telescoping SUM of
    ``orders_at`` against a brute-force recomputation -- not against the arm's own closed form.
    """
    arrival = _arrival(leads)
    arm = HindsightOraclePolicy(
        trace=_trace(events),
        opening_stock=dict.fromkeys(_SKU_NAMES, float(opening)),
        window_min=float(window),
        arrival_time_for=arrival,
        horizon_min=float(horizon),
    )
    supplied = dict.fromkeys(_SKU_NAMES, Fraction(opening))

    for decision in _decisions(window, horizon):
        orders = arm.orders_at(decision)
        assert all(quantity > 0.0 for quantity in orders.values()), (
            f"at {decision} the arm sent a non-positive order {orders!r}"
        )
        for sku in _SKU_NAMES:
            # The precondition the rule's domain is stated over, checked rather than assumed.
            assert arrival(sku, decision + window) >= arrival(sku, decision)
            supplied[sku] += Fraction(orders.get(sku, 0.0))
            covered_until = min(arrival(sku, decision + window), float(horizon))
            expected = max(Fraction(opening), _generated_before(events, sku, covered_until))
            assert supplied[sku] == expected, (
                f"{sku} after the decision at {decision}: cumulative supply {supplied[sku]} is "
                f"not max(I, G({covered_until})) = {expected}, so a fulfilment before the next "
                "order lands could find an empty shelf, or the arm holds a buffer nobody chose"
            )


def test_a_delayed_arm_orders_at_minute_zero_what_an_instant_one_orders_an_hour_later() -> None:
    """The witness that the delay changes WHEN the arm orders, built rather than generated.

    Eight units are generated before minute 150. With a 90-minute lead time nothing ordered at
    minute 60 lands before 150, so all of them must be ordered at minute 0; with no delay the
    minute-0 order need only cover the first hour. Non-emptiness by construction: both arms
    order, and in different decisions.
    """
    events = [(0, "sku_0", 3), (70, "sku_0", 5)]

    def ninety_minutes(_sku: str, t_min: float) -> float:
        return t_min + 90.0

    delayed = HindsightOraclePolicy(
        trace=_trace(events),
        opening_stock={"sku_0": 2.0},
        window_min=60.0,
        arrival_time_for=ninety_minutes,
        horizon_min=300.0,
    )
    instantaneous = HindsightOraclePolicy(
        trace=_trace(events), opening_stock={"sku_0": 2.0}, window_min=60.0
    )

    assert delayed.orders_at(0.0) == {"sku_0": 6.0}
    assert delayed.orders_at(60.0) == {}
    assert instantaneous.orders_at(0.0) == {"sku_0": 1.0}
    assert instantaneous.orders_at(60.0) == {"sku_0": 5.0}


@given(events=_EVENTS, opening=_OPENING, window=_WINDOWS)
def test_with_no_arrival_function_the_orders_are_the_instantaneous_rule_byte_for_byte(
    events: list[tuple[int, str, int]], opening: int, window: int
) -> None:
    """``arrival_time_for=None`` is the rule every landed run used: ``max(I, G(t + w))``.

    Compared as dicts of floats with no tolerance -- same SKUs, same quantities -- against the
    instantaneous closed form recomputed by brute force, so a drift of one unit or one key fails.
    """
    arm = HindsightOraclePolicy(
        trace=_trace(events),
        opening_stock=dict.fromkeys(_SKU_NAMES, float(opening)),
        window_min=float(window),
    )

    for decision in _decisions(window, _NO_DELAY_HORIZON_MIN + window):
        expected: dict[str, float] = {}
        for sku in _SKU_NAMES:
            before = max(Fraction(opening), _generated_before(events, sku, decision))
            after = max(Fraction(opening), _generated_before(events, sku, decision + window))
            if after > before:
                expected[sku] = float(after - before)
        assert arm.orders_at(decision) == expected


@given(events=_EVENTS, opening=_OPENING, window=_WINDOWS)
def test_an_arrival_function_that_lands_orders_at_once_reproduces_the_instantaneous_orders(
    events: list[tuple[int, str, int]], opening: int, window: int
) -> None:
    """The delayed rule at zero delay IS the instantaneous rule, decision by decision.

    The cap is placed past the last decision's window so it binds nowhere, which isolates the
    one difference left: the delayed path reads its held cut-off at ``t`` and starts minute 0
    from the opening stock, and both must agree with ``G(t)`` when nothing is in transit.
    """
    decisions = _decisions(window, _NO_DELAY_HORIZON_MIN + window)
    plain = HindsightOraclePolicy(
        trace=_trace(events),
        opening_stock=dict.fromkeys(_SKU_NAMES, float(opening)),
        window_min=float(window),
    )
    immediate = HindsightOraclePolicy(
        trace=_trace(events),
        opening_stock=dict.fromkeys(_SKU_NAMES, float(opening)),
        window_min=float(window),
        arrival_time_for=_lands_at_once,
        horizon_min=decisions[-1] + window,
    )

    for decision in decisions:
        assert immediate.orders_at(decision) == plain.orders_at(decision)


def test_a_delay_without_a_horizon_or_a_horizon_without_a_delay_is_refused() -> None:
    """Built, not generated: each refusal is reached by constructing the state it refuses."""
    with pytest.raises(ValueError, match="horizon_min"):
        HindsightOraclePolicy(
            trace=DemandTrace(), opening_stock={}, arrival_time_for=_lands_at_once
        )
    with pytest.raises(ValueError, match="horizon_min"):
        HindsightOraclePolicy(
            trace=DemandTrace(),
            opening_stock={},
            arrival_time_for=_lands_at_once,
            horizon_min=math.inf,
        )
    with pytest.raises(ValueError, match="horizon_min"):
        HindsightOraclePolicy(trace=DemandTrace(), opening_stock={}, horizon_min=60.0)


# ---------------------------------------------------------------------------
# (c) -- room to win is read from the two ceiling intervals alone
# ---------------------------------------------------------------------------


@given(low=_BOUNDS, width=_WIDTHS, margin=_BOUNDS)
def test_the_out_of_sample_reading_is_one_reading_and_never_room_with_the_margin_inside(
    low: float, width: float, margin: float
) -> None:
    """Exhaustive and exclusive over every finite interval and margin; a straddle never wins."""
    high = low + width
    reading = room_to_win_out_of_sample((low, high), margin=margin, split_admissible=True)

    holds = {
        "room_to_win": low > margin,
        "no_room_to_win": high < margin,
        "straddles": low <= margin <= high,
    }
    assert sum(holds.values()) == 1, f"the readings do not partition [{low}, {high}] at {margin}"
    assert holds[reading], f"[{low}, {high}] at margin {margin} read as {reading!r}"
    if low <= margin <= high:
        assert reading == "straddles", "an interval containing the margin licensed room to win"


@given(out_low=_BOUNDS, out_width=_WIDTHS, in_low=_BOUNDS, in_width=_WIDTHS, margin=_BOUNDS)
def test_room_needs_both_ceilings_above_the_margin_and_the_recheck_can_only_withhold_it(
    out_low: float, out_width: float, in_low: float, in_width: float, margin: float
) -> None:
    """W2b R1's binding rule over every finite pair of intervals and margin.

    Never room while the in-sample ceiling reaches the margin; otherwise exactly the
    out-of-sample reading, except that the recheck may turn its room into a straddle.
    """
    out_of_sample = (out_low, out_low + out_width)
    in_sample = (in_low, in_low + in_width)

    reading = room_to_win(
        out_of_sample_ceiling=out_of_sample,
        in_sample_ceiling=in_sample,
        margin=margin,
        split_admissible=True,
    )
    alone = room_to_win_out_of_sample(out_of_sample, margin=margin, split_admissible=True)

    assert reading == _binding_rule(out_of_sample, in_sample, margin=margin, admissible=True)
    if in_low <= margin:
        assert reading != "room_to_win", "room licensed with the in-sample ceiling at the margin"
    assert reading == alone or (alone, reading) == ("room_to_win", "straddles"), (
        f"the recheck moved the out-of-sample reading {alone!r} to {reading!r}"
    )


def test_an_out_of_sample_room_whose_in_sample_ceiling_reaches_the_margin_only_straddles() -> None:
    """The conservative rule, built: E's ceiling clears the 0.4 margin and E_in's does not."""
    above = (0.6, 0.9)

    def binding(in_sample: tuple[float, float]) -> str:
        return room_to_win(
            out_of_sample_ceiling=above,
            in_sample_ceiling=in_sample,
            margin=0.4,
            split_admissible=True,
        )

    assert room_to_win_out_of_sample(above, margin=0.4, split_admissible=True) == "room_to_win"
    assert binding((0.3, 0.5)) == "straddles"
    assert binding((0.4, 0.7)) == "straddles"
    assert binding((0.1, 0.3)) == "straddles"
    assert binding((0.45, 0.8)) == "room_to_win"
    below = room_to_win(
        out_of_sample_ceiling=(0.1, 0.3),
        in_sample_ceiling=(0.5, 0.6),
        margin=0.4,
        split_admissible=True,
    )
    assert below == "no_room_to_win", "no room is read from the out-of-sample interval alone"
    with pytest.raises(ValueError, match="in-sample ceiling"):
        binding((0.5, 0.45))


@given(
    low=_BOUNDS,
    width=_WIDTHS,
    margin=_BOUNDS,
    absent=st.sampled_from(["split", "margin", "out_of_sample", "in_sample"]),
)
def test_room_to_win_is_unavailable_whenever_the_split_or_the_recheck_is_refused_or_unread(
    low: float, width: float, margin: float, absent: str
) -> None:
    """A refused split, an impossible recheck, an unread margin or a missing interval licenses
    no binding reading -- and only a missing in-sample one leaves the out-of-sample reading."""
    interval = (low, low + width)
    out_of_sample = None if absent == "out_of_sample" else interval
    read_margin = None if absent == "margin" else margin
    admissible = absent != "split"

    reading = room_to_win(
        out_of_sample_ceiling=out_of_sample,
        in_sample_ceiling=None if absent == "in_sample" else interval,
        margin=read_margin,
        split_admissible=admissible,
    )
    alone = room_to_win_out_of_sample(
        out_of_sample, margin=read_margin, split_admissible=admissible
    )

    assert reading == "unavailable"
    assert (alone == "unavailable") == (absent != "in_sample")


def test_each_reading_is_reached_and_an_endpoint_on_the_margin_straddles_it() -> None:
    """Non-emptiness of the partition, and the boundary R5.13's strictness turns on."""

    def alone(interval: tuple[float, float]) -> str:
        return room_to_win_out_of_sample(interval, margin=1.0, split_admissible=True)

    assert alone((1.5, 2.0)) == "room_to_win"
    assert alone((0.1, 0.5)) == "no_room_to_win"
    assert alone((0.5, 1.5)) == "straddles"
    assert alone((1.0, 2.0)) == "straddles"
    assert alone((0.0, 1.0)) == "straddles"
    with pytest.raises(ValueError, match="low <= high"):
        alone((2.0, 1.0))


def test_the_readings_take_only_the_ceiling_intervals_the_margin_and_admissibility() -> None:
    """Structural: no tuning gap, achievable value or regret can reach either reading, and the
    binding one takes its two intervals by keyword, so they cannot be swapped by position."""
    binding = inspect.signature(room_to_win).parameters
    assert list(binding) == [
        "out_of_sample_ceiling",
        "in_sample_ceiling",
        "margin",
        "split_admissible",
    ]
    assert all(param.kind is inspect.Parameter.KEYWORD_ONLY for param in binding.values())
    assert list(inspect.signature(room_to_win_out_of_sample).parameters) == [
        "ceiling_interval",
        "margin",
        "split_admissible",
    ]


# ---------------------------------------------------------------------------
# (d) -- the split refuses whenever hindsight fails to bound the structure-aware arm
# ---------------------------------------------------------------------------


@given(count=_COUNTS, shortfall=_SHORTFALLS)
def test_the_split_is_refused_whenever_hindsight_does_not_bound_the_structure_aware_arm(
    count: int, shortfall: float
) -> None:
    """``mean(O - D) < 0`` refuses with every other clause clean -- by construction."""
    reason = _reason(
        search_refusal=None,
        usable=dict.fromkeys(_SPLIT_ARMS, count),
        decomposition=None,
        residual_information_value=-shortfall,
    )

    assert "D is not an oracle in this world" in reason


@given(count=_COUNTS, residual=_NON_NEGATIVE)
def test_the_split_is_admitted_when_o_minus_d_is_non_negative_and_every_clause_is_clean(
    count: int, residual: float
) -> None:
    """The converse, so the refusal above is a predicate and not a constant."""
    clean = dict.fromkeys(_SPLIT_ARMS, count)

    assert (
        split_refusal(
            search_refusal=None,
            usable=clean,
            decomposition=None,
            residual_information_value=residual,
        )
        is None
    )
    assert (
        split_refusal(
            search_refusal=None, usable=clean, decomposition=None, residual_information_value=-0.0
        )
        is None
    )


def test_every_other_split_refusal_clause_fires_by_construction() -> None:
    """E's search, ragged counts, the two-term refusal and an undefined O - D each refuse."""
    clean = dict.fromkeys(_SPLIT_ARMS, 3)

    searched = _reason(
        search_refusal="search-box boundary",
        usable=clean,
        decomposition=None,
        residual_information_value=1.0,
    )
    assert "search refused" in searched
    ragged = _reason(
        search_refusal=None,
        usable={**clean, "structure_aware": 2},
        decomposition=None,
        residual_information_value=1.0,
    )
    assert "different replicate counts" in ragged
    inherited = _reason(
        search_refusal=None,
        usable=clean,
        decomposition="tuning gap -0.1 is NEGATIVE",
        residual_information_value=1.0,
    )
    assert "two-term decomposition" in inherited
    undefined = _reason(
        search_refusal=None, usable=clean, decomposition=None, residual_information_value=math.nan
    )
    assert "not finite" in undefined


@given(refusal=_SEARCH_REFUSALS, count=_COUNTS, gap=_NON_NEGATIVE, ceiling=_NON_NEGATIVE)
def test_a_refused_search_makes_the_two_term_split_inadmissible_whatever_its_terms(
    refusal: str, count: int, gap: float, ceiling: float
) -> None:
    """R2: a boundary or non-convergence refusal refuses on its own, every sign and count clean;
    the same terms are admitted without it, so the clause is a predicate and not a constant."""
    refused = decomposition_refusal(
        search_refusal=f"{refusal}: built",
        tuning_gap=gap,
        information_ceiling=ceiling,
        usable_judged=count,
        usable_tuned=count,
    )
    admitted = decomposition_refusal(
        search_refusal=None,
        tuning_gap=gap,
        information_ceiling=ceiling,
        usable_judged=count,
        usable_tuned=count,
    )

    assert refused is not None, "a refused search left the two-term split admissible"
    assert "search refused" in refused
    assert admitted is None


# ---------------------------------------------------------------------------
# (h) -- the in-sample recheck prices every candidate at every seed and keeps the first least
# ---------------------------------------------------------------------------


@given(
    selection=_LEVEL_VECTORS,
    heads_ranked=st.booleans(),
    ranked=st.lists(_LEVEL_VECTORS, max_size=5),
    neighbours=st.lists(_LEVEL_VECTORS, max_size=8),
    seeds=_RECHECK_SEEDS,
    weights=st.tuples(_WEIGHT, _WEIGHT, _WEIGHT),
)
def test_the_recheck_prices_every_candidate_at_every_seed_and_keeps_the_first_least_mean(
    selection: GroupLevels,
    heads_ranked: bool,
    ranked: list[GroupLevels],
    neighbours: list[GroupLevels],
    seeds: list[int],
    weights: tuple[int, int, int],
) -> None:
    """K is the ranked levels, then the neighbours, first occurrence kept; each member is priced
    once at each seed; E_in is K's FIRST least mean. When the selection heads ``ranked`` -- as a
    converged search's does -- a tie keeps it and E_in never costs more than it."""
    if heads_ranked:
        ranked = [selection, *ranked]
    priced = _priced_by(weights)
    calls: list[tuple[int, GroupLevels]] = []

    def cost_of(seed: int, levels: GroupLevels) -> float:
        calls.append((seed, levels))
        return priced(seed, levels)

    if not ranked and not neighbours:
        with pytest.raises(ValueError, match="no candidate"):
            in_sample_recheck(
                selection=selection,
                ranked=[],
                neighbours_of_selection=[],
                seeds=seeds,
                cost_of=cost_of,
                aggregate=statistics.fmean,
            )
        return
    recheck = in_sample_recheck(
        selection=selection,
        ranked=[(levels, 0.0) for levels in ranked],
        neighbours_of_selection=neighbours,
        seeds=seeds,
        cost_of=cost_of,
        aggregate=statistics.fmean,
    )

    expected: list[GroupLevels] = []
    for candidate in (*ranked, *neighbours):
        if candidate not in expected:
            expected.append(candidate)
    means = [statistics.fmean(priced(seed, member) for seed in seeds) for member in expected]
    least = min(means)
    assert list(recheck.members) == expected
    assert Counter(calls) == Counter((seed, member) for member in expected for seed in seeds)
    assert list(recheck.mean_costs) == means
    assert recheck.mean_cost == least
    assert recheck.levels == expected[means.index(least)], "E_in is not K's first least mean"
    assert recheck.costs == tuple(priced(seed, recheck.levels) for seed in seeds)
    if selection in expected:
        own = tuple(priced(seed, selection) for seed in seeds)
        assert recheck.selection_costs == own
        assert recheck.mean_cost <= statistics.fmean(own), "E_in costs more than the selection"
    else:
        assert recheck.selection_costs is None, "costs were reported for a selection outside K"
    if heads_ranked:
        assert recheck.members[0] == selection


def test_a_tie_keeps_the_selection_and_only_a_strictly_cheaper_candidate_displaces_it() -> None:
    """Built, not generated: the declared tie-break, and the one move it must take."""
    selection, tied, cheaper = _one_group(2, 3), _one_group(1, 3), _one_group(2, 4)

    def flat(_seed: int, _levels: GroupLevels) -> float:
        return 1.0

    def favours_cheaper(_seed: int, levels: GroupLevels) -> float:
        return 0.5 if levels == cheaper else 1.0

    kept = in_sample_recheck(
        selection=selection,
        ranked=[(selection, 1.0), (tied, 1.0)],
        neighbours_of_selection=[tied],
        seeds=[0, 1],
        cost_of=flat,
        aggregate=statistics.fmean,
    )
    moved = in_sample_recheck(
        selection=selection,
        ranked=[(selection, 1.0)],
        neighbours_of_selection=[tied, cheaper],
        seeds=[0, 1],
        cost_of=favours_cheaper,
        aggregate=statistics.fmean,
    )
    # A refused search need not head `ranked` with its selection; then K does not contain it.
    outside = in_sample_recheck(
        selection=selection,
        ranked=[(tied, 1.0)],
        neighbours_of_selection=[cheaper],
        seeds=[0, 1],
        cost_of=favours_cheaper,
        aggregate=statistics.fmean,
    )

    assert kept.members == (selection, tied)
    assert kept.levels == selection
    assert moved.levels == cheaper
    assert moved.mean_cost == 0.5
    assert moved.selection_costs == (1.0, 1.0)
    assert outside.members == (tied, cheaper)
    assert outside.selection_costs is None


def test_the_recheck_refuses_no_seed_no_candidate_and_a_non_finite_cost() -> None:
    """Built: a least mean over no seed, no candidate or a nan is not one over the seeds."""
    selection = _one_group(2, 3)

    def unit_cost(_seed: int, _levels: GroupLevels) -> float:
        return 1.0

    def nan_cost(_seed: int, _levels: GroupLevels) -> float:
        return math.nan

    with pytest.raises(ValueError, match="no seed"):
        in_sample_recheck(
            selection=selection,
            ranked=[(selection, 1.0)],
            neighbours_of_selection=[],
            seeds=[],
            cost_of=unit_cost,
            aggregate=statistics.fmean,
        )
    with pytest.raises(ValueError, match="no candidate"):
        in_sample_recheck(
            selection=selection,
            ranked=[],
            neighbours_of_selection=[],
            seeds=[0],
            cost_of=unit_cost,
            aggregate=statistics.fmean,
        )
    with pytest.raises(ValueError, match="non-finite"):
        in_sample_recheck(
            selection=selection,
            ranked=[(selection, 1.0)],
            neighbours_of_selection=[],
            seeds=[0],
            cost_of=nan_cost,
            aggregate=statistics.fmean,
        )


# ---------------------------------------------------------------------------
# Two pins on the coupling this leaf owns: the arm labels and the `--cell` flag
# ---------------------------------------------------------------------------


def test_the_arm_labels_are_appended_never_reordered_and_name_both_new_arms() -> None:
    """Counter totals, the cost family and the decomposition are keyed by this tuple."""
    assert ARM_LABELS[:5] == ("noop", "reference", "foresight", "hindsight", "tuned_static")
    assert ARM_LABELS[4] == TUNED_STATIC_ARM
    assert ARM_LABELS[5:] == (STRUCTURE_AWARE_ARM,)


@pytest.fixture
def _isolated_structlog() -> Iterator[None]:
    """Quiet the twin's per-event debug log for one test, then restore the global config.

    ``structlog.configure`` is process-global, and ``main`` calls it too; restoring keeps this
    file from changing what any later test logs.
    """
    saved: dict[str, Any] = dict(structlog.get_config())
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))
    try:
        yield
    finally:
        structlog.configure(**saved)


@pytest.mark.usefixtures("_isolated_structlog")
def test_the_cli_hands_the_named_cell_to_the_measurement_and_no_cell_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--cell NAME`` reaches ``_measure`` unchanged; omitted, the world before structures."""
    seen: list[tuple[int, float, str | None]] = []

    def _record(replicates: int, hours: float, cell: str | None) -> dict[str, object]:
        seen.append((replicates, hours, cell))
        return {"status": "measured"}

    monkeypatch.setattr(regret_module, "_measure", _record)

    named = ["--json", "--replicates", "3", "--hours", "2.5", "--cell", "a_declared_cell"]
    assert regret_module.main(named) == 0
    assert regret_module.main(["--json", "--replicates", "3", "--hours", "2.5"]) == 0
    assert seen == [(3, 2.5, "a_declared_cell"), (3, 2.5, None)]


# ---------------------------------------------------------------------------
# (e), (f), (g) -- the real twin, in declared world cells (slow; CI only under I-0)
# ---------------------------------------------------------------------------


def _small_candidates(world: ResolvedWorld | None) -> dict[str, tuple[int, ...]]:
    """Arm E's injected candidates: the same short list for every group this world has."""
    groups = sku_groups(world, stocked_skus(0, world=world))
    return dict.fromkeys(sorted(set(groups.values())), _SMALL_CANDIDATES)


def _one_tuning_seed() -> tuple[int, ...]:
    """The first committed tuning seed, so injected tuning stays disjoint by the file's range."""
    return tuple(load_tuning_spec().seeds)[:1]


def _float(report: Mapping[str, object], key: str) -> float:
    value = report.get(key)
    assert isinstance(value, float), f"{key} is {value!r}, not a measured float"
    return value


def _bounds(report: Mapping[str, object], key: str) -> tuple[float, float] | None:
    """A reported interval's ``(low, high)``, or ``None`` when the artifact reports none."""
    value = report.get(key)
    if value is None:
        return None
    assert isinstance(value, dict), f"{key} is {value!r}, not an interval"
    return (float(value["low"]), float(value["high"]))


@pytest.mark.slow
@pytest.mark.usefixtures("_isolated_structlog")
def test_under_a_delay_no_arm_leaves_less_demand_unmet_than_arm_d_at_any_seed() -> None:
    """Arm D's unmet demand is the floor at every seed, against all five other arms.

    Before a SKU's first arrival every arm holds the same opening stock against the same
    fulfilments; after it, arm D covers every fulfilment. Non-emptiness: the no-op arm holds only
    its opening stock against a day's demand, so it MUST stock out -- otherwise the inequality
    would hold as zero against zero and prove nothing.
    """
    world_spec = load_world()
    world = world_spec.resolve(world_spec.primary_cell)
    assert world.structure_3_on, "the primary cell must delay replenishment for this to bite"
    reference = comparator_reference_policy()
    incumbent = GridPoint(s=reference.reorder_point, S=reference.order_up_to)
    no_op_unmet = 0

    for seed in _SLOW_SEEDS:
        groups = sku_groups(world, stocked_skus(seed, world=world))
        levels = GroupLevels(levels=dict.fromkeys(sorted(set(groups.values())), incumbent))
        result = run_three_pass(
            seed,
            hours=_DAY_HOURS,
            restock_threshold=comparator_restock_threshold(),
            reference_policy=Par_Level_Reorder(
                s=reference.reorder_point, S=reference.order_up_to, seed=seed
            ),
            tuned_static_policy=GroupParLevelReorder(levels, groups, seed=seed),
            world=world,
        )
        hindsight, tuned = result.hindsight, result.tuned_static
        assert hindsight is not None and tuned is not None
        assert result.demand_identical, f"seed {seed}: the arms saw different demand"
        floor = hindsight.metrics.unmet_demand_events
        others = {
            "noop": result.noop,
            "reference": result.reference,
            "foresight": result.foresight,
            "tuned_static": tuned,
            "structure_aware": result.structure_aware,
        }
        for name, sim in others.items():
            assert floor <= sim.metrics.unmet_demand_events, (
                f"seed {seed}: arm {name} left {sim.metrics.unmet_demand_events} unit(s) unmet "
                f"against the hindsight arm's {floor}, so arm D is not the floor in this world"
            )
        no_op_unmet += result.noop.metrics.unmet_demand_events

    assert no_op_unmet > 0, "the no-op arm never stocked out, so the floor was never tested"


@pytest.mark.slow
@pytest.mark.usefixtures("_isolated_structlog")
def test_the_primary_cells_reported_split_is_exact_and_names_the_world_it_ran() -> None:
    """The artifact's terms are the differences of the means it reports, and its world is named.

    Each term is one IEEE subtraction of two reported means, so equality is exact. The recheck
    must reproduce arm E -- its surface carries arm E's own levels at arm E's own mean -- and
    report that surface's first least mean; both readings must be the rule recomputed from the
    reported intervals and margin; a refused search must refuse the two-term split. Whatever
    ``status`` the judged path reaches, the split, the recheck, the cell and the world are on the
    payload.
    """
    world_spec = load_world()
    cell = world_spec.primary_cell

    report = regret_module._measure(
        len(_SLOW_SEEDS),
        _DAY_HOURS,
        cell,
        candidates=_small_candidates(world_spec.resolve(cell)),
        tuning_seeds=_one_tuning_seed(),
    )

    assert report["cell"] == cell
    assert report["primary_cell"] is True
    world = report["world"]
    assert isinstance(world, dict)
    assert world["structure_1_on"] is True
    assert world["structure_3_on"] is True
    assert report["tuned_static_candidates_injected"] is True
    assert report["tuning_seeds_injected"] is True
    reference = _float(report, "mean_reference_cost")
    tuned = _float(report, "mean_tuned_static_cost")
    aware = _float(report, "mean_structure_aware_cost")
    hindsight = _float(report, "mean_hindsight_cost")
    in_sample = _float(report, "mean_in_sample_tuned_static_cost")
    assert report["tuning_gap"] == reference - tuned
    assert report["achievable_information_value"] == tuned - aware
    assert report["residual_information_value"] == aware - hindsight
    assert report["information_ceiling"] == tuned - hindsight
    assert report["information_ceiling_in_sample"] == in_sample - hindsight
    tuning_mean = _float(report, "tuned_static_mean_cost")
    assert report["tuning_vs_measurement_seed_gap"] == tuned - tuning_mean
    assert isinstance(report["split_residual_float"], float)
    assert "split_identity_exact" not in report, "a constant is reported as if it were measured"
    assert report["hindsight_unmet_pointwise_least"] is True

    # R1: the recheck re-priced arm E's own levels exactly, and kept its surface's first least.
    assert report["in_sample_reproduces_arm_e"] is True
    surface = report["in_sample_surface"]
    assert isinstance(surface, list)
    assert len(surface) == report["in_sample_candidates_evaluated"]
    selected = [entry for entry in surface if entry["levels"] == report["tuned_static_levels"]]
    assert len(selected) == 1, "arm E's own levels are not among the recheck's candidates"
    assert float(selected[0]["mean_cost"]) == tuned, "re-pricing arm E did not reproduce its mean"
    means = [float(entry["mean_cost"]) for entry in surface]
    assert in_sample == min(means) <= tuned
    assert report["in_sample_tuned_static_levels"] == surface[means.index(in_sample)]["levels"]
    assert (report["in_sample_recheck_refusal"] is None) == (
        report["information_ceiling_in_sample_interval"] is not None
    )

    # R2: a refused search refuses the two-term split as well as the three-term one.
    if report["tuned_static_refusal"] is not None:
        assert report["decomposition_admissible"] is False
        assert report["split_admissible"] is False

    # R5: both readings are the rule recomputed from what the artifact itself reports.
    margin = report["room_to_win_margin"]
    assert margin is None or isinstance(margin, float)
    admissible = report["split_admissible"] is True
    out_of_sample = _bounds(report, "information_ceiling_interval")
    assert report["room_to_win"] == _binding_rule(
        out_of_sample,
        _bounds(report, "information_ceiling_in_sample_interval"),
        margin=margin,
        admissible=admissible,
    )
    assert report["room_to_win_out_of_sample"] == _out_of_sample_rule(
        out_of_sample, margin=margin, admissible=admissible
    )


@pytest.mark.slow
@pytest.mark.usefixtures("_isolated_structlog")
def test_the_cell_with_both_structures_off_measures_the_judged_arms_as_no_cell_does() -> None:
    """Arms B and D are identical by construction there, so their costs agree to every digit."""
    world_spec = load_world()
    off = [
        name
        for name, spec in sorted(world_spec.cells.items())
        if not spec.structure_1 and not spec.structure_3
    ]
    assert off, "the committed grid declares no cell with both structures off"

    in_cell = regret_module._measure(
        len(_SLOW_SEEDS),
        _DAY_HOURS,
        off[0],
        candidates=_small_candidates(world_spec.resolve(off[0])),
        tuning_seeds=_one_tuning_seed(),
    )
    no_cell = regret_module._measure(
        len(_SLOW_SEEDS),
        _DAY_HOURS,
        None,
        candidates=_small_candidates(None),
        tuning_seeds=_one_tuning_seed(),
    )

    for key in ("mean_reference_cost", "mean_hindsight_cost", "regret"):
        assert _float(in_cell, key) == _float(no_cell, key), f"{key} moved with an empty cell"
    assert in_cell["cell"] == off[0]
    assert no_cell["cell"] is None
    assert no_cell["world"] is None
    world = in_cell["world"]
    assert isinstance(world, dict)
    assert world["structure_1_on"] is False
    assert world["structure_3_on"] is False
