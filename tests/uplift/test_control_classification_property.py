# Feature: decision-quality-proof, Property 84: Controls classify by interval position, and the
# repetition rate matches the committed alpha
"""Each control reads where its interval lies against zero; the null rate is judged at alpha.

Leaves 16.4 and 16.5 (R6.1, R6.2, R6.15). Subject: ``uplift/controls.py`` --
``classify_positive_control``, ``classify_negative_control`` and the records they judge.

**What would make the subject wrong**, one clause each: (a) a positive control ``detected`` on
an interval that merely EXCLUDES zero -- one wholly below it -- or whose low bound sits exactly
ON zero; (b) a repetition counted as a proven gain without its low bound lying strictly above
zero; (c) a negative-control verdict other than ``pass`` iff ``count <= floor(bound * n)`` at
the committed ``n`` and bound, or one that moves with the order repetitions arrive in; (d) a
rate, or a pass, over fewer repetitions than declared; (e) seed ranges shared within a
repetition -- on identical ranges two copies of a deterministic arm give a ``[0, 0]`` interval
that cannot fail (finding 69) -- or across repetitions, or a duplicated or undeclared
repetition, admitted rather than refused; (f) a verdict reached at any ``alpha`` but the
Metric_Contract's, or under a rate bound at which the control could never fail; (g) a reading
that can be built, or read back, carrying a verdict, position or rate its own interval or
counts do not license -- a ``detected`` on an interval containing zero, a ``pass`` over fewer
repetitions than declared.

**Domain, stated (R2.10).** Generated bounds are whole thousandths, so every comparison with
zero is exact and no clause rides on rounding. Clause (c) is asserted at the COMMITTED ``n``
and bound only, read through ``negative_control_settings()``: the subject divides
(``count / n <= bound``) where the clause multiplies, and the two agree at 20 and ``0.20``
(hand-checked: ``0.2 * 20`` rounds to exactly ``4.0``, and ``4 / 20`` to the same double as
``0.20``). For an arbitrary float bound they need not, so no wider claim is made.

Not slow-marked, although task 16.5's body says ``@pytest.mark.slow``: that marker predates the
2026-09-29 re-scope, and the subject is pure arithmetic over frozen records -- no twin, no
harness run, no subprocess. Locus: ``ci.yml::uplift-verify-fast-1``
(``tests/uplift/test_[abcdefghijklmno]*.py``, ``ci`` profile). Budget inherited from
``HYPOTHESIS_PROFILE``; no ``max_examples`` literal, and no example total is asserted.
"""

from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, get_args

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from digital_twin.simulation.policy import negative_control_settings
from uplift.controls import (
    JudgedInterval,
    NegativeControlReading,
    NegativeControlVerdict,
    NegativeRepetition,
    Position,
    PositiveControlReading,
    PositiveControlVerdict,
    SeedRange,
    classify_negative_control,
    classify_positive_control,
)
from uplift.interval import INTERVAL_SEED, METHOD, Interval, contract_alpha, resamples_for

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Bounds are whole thousandths, so ``low > 0`` and ``high < 0`` are exact comparisons.
_THOUSANDTHS: Final[float] = 1000.0

#: The grid's reach either side of zero, in thousandths: five objective units.
_SPAN: Final[int] = 5_000


@functools.cache
def _committed_alpha() -> float:
    """The Metric_Contract's ``alpha``, read once. No confidence level is a literal here."""
    return contract_alpha()


@functools.cache
def _committed_settings() -> tuple[int, float]:
    """ADR-055 D6's ``(independent_seed_sets, max_proven_gain_rate)``, as the policy commits."""
    return negative_control_settings()


@dataclass(frozen=True)
class _RawBounds:
    """An interval-shaped record that checks nothing, so the controls' OWN refusals are proven.

    ``uplift.interval.Interval`` refuses a non-finite or inverted interval at construction, so
    it cannot carry one to a classifier. An interval read back from an artifact has passed
    through no estimator; this is that case.
    """

    low: float
    high: float
    point: float
    alpha: float


def _interval(low: int, point: int, high: int) -> Interval:
    """The estimator's computation form at the committed ``alpha``, from whole thousandths."""
    alpha = _committed_alpha()
    return Interval(
        method=METHOD,
        alpha=alpha,
        resamples=resamples_for(alpha),
        seed=INTERVAL_SEED,
        low=low / _THOUSANDTHS,
        high=high / _THOUSANDTHS,
        point=point / _THOUSANDTHS,
    )


