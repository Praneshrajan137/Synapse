# Feature: decision-quality-proof, Property 94: A higher fill rate bought with a worse objective
# never reports a win
"""The headline is the committed objective, so holding more stock cannot buy a win.

Task 29.5 (R7.19), for task 29.4's Metric_Contract v2. Subjects:
``uplift/harness.py::assemble_uplift_result`` and ``uplift/contract.py::interval_verdict``.

**Carries finding 64.** Version 1 read the contract's first primary KPI, and the only one was
``fill_rate``, which rises with stock: an arm that simply holds more inventory beat the lean
tuned control on ``fill_rate`` while losing on the committed objective. Version 2 makes the
ADR-055 D2 objective the sole primary KPI. The overstocking arms generated below are better on
``fill_rate`` by construction -- the predecessor's fill-rate relative-percentage headline is
asserted POSITIVE for every one of them, so the trap is real on every example -- and worse on
the objective, and the headline must not call that a win.

**Clauses, each asserted unconditionally.**

1. Generated overstocking arms (higher ``fill_rate``, worse ``objective``) never classify
   ``win`` -- through :func:`~uplift.harness.assemble_uplift_result`, not only
   :func:`~uplift.contract.interval_verdict`. With every replicate worse by at least a fixed
   gap the verdict is exactly ``baseline_wins``; with a mixed sign but a worse mean it is
   ``inconclusive`` or ``baseline_wins``, never a gain of either size.
2. The four verdicts are exhaustive and mutually exclusive over generated admissible intervals,
   checked against the rule restated here independently of the subject.
3. The strict edges: ``low == m`` is ``sub_margin_gain``, ``low == 0`` and ``high == 0`` are
   ``inconclusive``, and ``high < 0`` -- down to the negative float nearest zero -- is
   ``baseline_wins``.
4. The headline equals ``interval.point`` exactly, and equals the mean seed-paired objective
   difference recomputed here; with nothing to pair it is the sentinel and no verdict exists.
5. Replicates are paired on seed: permuting one arm's run order moves neither the headline nor
   the interval. A deterministic case shows that pairing by POSITION would have moved the
   interval while leaving the point exactly where it was -- which is why the interval, not
   only the headline, is asserted.

**Pure.** Harness results are built by hand: no twin, no consensus network. Budget inherited
from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal. Locus: ``ci.yml::uplift-verify`` fast
step.
"""

from __future__ import annotations

import math
import statistics
from typing import TYPE_CHECKING, Final

from hypothesis import given
from hypothesis import strategies as st

from digital_twin.simulation.monte_carlo import ShockParams
from uplift.contract import interval_verdict, load_contract, relative_pct_change
from uplift.fidelity import FidelityReport
from uplift.harness import (
    NO_ESTIMATE_HEADLINE,
    HarnessResult,
    aggregate_arm,
    assemble_uplift_result,
)
from uplift.interfaces import (
    HEADLINE_VERDICTS,
    KpiVector,
    Outcome,
    Scenario,
    ScenarioRun,
    UpliftResult,
)
from uplift.interval import INTERVAL_SEED, paired_difference_interval

if TYPE_CHECKING:
    from collections.abc import Mapping

_CONTRACT = load_contract()
_FIDELITY = FidelityReport(kl_divergence=0.05, threshold=0.1)
_SUBJECT: Final[str] = "consensus"
_COMPARATOR: Final[str] = "Par_Level_Reorder"

_FINITE = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_MARGINS = st.floats(min_value=1e-6, max_value=100.0, allow_nan=False, allow_infinity=False)
_COSTS = st.floats(min_value=10.0, max_value=50.0, allow_nan=False, allow_infinity=False)
_FILLS = st.floats(min_value=0.1, max_value=0.85, allow_nan=False, allow_infinity=False)
_FILL_GAINS = st.floats(min_value=1e-3, max_value=0.1, allow_nan=False, allow_infinity=False)
#: The least amount by which an overstocking replicate's cost exceeds its comparator's. Bounded
#: away from zero so the sign of every paired difference survives rounding.
_LEAST_GAP: Final[float] = 1e-3
_GAPS = st.floats(min_value=_LEAST_GAP, max_value=10.0, allow_nan=False, allow_infinity=False)
_SPREAD = st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Hand-built harness results
# ---------------------------------------------------------------------------
def _kpis(*, objective: float, fill_rate: float, on_hand: float) -> KpiVector:
    return KpiVector(
        fill_rate=fill_rate,
        spoilage_rate=0.0,
        stockout_rate=1.0 - fill_rate,
        avg_delivery_time_min=20.0,
        margin=1.0,
        co2_estimate=1.0,
        avg_on_hand_units=on_hand,
        objective=objective,
    )