def _judged(triple: tuple[int, int, int]) -> JudgedInterval:
    """``(low, point, high)`` in thousandths, as a control records it."""
    return JudgedInterval.of(_interval(*triple))


def _repetition(index: int, triple: tuple[int, int, int], *, replicates: int) -> NegativeRepetition:
    """Repetition ``index``: both copies of arm E, each on its own block of seeds.

    The blocks are laid out by index -- ``[2ir, 2ir + r)`` and ``[(2i + 1)r, (2i + 2)r)`` -- so
    no seed is shared within a repetition or across any two: the premise these cases hold fixed.
    """
    return NegativeRepetition(
        index=index,
        subject_seeds=SeedRange(start=2 * index * replicates, count=replicates),
        comparator_seeds=SeedRange(start=(2 * index + 1) * replicates, count=replicates),
        interval=_judged(triple),
    )


def _classify(repetitions: Sequence[NegativeRepetition]) -> NegativeControlReading:
    """The negative control judged at ADR-055 D6's committed count and bound."""
    required, bound = _committed_settings()
    return classify_negative_control(
        repetitions, required_repetitions=required, max_proven_gain_rate=bound
    )


def _neighbouring_alphas() -> tuple[float, ...]:
    """Levels a stray interval could carry, none of them the committed one.

    One ulp either side of it -- so the refusal is an exact comparison, not a tolerance -- and
    two ordinary others.
    """
    committed = _committed_alpha()
    return (
        math.nextafter(committed, 0.0),
        math.nextafter(committed, 1.0),
        committed / 2.0,
        (1.0 + committed) / 2.0,
    )


@st.composite
def _ordered(draw: st.DrawFn, lowest: int, highest: int) -> tuple[int, int, int]:
    """``(low, point, high)`` on the grid within ``[lowest, highest]``; ties are allowed."""
    values = sorted(
        draw(st.lists(st.integers(min_value=lowest, max_value=highest), min_size=3, max_size=3))
    )
    return values[0], values[1], values[2]


@st.composite
def _containing_zero(draw: st.DrawFn) -> tuple[int, int, int]:
    """An interval with ``low <= 0 <= high``: an endpoint exactly ON zero contains it."""
    low = draw(st.integers(min_value=-_SPAN, max_value=0))
    high = draw(st.integers(min_value=0, max_value=_SPAN))
    return low, draw(st.integers(min_value=low, max_value=high)), high


#: Strictly above zero: a proven gain. The least such low bound is one thousandth.
_ABOVE_ZERO = _ordered(1, _SPAN)

#: Strictly below zero: a proven LOSS, which R6.15 records but does not count.
_BELOW_ZERO = _ordered(-_SPAN, -1)

#: Everything that is not a proven gain.
_NOT_ABOVE_ZERO = st.one_of(_containing_zero(), _BELOW_ZERO)

#: Anywhere on the grid.
_ANYWHERE = _ordered(-_SPAN, _SPAN)

#: Replicates per side. Small on purpose: no clause reads the count, only that it is shared.
_REPLICATES = st.integers(min_value=1, max_value=8)


# ---------------------------------------------------------------------------
# The positive control (R6.2): detected iff the interval lies entirely above zero
# ---------------------------------------------------------------------------


@given(triple=_ANYWHERE)
@example(triple=(0, 0, 0))
@example(triple=(0, 1, 2))
@example(triple=(1, 1, 1))
@example(triple=(-2, -1, 0))
@example(triple=(-3, -2, -1))
def test_a_positive_control_is_detected_exactly_when_its_low_bound_lies_above_zero(
    triple: tuple[int, int, int],
) -> None:
    """``detected`` iff ``low > 0``, with the position recorded beside the interval it judged.

    The examples pin the edges a looser rule would pass: a low bound exactly ON zero, a high
    bound exactly on zero, a degenerate interval at zero, the least detection, and an interval
    wholly below zero -- which excludes zero, on the wrong side.
    """
    low, _point, high = triple
    reading = classify_positive_control(_interval(*triple))
    assert reading.verdict == ("detected" if low > 0 else "not_detected")
    assert reading.position == (
        "above_zero" if low > 0 else "below_zero" if high < 0 else "contains_zero"
    )
    assert reading.interval == _judged(triple)
    assert reading.explanation.strip()
    assert reading.explanation.isascii()


@given(triple=_BELOW_ZERO)
def test_an_interval_wholly_below_zero_excludes_zero_and_is_still_not_detected(
    triple: tuple[int, int, int],
) -> None:
    """R6.2 replaced "excludes zero" because an interval wholly below zero satisfies it too."""
    reading = classify_positive_control(_interval(*triple))
    assert reading.verdict == "not_detected"
    assert reading.position == "below_zero"


@given(data=st.data())
def test_a_low_bound_exactly_on_zero_contains_zero_and_is_not_detected(
    data: st.DataObject,
) -> None:
    """A low bound ON zero contains zero, so detects nothing; negative zero is the same point."""
    high = data.draw(st.integers(min_value=0, max_value=_SPAN), label="high")
    point = data.draw(st.integers(min_value=0, max_value=high), label="point")
    reading = classify_positive_control(_interval(0, point, high))
    assert reading.verdict == "not_detected"
    assert reading.position == "contains_zero"
    signed = _RawBounds(
        low=-0.0, high=high / _THOUSANDTHS, point=point / _THOUSANDTHS, alpha=_committed_alpha()
    )
    assert classify_positive_control(signed).verdict == "not_detected"


def _assert_only_its_own_verdict_is_admitted(reading: PositiveControlReading) -> None:
    """Every ``(verdict, position)`` pair but the recorded one is refused for that interval.

    The untouched payload round-trips first, so each refusal is the forged pair's.
    """
    payload = reading.model_dump()
    assert PositiveControlReading.model_validate(payload) == reading
    recorded = (reading.verdict, reading.position)
    pairs = itertools.product(get_args(PositiveControlVerdict), (*get_args(Position), None))
    forged = [pair for pair in pairs if pair != recorded]
    assert forged
    for verdict, position in forged:
        with pytest.raises(ValueError, match="do not license"):
            PositiveControlReading.model_validate(
                {**payload, "verdict": verdict, "position": position}
            )


def test_an_absent_positive_control_is_unavailable_and_never_detected() -> None:
    """No interval means the harness was shown neither to detect nor to miss: not a pass.

    Nor can the absence be recorded as anything else: every other verdict is refused.
    """
    reading = classify_positive_control(None)
    assert reading.verdict == "unavailable"
    assert reading.position is None
    assert reading.interval is None
    assert reading.explanation.strip()
    _assert_only_its_own_verdict_is_admitted(reading)


@given(triple=_ANYWHERE)
@example(triple=(0, 1, 2))
@example(triple=(1, 1, 1))
@example(triple=(-3, -2, -1))
def test_a_positive_control_reading_its_interval_does_not_license_is_refused(
    triple: tuple[int, int, int],
) -> None:
    """A ``detected`` read back from an artifact is one its interval shows, or it is refused.

    Pinned at a low bound ON zero, the least detection and an interval wholly below zero.
    """
    _assert_only_its_own_verdict_is_admitted(classify_positive_control(_interval(*triple)))


@pytest.mark.parametrize(
    ("low", "high", "point"),
    [
        (math.nan, 1.0, 0.5),
        (-math.inf, 1.0, 0.5),
        (0.0, math.inf, 0.5),
        (0.0, 1.0, math.nan),
        (1.0, 0.0, 0.5),
        (0.0, 1.0, 2.0),
    ],
    ids=["nan-low", "infinite-low", "infinite-high", "nan-point", "inverted", "point-outside"],
)
def test_a_malformed_positive_control_interval_is_refused_rather_than_classified(
    low: float, high: float, point: float
) -> None:
    """Non-finite, inverted or not bracketing its own point: a defect, never a verdict.

    The same unchecked record with admissible numbers IS classified, so the refusal is the
    defect's and not the record type's.
    """
    alpha = _committed_alpha()
    with pytest.raises(ValueError, match="malformed"):
        classify_positive_control(_RawBounds(low=low, high=high, point=point, alpha=alpha))
    admissible = _RawBounds(low=0.0, high=1.0, point=0.5, alpha=alpha)
    assert classify_positive_control(admissible).verdict == "not_detected"


def test_a_positive_control_at_any_alpha_but_the_committed_one_is_refused() -> None:
    """A verdict at another level is a different test; one ulp away is refused like any other."""
    alphas = _neighbouring_alphas()
    assert alphas
    assert _committed_alpha() not in alphas
    for alpha in alphas:
        with pytest.raises(ValueError, match="committed alpha"):
            classify_positive_control(_RawBounds(low=0.1, high=0.3, point=0.2, alpha=alpha))
    committed = _RawBounds(low=0.1, high=0.3, point=0.2, alpha=_committed_alpha())
    assert classify_positive_control(committed).verdict == "detected"