def _run(arm: str, seed: int, kpis: KpiVector) -> ScenarioRun:
    return ScenarioRun(arm=arm, seed=seed, kpis=kpis, failed=False, error=None)


def _harness(runs_by_pair: Mapping[tuple[str, str], list[ScenarioRun]]) -> HarnessResult:
    """A two-arm harness result: the consensus subject and one baseline-role comparator."""
    scenario_names = sorted({scenario for scenario, _ in runs_by_pair})
    return HarnessResult(
        arm_results={pair: aggregate_arm(pair[1], runs) for pair, runs in runs_by_pair.items()},
        runs_by_pair=dict(runs_by_pair),
        all_runs=[run for runs in runs_by_pair.values() for run in runs],
        results_path=None,
        scenarios=tuple(
            Scenario(name=name, seed=index, shock=ShockParams())
            for index, name in enumerate(scenario_names)
        ),
        arm_names=(_SUBJECT, _COMPARATOR),
        arm_roles={_SUBJECT: "consensus", _COMPARATOR: "baseline"},
    )


def _assemble(harness: HarnessResult, *, named: bool) -> UpliftResult:
    return assemble_uplift_result(
        harness,
        _CONTRACT,
        fidelity=_FIDELITY,
        consensus_arm=_SUBJECT,
        baseline_arm=_COMPARATOR if named else None,
    )


@st.composite
def _overstocking(draw: st.DrawFn, *, uniform: bool) -> HarnessResult:
    """Subject runs that hold more stock, fill more orders, and cost more, per scenario.

    ``uniform``: every replicate costs at least :data:`_LEAST_GAP` more than its comparator.
    Otherwise the per-replicate gaps have either sign, shifted so that EACH scenario's mean gap is
    at least :data:`_LEAST_GAP` -- the subject is worse on average, not on every replicate.
    """
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario_index in range(draw(st.integers(min_value=1, max_value=2))):
        scenario = f"scenario-{scenario_index}"
        count = draw(st.integers(min_value=1, max_value=5))
        costs = draw(st.lists(_COSTS, min_size=count, max_size=count))
        fills = draw(st.lists(_FILLS, min_size=count, max_size=count))
        gains = draw(st.lists(_FILL_GAINS, min_size=count, max_size=count))
        if uniform:
            gaps = draw(st.lists(_GAPS, min_size=count, max_size=count))
        else:
            spread = draw(st.lists(_SPREAD, min_size=count, max_size=count))
            shift = abs(statistics.fmean(spread)) + draw(_GAPS)
            gaps = [value + shift for value in spread]
        runs_by_pair[(scenario, _COMPARATOR)] = [
            _run(_COMPARATOR, seed, _kpis(objective=cost, fill_rate=fill, on_hand=50.0))
            for seed, (cost, fill) in enumerate(zip(costs, fills, strict=True))
        ]
        runs_by_pair[(scenario, _SUBJECT)] = [
            _run(
                _SUBJECT,
                seed,
                _kpis(objective=cost + gap, fill_rate=fill + gain, on_hand=150.0),
            )
            for seed, (cost, fill, gain, gap) in enumerate(
                zip(costs, fills, gains, gaps, strict=True)
            )
        ]
    return _harness(runs_by_pair)


def _samples(harness: HarnessResult, arm: str, kpi: str) -> list[float]:
    return [
        value
        for scenario in harness.scenarios
        for value in harness.kpi_samples(scenario.name, arm, kpi)
    ]


def _assert_better_on_fill_rate(harness: HarnessResult) -> None:
    """The trap is real: the predecessor's fill-rate headline reads a GAIN for this subject."""
    subject = _samples(harness, _SUBJECT, "fill_rate")
    comparator = _samples(harness, _COMPARATOR, "fill_rate")
    assert relative_pct_change(subject, comparator) > 0.0
    assert statistics.fmean(_samples(harness, _SUBJECT, "objective")) > statistics.fmean(
        _samples(harness, _COMPARATOR, "objective")
    )


# ---------------------------------------------------------------------------
# Clause 1 -- an overstocking arm never classifies as a win
# ---------------------------------------------------------------------------
@given(harness=_overstocking(uniform=True), named=st.booleans())
def test_an_arm_worse_on_every_replicate_is_a_baseline_win_however_much_more_it_fills(
    harness: HarnessResult, named: bool
) -> None:
    """Every replicate costs more: the interval lies wholly below zero, so the baseline wins."""
    _assert_better_on_fill_rate(harness)
    result = _assemble(harness, named=named)

    assert result.interval is not None
    assert result.headline_verdict == "baseline_wins"
    assert result.headline_verdict != "win"
    assert result.headline_uplift < 0.0
    assert result.per_kpi == {"objective": Outcome.BASELINE_WINS}
    assert result.per_scenario
    assert all(outcome is Outcome.BASELINE_WINS for outcome in result.per_scenario.values())
    assert result.all_wins_warning is False
    assert "fill_rate" in result.secondary_kpis