# ---------------------------------------------------------------------------
# The negative control (R6.1, R6.15): E against E on disjoint seeds, judged by its gain rate
# ---------------------------------------------------------------------------


@given(triple=_ANYWHERE, replicates=_REPLICATES)
@example(triple=(0, 0, 0), replicates=1)
@example(triple=(0, 2, 5), replicates=1)
@example(triple=(1, 2, 5), replicates=1)
def test_a_repetition_reports_a_proven_gain_exactly_when_its_low_bound_lies_above_zero(
    triple: tuple[int, int, int], replicates: int
) -> None:
    """Strict: a low bound ON zero contains zero, so it proves no gain."""
    assert _repetition(0, triple, replicates=replicates).proven_gain is (triple[0] > 0)


@given(data=st.data())
def test_the_negative_control_passes_iff_its_gain_count_is_within_the_committed_rate(
    data: st.DataObject,
) -> None:
    """``pass`` iff ``count <= floor(bound * n)``, with ``n`` and the bound as committed.

    The reading records what the verdict was judged on -- the count, ``n``, the rate, the bound
    and the committed ``alpha``. Proven losses are recorded and never counted (R6.15 counts
    gains), and the same repetitions supplied in another order give the same reading.
    """
    required, bound = _committed_settings()
    gains = data.draw(st.integers(min_value=0, max_value=required), label="gains")
    flags = data.draw(
        st.permutations([True] * gains + [False] * (required - gains)), label="gain flags"
    )
    triples = [data.draw(_ABOVE_ZERO if flag else _NOT_ABOVE_ZERO) for flag in flags]
    replicates = data.draw(_REPLICATES, label="replicates")
    repetitions = [
        _repetition(index, triple, replicates=replicates) for index, triple in enumerate(triples)
    ]
    reading = _classify(repetitions)
    assert reading.verdict == ("pass" if gains <= math.floor(bound * required) else "fail")
    assert reading.proven_gain_count == gains
    assert reading.proven_loss_count == sum(1 for _low, _point, high in triples if high < 0)
    assert reading.supplied == reading.required == required
    assert reading.rate == gains / required
    assert reading.max_proven_gain_rate == bound
    assert reading.alpha == _committed_alpha()
    order = data.draw(st.permutations(range(required)), label="supplied order")
    assert _classify([repetitions[index] for index in order]) == reading


def test_the_committed_bound_passes_at_its_floor_and_fails_one_gain_above_it() -> None:
    """Both verdicts are reachable at the committed values, so the negative control CAN fail."""
    required, bound = _committed_settings()
    allowed = math.floor(bound * required)
    assert 0 <= allowed < required, (
        f"floor({bound!r} * {required}) = {allowed}: a bound admitting every count is a "
        "negative control that cannot fail"
    )

    def judged_with(gains: int) -> NegativeControlReading:
        triples = [(1, 2, 3)] * gains + [(-1, 0, 1)] * (required - gains)
        return _classify(
            [_repetition(index, triple, replicates=2) for index, triple in enumerate(triples)]
        )

    at_floor, above_floor = judged_with(allowed), judged_with(allowed + 1)
    assert at_floor.verdict == "pass"
    assert at_floor.proven_gain_count == allowed
    assert above_floor.verdict == "fail"
    assert above_floor.proven_gain_count == allowed + 1


@given(data=st.data())
def test_fewer_repetitions_than_declared_are_unavailable_and_never_a_pass(
    data: st.DataObject,
) -> None:
    """Short of the declared count no rate is estimated, whatever the supplied ones show."""
    required, _bound = _committed_settings()
    supplied = data.draw(st.integers(min_value=0, max_value=required - 1), label="supplied")
    indices = data.draw(
        st.lists(
            st.integers(min_value=0, max_value=required - 1),
            min_size=supplied,
            max_size=supplied,
            unique=True,
        ),
        label="indices",
    )
    replicates = data.draw(_REPLICATES, label="replicates")
    repetitions = [
        _repetition(index, data.draw(_ANYWHERE), replicates=replicates) for index in indices
    ]
    reading = _classify(repetitions)
    assert reading.verdict == "unavailable"
    assert reading.rate is None
    assert reading.supplied == supplied
    assert reading.required == required
    assert reading.explanation.strip()


def test_a_shortfall_is_unavailable_even_when_the_same_null_repetitions_would_pass() -> None:
    """The verdict is the shortfall's alone: the declared count of the same nulls does pass."""
    required, _bound = _committed_settings()
    nulls = [_repetition(index, (-1, 0, 1), replicates=2) for index in range(required)]
    assert _classify([]).verdict == "unavailable"
    assert _classify(nulls[:-1]).verdict == "unavailable"
    assert _classify(nulls).verdict == "pass"


@given(data=st.data())
def test_a_repetition_running_both_copies_on_overlapping_seeds_is_refused(
    data: st.DataObject,
) -> None:
    """A seed on both sides is one realisation counted twice; the pair is refused, not judged."""
    count = data.draw(st.integers(min_value=1, max_value=50), label="count")
    start = data.draw(st.integers(min_value=count, max_value=10_000), label="start")
    shift = data.draw(st.integers(min_value=1 - count, max_value=count - 1), label="shift")
    with pytest.raises(ValueError, match="overlapping seeds"):
        NegativeRepetition(
            index=0,
            subject_seeds=SeedRange(start=start, count=count),
            comparator_seeds=SeedRange(start=start + shift, count=count),
            interval=_judged((-1, 0, 1)),
        )


def test_identical_seed_ranges_are_refused_because_their_interval_could_never_fail() -> None:
    """Finding 69 by construction, and the boundary beside it: adjacent ranges share no seed."""
    seeds = SeedRange(start=0, count=4)
    with pytest.raises(ValueError, match="cannot fail"):
        NegativeRepetition(
            index=0, subject_seeds=seeds, comparator_seeds=seeds, interval=_judged((0, 0, 0))
        )
    adjacent = NegativeRepetition(
        index=0,
        subject_seeds=seeds,
        comparator_seeds=SeedRange(start=seeds.stop, count=seeds.count),
        interval=_judged((0, 0, 0)),
    )
    assert adjacent.subject_seeds.stop == adjacent.comparator_seeds.start
    assert not adjacent.subject_seeds.overlaps(adjacent.comparator_seeds)


def test_a_repetition_pairing_ranges_of_unequal_length_is_refused() -> None:
    """Pairing by index needs one length on both sides."""
    with pytest.raises(ValueError, match="one length"):
        NegativeRepetition(
            index=0,
            subject_seeds=SeedRange(start=0, count=3),
            comparator_seeds=SeedRange(start=3, count=4),
            interval=_judged((-1, 0, 1)),
        )


@given(replicates=_REPLICATES, data=st.data())
def test_seed_ranges_shared_across_repetitions_are_refused(
    replicates: int, data: st.DataObject
) -> None:
    """Each repetition is internally disjoint; one seed shared between two is still refused."""
    offset = data.draw(st.integers(min_value=0, max_value=replicates - 1), label="offset")
    first = _repetition(0, (-1, 0, 1), replicates=replicates)
    second = NegativeRepetition(
        index=1,
        subject_seeds=SeedRange(start=replicates + offset, count=replicates),
        comparator_seeds=SeedRange(start=10 * replicates, count=replicates),
        interval=_judged((-1, 0, 1)),
    )
    assert second.subject_seeds.overlaps(first.comparator_seeds)
    with pytest.raises(ValueError, match="overlap"):
        _classify([first, second])


@given(data=st.data())
def test_a_duplicated_repetition_index_is_refused_rather_than_counted_twice(
    data: st.DataObject,
) -> None:
    """Two repetitions claiming one declared slot are refused, even on disjoint seeds."""
    required, _bound = _committed_settings()
    index = data.draw(st.integers(min_value=0, max_value=required - 1), label="index")
    first = _repetition(index, (1, 2, 3), replicates=2)
    copy = NegativeRepetition(
        index=index,
        subject_seeds=SeedRange(start=10_000, count=2),
        comparator_seeds=SeedRange(start=10_002, count=2),
        interval=_judged((1, 2, 3)),
    )
    with pytest.raises(ValueError, match="appears twice"):
        _classify([first, copy])


def test_a_repetition_nobody_declared_is_refused() -> None:
    """An index past the declared count would license running until the rate looks good."""
    required, _bound = _committed_settings()
    with pytest.raises(ValueError, match="undeclared"):
        _classify([_repetition(required, (-1, 0, 1), replicates=2)])


def test_repetitions_at_different_replicate_counts_are_refused() -> None:
    """A rate is a proportion of ONE experiment repeated; another replicate count is another."""
    with pytest.raises(ValueError, match="different experiments"):
        _classify(
            [
                _repetition(0, (-1, 0, 1), replicates=2),
                _repetition(1, (-1, 0, 1), replicates=3),
            ]
        )