@given(harness=_overstocking(uniform=False), named=st.booleans())
def test_an_arm_worse_on_average_is_never_a_gain_of_any_size(
    harness: HarnessResult, named: bool
) -> None:
    """A mixed sign but a worse mean: the point is negative, so no interval is a gain."""
    _assert_better_on_fill_rate(harness)
    result = _assemble(harness, named=named)

    assert result.interval is not None
    assert result.headline_uplift < 0.0
    assert result.headline_verdict in ("inconclusive", "baseline_wins")
    assert result.per_kpi["objective"] is not Outcome.SYNAPSE_WINS
    assert result.per_scenario
    assert all(outcome is not Outcome.SYNAPSE_WINS for outcome in result.per_scenario.values())
    assert result.all_wins_warning is False


# ---------------------------------------------------------------------------
# Clause 2 -- the four verdicts are exhaustive and mutually exclusive
# ---------------------------------------------------------------------------
def _restated(low: float, high: float, margin: float) -> dict[str, bool]:
    """R7.19's four predicates, written out here rather than imported from the subject."""
    return {
        "win": low > margin,
        "sub_margin_gain": 0.0 < low <= margin,
        "inconclusive": low <= 0.0 <= high,
        "baseline_wins": high < 0.0,
    }


@st.composite
def _admissible(draw: st.DrawFn) -> tuple[float, float, float]:
    """``(low, high, margin)`` with ``low <= high``, dense at the edges the rule turns on."""
    margin = draw(_MARGINS)
    edges = (
        0.0,
        -0.0,
        margin,
        math.nextafter(margin, math.inf),
        math.nextafter(margin, -math.inf),
        math.nextafter(0.0, math.inf),
        math.nextafter(0.0, -math.inf),
    )
    bound = st.one_of(_FINITE, st.sampled_from(edges))
    low, high = sorted((draw(bound), draw(bound)))
    return low, high, margin


@given(case=_admissible())
def test_the_four_verdicts_are_exhaustive_and_mutually_exclusive(
    case: tuple[float, float, float],
) -> None:
    """Exactly one predicate holds for every admissible interval, and it is the one returned."""
    low, high, margin = case
    verdict = interval_verdict(low, high, margin=margin)
    predicates = _restated(low, high, margin)

    assert set(predicates) == set(HEADLINE_VERDICTS)
    assert sum(predicates.values()) == 1
    assert predicates[verdict] is True


# ---------------------------------------------------------------------------
# Clause 3 -- the strict edges
# ---------------------------------------------------------------------------
@given(margin=_MARGINS, extra=st.floats(min_value=0.0, max_value=1e3, allow_nan=False))
def test_each_edge_falls_on_the_strict_side_of_its_bound(margin: float, extra: float) -> None:
    """On the margin is not above it; touching zero contains it; any negative high is a loss."""
    just_above_margin = math.nextafter(margin, math.inf)
    smallest_gain = math.nextafter(0.0, math.inf)
    largest_loss = math.nextafter(0.0, -math.inf)

    assert interval_verdict(margin, margin + extra, margin=margin) == "sub_margin_gain"
    assert interval_verdict(just_above_margin, margin + extra + 1.0, margin=margin) == "win"
    assert interval_verdict(0.0, extra, margin=margin) == "inconclusive"
    assert interval_verdict(-extra, 0.0, margin=margin) == "inconclusive"
    assert interval_verdict(-extra - 1.0, largest_loss, margin=margin) == "baseline_wins"
    assert interval_verdict(smallest_gain, margin + extra, margin=margin) == "sub_margin_gain"


# ---------------------------------------------------------------------------
# Clauses 4 and 5 -- the headline is the point, paired on seed
# ---------------------------------------------------------------------------
@st.composite
def _paired(draw: st.DrawFn) -> HarnessResult:
    """Arbitrary objective samples for both arms, one to two scenarios, distinct seeds."""
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
    for scenario_index in range(draw(st.integers(min_value=1, max_value=2))):
        scenario = f"scenario-{scenario_index}"
        count = draw(st.integers(min_value=1, max_value=5))
        seeds = draw(
            st.lists(
                st.integers(min_value=0, max_value=2**32 - 1),
                min_size=count,
                max_size=count,
                unique=True,
            )
        )
        for arm in (_SUBJECT, _COMPARATOR):
            costs = draw(st.lists(_COSTS, min_size=count, max_size=count))
            runs_by_pair[(scenario, arm)] = [
                _run(arm, seed, _kpis(objective=cost, fill_rate=0.5, on_hand=50.0))
                for seed, cost in zip(seeds, costs, strict=True)
            ]
    return _harness(runs_by_pair)


def _by_seed(harness: HarnessResult, scenario: str, arm: str) -> dict[int, float]:
    return {
        run.seed: run.kpis.objective
        for run in harness.runs_by_pair[(scenario, arm)]
        if run.kpis is not None
    }


@given(harness=_paired(), named=st.booleans())
def test_the_headline_is_the_interval_point_and_the_mean_seed_paired_difference(
    harness: HarnessResult, named: bool
) -> None:
    """One number, computed once: the point, which is the mean of comparator minus subject."""
    result = _assemble(harness, named=named)

    assert result.interval is not None
    assert result.headline_uplift == result.interval.point
    assert result.headline_verdict == interval_verdict(
        result.interval.low, result.interval.high, margin=_CONTRACT.materiality_margin
    )
    differences: list[float] = []
    for scenario in harness.scenarios:
        subject = _by_seed(harness, scenario.name, _SUBJECT)
        comparator = _by_seed(harness, scenario.name, _COMPARATOR)
        assert set(subject) == set(comparator)
        differences.extend(comparator[seed] - subject[seed] for seed in subject)
    assert differences
    assert result.headline_uplift == statistics.fmean(differences)


def test_with_nothing_to_pair_the_headline_is_the_sentinel_and_no_verdict_exists() -> None:
    """A subject that completed no replicate: no interval, the sentinel, no verdict, incomplete."""
    failed = [
        ScenarioRun(arm=_SUBJECT, seed=seed, kpis=None, failed=True, error="unavailable")
        for seed in range(3)
    ]
    comparator = [
        _run(_COMPARATOR, seed, _kpis(objective=20.0 + seed, fill_rate=0.5, on_hand=50.0))
        for seed in range(3)
    ]
    result = _assemble(
        _harness({("scenario-0", _SUBJECT): failed, ("scenario-0", _COMPARATOR): comparator}),
        named=True,
    )
    assert result.interval is None
    assert result.headline_verdict is None
    assert result.headline_uplift == NO_ESTIMATE_HEADLINE
    assert result.per_kpi == {"objective": Outcome.TIE_INCONCLUSIVE}
    assert result.incomplete is True


@given(harness=_paired(), named=st.booleans(), data=st.data())
def test_permuting_one_arms_run_order_moves_neither_the_headline_nor_the_interval(
    harness: HarnessResult, named: bool, data: st.DataObject
) -> None:
    """Pairing is by seed, so the order runs were recorded in is not part of the measurement."""
    permuted_arm = data.draw(st.sampled_from((_SUBJECT, _COMPARATOR)))
    permuted_runs = {
        pair: (list(data.draw(st.permutations(runs))) if pair[1] == permuted_arm else runs)
        for pair, runs in harness.runs_by_pair.items()
    }

    original = _assemble(harness, named=named)
    permuted = _assemble(_harness(permuted_runs), named=named)

    assert permuted.headline_uplift == original.headline_uplift
    assert permuted.interval == original.interval
    assert permuted.headline_verdict == original.headline_verdict
    assert permuted.per_scenario == original.per_scenario


def test_pairing_by_position_would_have_moved_the_interval_but_not_the_point() -> None:
    """Why clause 5 asserts the interval: a mis-paired mean is the same number.

    Seed-paired differences are ``1, 2, 3``. Recording the comparator's runs in reverse order
    and pairing by position would give ``23, 2, -19``: the same mean -- a difference of means
    does not care how it is paired -- and a far wider interval. So a headline-only check could
    not tell seed pairing from position pairing, and the interval can.
    """
    subject = [10.0, 20.0, 30.0]
    comparator = [11.0, 22.0, 33.0]
    in_order = {
        ("scenario-0", _SUBJECT): [
            _run(_SUBJECT, seed, _kpis(objective=cost, fill_rate=0.5, on_hand=50.0))
            for seed, cost in enumerate(subject)
        ],
        ("scenario-0", _COMPARATOR): [
            _run(_COMPARATOR, seed, _kpis(objective=cost, fill_rate=0.5, on_hand=50.0))
            for seed, cost in enumerate(comparator)
        ],
    }
    reversed_order = {
        **in_order,
        ("scenario-0", _COMPARATOR): list(reversed(in_order[("scenario-0", _COMPARATOR)])),
    }

    seed_paired = _assemble(_harness(in_order), named=True)
    recorded_backwards = _assemble(_harness(reversed_order), named=True)
    position_paired = paired_difference_interval(
        list(reversed(comparator)),
        subject,
        alpha=_CONTRACT.alpha,
        resamples=_CONTRACT.resamples,
        seed=INTERVAL_SEED,
    )

    assert seed_paired.interval is not None
    assert recorded_backwards.interval == seed_paired.interval
    assert position_paired.point == seed_paired.interval.point == 2.0
    assert position_paired.width > seed_paired.interval.width