def test_a_repetition_judged_at_any_alpha_but_the_committed_one_is_refused() -> None:
    """The rate is judged at the Metric_Contract's alpha and at no neighbour of it."""
    alphas = _neighbouring_alphas()
    assert alphas
    for alpha in alphas:
        stray = NegativeRepetition(
            index=0,
            subject_seeds=SeedRange(start=0, count=2),
            comparator_seeds=SeedRange(start=2, count=2),
            interval=JudgedInterval(low=-0.1, high=0.1, point=0.0, alpha=alpha),
        )
        with pytest.raises(ValueError, match="committed alpha"):
            _classify([stray])


@pytest.mark.parametrize("bound", [-0.1, 1.0, 1.5, math.nan, math.inf])
def test_a_rate_bound_naming_no_proportion_or_admitting_every_count_is_refused(
    bound: float,
) -> None:
    """At ``1`` every count passes, so the control could never fail; outside ``[0, 1]`` none can.

    The committed bound, with the same inputs, is admitted.
    """
    required, committed = _committed_settings()
    with pytest.raises(ValueError, match="max_proven_gain_rate"):
        classify_negative_control([], required_repetitions=required, max_proven_gain_rate=bound)
    admitted = classify_negative_control(
        [], required_repetitions=required, max_proven_gain_rate=committed
    )
    assert admitted.verdict == "unavailable"


def test_a_declared_repetition_count_below_one_is_refused() -> None:
    """A rate over no declared repetition is a proportion of nothing."""
    _required, bound = _committed_settings()
    with pytest.raises(ValueError, match="required_repetitions"):
        classify_negative_control([], required_repetitions=0, max_proven_gain_rate=bound)


@given(data=st.data())
def test_a_negative_control_reading_its_own_counts_do_not_license_is_refused(
    data: st.DataObject,
) -> None:
    """A ``pass`` over too few repetitions, or over more gains than the bound admits, is refused.

    Every verdict but the licensed one, and any rate but the licensed one, is refused at
    construction, so a reading read back from an artifact says what its counts say. About half
    the draws supply the declared count, so ``pass`` and ``fail`` readings are forged as well as
    ``unavailable`` ones; the untouched payload round-trips, so each refusal is the forged
    field's.
    """
    required, _bound = _committed_settings()
    supplied = data.draw(
        st.one_of(st.just(required), st.integers(min_value=0, max_value=required - 1)),
        label="supplied",
    )
    gains = data.draw(st.integers(min_value=0, max_value=supplied), label="gains")
    triples = [(1, 2, 3)] * gains + [(-1, 0, 1)] * (supplied - gains)
    reading = _classify(
        [_repetition(index, triple, replicates=2) for index, triple in enumerate(triples)]
    )
    payload = reading.model_dump()
    assert NegativeControlReading.model_validate(payload) == reading
    verdicts = get_args(NegativeControlVerdict)
    forged = [verdict for verdict in verdicts if verdict != reading.verdict]
    assert forged
    for verdict in forged:
        with pytest.raises(ValueError, match="do not license"):
            NegativeControlReading.model_validate({**payload, "verdict": verdict})
    moved_rate = 0.0 if reading.rate is None else None
    with pytest.raises(ValueError, match="do not license"):
        NegativeControlReading.model_validate({**payload, "rate": moved_rate})


def test_a_negative_control_reading_with_impossible_counts_is_refused() -> None:
    """More repetitions than declared, or more proofs than repetitions, cannot be recorded.

    Nor can a bound at which the control could never fail, or a level that names none. The
    untouched payload round-trips, so each refusal is the forged field's.
    """
    required, _bound = _committed_settings()
    nulls = [_repetition(index, (-1, 0, 1), replicates=2) for index in range(required)]
    reading = _classify(nulls)
    assert reading.verdict == "pass"
    payload = reading.model_dump()
    assert NegativeControlReading.model_validate(payload) == reading
    with pytest.raises(ValueError, match="undeclared"):
        NegativeControlReading.model_validate({**payload, "supplied": required + 1})
    with pytest.raises(ValueError, match="one or neither"):
        NegativeControlReading.model_validate(
            {**payload, "proven_gain_count": required, "proven_loss_count": 1}
        )
    with pytest.raises(ValueError, match="not a proportion"):
        NegativeControlReading.model_validate({**payload, "max_proven_gain_rate": 1.0})
    with pytest.raises(ValueError, match="names no level"):
        NegativeControlReading.model_validate({**payload, "alpha": 1.0})
