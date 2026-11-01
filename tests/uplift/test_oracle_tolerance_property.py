# Feature: decision-quality-proof, Property 85: An out-of-tolerance oracle effect is a
# mis-measurement, never under-performance
"""Breaking the re-cut R6.3 agreement rule convicts the harness; nothing can convict arm O.

Leaves 16.2 and 16.6 (R6.3, R6.4, R6.5). Subject: ``uplift/controls.py`` --
``classify_agreement``, ``agreement_difference`` and the ``AgreementReading`` record -- and
``digital_twin/simulation/policy.py::detection_probability``.

**What would make the subject wrong**, one clause each: (a) any verdict, reason or record able
to say arm O under-performs (R6.4); (b) a reading other than the re-cut R6.3 rule -- ``agrees``
iff the interval on ``(harness E - O) - (comparator E - O)`` contains 0 AND the harness's low
bound is at or below the information ceiling ``E - D``'s high bound -- or one that drops or
misorders a failed clause; (c) a difference interval other than the normal approximation from
the two half-widths, or one that swapping the estimates does not negate; (d) the B-prime primary
cell's measured ``E - O`` failing to agree with itself under either measured ceiling; (e) an
absent estimate read as anything but ``unavailable``, or a malformed or foreign-``alpha`` one
read at all, even beside an absent one; (f) a detection probability defaulted, coerced or
admitted outside ``(0, 1)``, or an R6.3 tolerance NUMBER committed beside it; (g) an agreement
reading that can be built, or read back, carrying a verdict, a set of clauses or a difference
interval its own three estimates do not license.

**Domain, stated (R2.10).** Generated bounds are whole thousandths, so every verdict clause is
an exact comparison. Clause (c) is checked against ``math.hypot`` -- an independent evaluation
of the same formula -- to a relative ``1e-9``; the subject's ``sqrt(a * a + b * b)`` and the
subtraction that recovers a half-width each lose a few ulps at most.

**Measured inputs** (run 36860454801, sha ec0eb91, 200 replicates, primary cell), not
re-measured here. The ceiling ``E - D`` -- ``0.62953`` on ``[0.59583, 0.66606]`` out of sample
and ``[0.59486, 0.66380]`` in sample -- is read from tasks.md task 14. The ``E - O`` interval,
``0.24629`` on ``[0.21442, 0.27600]``, is relayed from that run's cell artifact by the session
contract: no in-tree document records it (ADR-055 D2.9 states only ``0.246``).

Pure arithmetic plus one small YAML file per reader case; not slow-marked. Locus:
``ci.yml::uplift-verify-fast-1`` (``tests/uplift/test_[abcdefghijklmno]*.py``, ``ci`` profile).
Budget inherited from ``HYPOTHESIS_PROFILE``; no ``max_examples`` literal.
"""

from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, get_args

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from digital_twin.simulation.policy import (
    PolicyUnavailableError,
    detection_probability,
    load_policy,
)
from uplift.controls import (
    AGREEMENT_ASSUMPTION,
    AGREEMENT_METHOD,
    AgreementReading,
    AgreementVerdict,
    IntervalBounds,
    JudgedInterval,
    MisMeasurement,
    PositiveControlVerdict,
    agreement_difference,
    classify_agreement,
)
from uplift.interval import INTERVAL_SEED, METHOD, Interval, contract_alpha, resamples_for

if TYPE_CHECKING:
    from pathlib import Path

#: Bounds are whole thousandths, so every clause comparison is exact.
_THOUSANDTHS: Final[float] = 1000.0

#: The grid's reach either side of zero, in thousandths: five objective units.
_SPAN: Final[int] = 5_000

#: The ceiling's point, read from tasks.md task 14. Only a ceiling's HIGH bound is judged; the
#: in-sample interval's own point is not recorded in-tree, so this one stands in for it too.
_CEILING_POINT: Final[float] = 0.62953


@functools.cache
def _committed_alpha() -> float:
    """The Metric_Contract's ``alpha``, read once. No confidence level is a literal here."""
    return contract_alpha()


@dataclass(frozen=True)
class _RawBounds:
    """An interval-shaped record that checks nothing, so the classifier's OWN refusals are proven.

    ``uplift.interval.Interval`` refuses a non-finite or inverted interval at construction, so
    it cannot carry one to a classifier. An interval read back from an artifact has passed
    through no estimator; this is that case.
    """

    low: float
    high: float
    point: float
    alpha: float


def _at_alpha(low: float, point: float, high: float) -> Interval:
    """The estimator's computation form at the committed ``alpha``."""
    alpha = _committed_alpha()
    return Interval(
        method=METHOD,
        alpha=alpha,
        resamples=resamples_for(alpha),
        seed=INTERVAL_SEED,
        low=low,
        high=high,
        point=point,
    )


def _grid(triple: tuple[int, int, int]) -> Interval:
    """``(low, point, high)`` in whole thousandths."""
    low, point, high = triple
    return _at_alpha(low / _THOUSANDTHS, point / _THOUSANDTHS, high / _THOUSANDTHS)


def _measured_e_minus_o() -> Interval:
    """The comparator's measured ``E - O``, B-prime primary cell (see the module docstring)."""
    return _at_alpha(0.21442, 0.24629, 0.27600)


def _measured_ceiling() -> Interval:
    """The out-of-sample information ceiling ``E - D`` in the same cell (tasks.md task 14)."""
    return _at_alpha(0.59583, _CEILING_POINT, 0.66606)


def _neighbouring_alphas() -> tuple[float, ...]:
    """Levels a stray estimate could carry, none of them the committed one.

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


#: Anywhere on the grid.
_ANYWHERE = _ordered(-_SPAN, _SPAN)


# ---------------------------------------------------------------------------
# R6.4: the vocabulary cannot say that arm O under-performs
# ---------------------------------------------------------------------------


def test_no_verdict_or_reason_in_the_vocabulary_says_the_oracle_under_performs() -> None:
    """Closed vocabularies, asserted exactly: a member added later must be argued against R6.4.

    The agreement record's own ``verdict`` field carries exactly that vocabulary, so a reading
    cannot be built that says more than the classifier can.
    """
    assert set(get_args(AgreementVerdict)) == {"agrees", "harness_mis_measuring", "unavailable"}
    assert get_args(MisMeasurement) == (
        "disagrees_with_comparator",
        "exceeds_information_ceiling",
    )
    assert set(get_args(PositiveControlVerdict)) == {"detected", "not_detected", "unavailable"}
    vocabulary = (
        *get_args(AgreementVerdict),
        *get_args(MisMeasurement),
        *get_args(PositiveControlVerdict),
    )
    assert vocabulary
    for member in vocabulary:
        assert "under" not in member, member
        assert "perform" not in member, member
    verdict_field = AgreementReading.model_fields["verdict"].annotation
    assert get_args(verdict_field) == get_args(AgreementVerdict)


def test_a_record_naming_an_under_performing_oracle_is_refused_by_construction() -> None:
    """The record refuses the reading R6.4 forbids, and refuses it for that field alone.

    The untouched payload round-trips, and each refusal is exactly one error, located at the
    tampered field. Asserted on the location rather than the message: the record also
    re-derives its verdict, and that model-level refusal repeats the whole payload -- field
    names included -- in its message, so a message match could not tell the two apart.
    """
    measured = _measured_e_minus_o()
    reading = classify_agreement(harness=measured, comparator=measured, ceiling=_measured_ceiling())
    payload = reading.model_dump()
    assert AgreementReading.model_validate(payload) == reading
    tampered_fields: tuple[tuple[str, object], ...] = (
        ("verdict", "oracle_under_performing"),
        ("reasons", ("oracle_under_performing",)),
    )
    for field_name, value in tampered_fields:
        with pytest.raises(ValidationError) as refused:
            AgreementReading.model_validate({**payload, field_name: value})
        assert [error["loc"][:1] for error in refused.value.errors()] == [(field_name,)]


# ---------------------------------------------------------------------------
# R6.3 as re-cut: the reading is exactly the two-clause agreement rule
# ---------------------------------------------------------------------------


@given(harness=_ANYWHERE, comparator=_ANYWHERE, ceiling=_ANYWHERE)
def test_the_agreement_verdict_is_exactly_the_two_clause_rule(
    harness: tuple[int, int, int],
    comparator: tuple[int, int, int],
    ceiling: tuple[int, int, int],
) -> None:
    """Every failed clause is named, in declared order, and ``agrees`` means none failed.

    The disagreement clause is read off the recorded difference interval (its construction is
    the normal-approximation property's, below); the ceiling clause off the two bounds it
    compares.
    """
    reading = classify_agreement(
        harness=_grid(harness), comparator=_grid(comparator), ceiling=_grid(ceiling)
    )
    difference = reading.difference
    assert difference is not None
    failed = (
        ("disagrees_with_comparator", difference.low > 0.0 or difference.high < 0.0),
        ("exceeds_information_ceiling", harness[0] > ceiling[2]),
    )
    expected = tuple(reason for reason, fired in failed if fired)
    assert reading.reasons == expected
    assert reading.verdict == ("harness_mis_measuring" if expected else "agrees")
    assert reading.harness == JudgedInterval.of(_grid(harness))
    assert reading.comparator == JudgedInterval.of(_grid(comparator))
    assert reading.ceiling == JudgedInterval.of(_grid(ceiling))
    assert reading.method == AGREEMENT_METHOD
    assert reading.assumption == AGREEMENT_ASSUMPTION
    assert reading.explanation.isascii()


@given(harness=_ANYWHERE, comparator=_ANYWHERE, ceiling=_ANYWHERE)
def test_an_agreement_reading_its_own_estimates_do_not_license_is_refused(
    harness: tuple[int, int, int],
    comparator: tuple[int, int, int],
    ceiling: tuple[int, int, int],
) -> None:
    """An ``agrees`` read back from an artifact is one its three estimates license, or refused.

    Every other verdict, the complementary set of clauses and a shifted difference interval
    are each refused, as are a foreign method and a ceiling at another alpha. The untouched
    payload round-trips, so each refusal is the forged field's.
    """
    reading = classify_agreement(
        harness=_grid(harness), comparator=_grid(comparator), ceiling=_grid(ceiling)
    )
    payload = reading.model_dump()
    assert AgreementReading.model_validate(payload) == reading
    verdicts = get_args(AgreementVerdict)
    clauses = get_args(MisMeasurement)
    complement = tuple(clause for clause in clauses if clause not in reading.reasons)
    assert complement != reading.reasons
    recorded = payload["difference"]
    shifted = {
        "low": recorded["low"] - 1.0,
        "point": recorded["point"] - 1.0,
        "high": recorded["high"] - 1.0,
        "alpha": recorded["alpha"],
    }
    forgeries: list[tuple[str, object]] = [
        *(("verdict", verdict) for verdict in verdicts if verdict != reading.verdict),
        ("reasons", complement),
        ("difference", shifted),
    ]
    for field_name, value in forgeries:
        with pytest.raises(ValueError, match="do not license"):
            AgreementReading.model_validate({**payload, field_name: value})
    with pytest.raises(ValueError, match="the one method whose"):
        AgreementReading.model_validate({**payload, "method": "welch_t_interval"})
    stray = {**payload["ceiling"], "alpha": _neighbouring_alphas()[0]}
    with pytest.raises(ValueError, match="one verdict is read at one alpha"):
        AgreementReading.model_validate({**payload, "ceiling": stray})


@given(harness=_ANYWHERE, comparator=_ANYWHERE)
def test_the_difference_interval_is_the_normal_approximation_and_a_swap_negates_it(
    harness: tuple[int, int, int], comparator: tuple[int, int, int]
) -> None:
    """Centred on the difference of the points, half-width ``hypot`` of the two half-widths."""
    first, second = JudgedInterval.of(_grid(harness)), JudgedInterval.of(_grid(comparator))
    forward = agreement_difference(first, second)
    backward = agreement_difference(second, first)
    expected_half = math.hypot((first.high - first.low) / 2.0, (second.high - second.low) / 2.0)
    assert forward.point == first.point - second.point
    assert forward.alpha == _committed_alpha()
    for half in (forward.high - forward.point, forward.point - forward.low):
        assert math.isclose(half, expected_half, rel_tol=1e-9, abs_tol=1e-12)
    assert (backward.low, backward.point, backward.high) == (
        -forward.high,
        -forward.point,
        -forward.low,
    )


@given(
    comparator=_ANYWHERE,
    shape=_ANYWHERE,
    gap=st.integers(min_value=1, max_value=_SPAN),
    upward=st.booleans(),
)
def test_estimates_whose_difference_excludes_zero_disagree_with_the_comparator(
    comparator: tuple[int, int, int],
    shape: tuple[int, int, int],
    gap: int,
    upward: bool,
) -> None:
    """Points further apart than both widths together disagree, whichever estimate is higher.

    The ceiling sits at the higher of the two low bounds, so its clause holds either way round
    and the disagreement is the only clause that fails.
    """
    c_low, c_point, c_high = comparator
    s_low, s_point, s_high = shape
    distance = (s_high - s_low) + (c_high - c_low) + gap
    shift = c_point - s_point + (distance if upward else -distance)
    harness = (s_low + shift, s_point + shift, s_high + shift)
    top = max(harness[0], c_low)
    ceiling = _grid((top - 1, top, top))
    forward = classify_agreement(
        harness=_grid(harness), comparator=_grid(comparator), ceiling=ceiling
    )
    swapped = classify_agreement(
        harness=_grid(comparator), comparator=_grid(harness), ceiling=ceiling
    )
    for reading in (forward, swapped):
        assert reading.verdict == "harness_mis_measuring"
        assert reading.reasons == ("disagrees_with_comparator",)


@given(
    harness=_ANYWHERE,
    gap=st.integers(min_value=1, max_value=_SPAN),
    width=st.integers(min_value=0, max_value=_SPAN),
)
def test_a_harness_low_bound_above_the_ceilings_high_bound_exceeds_the_information_ceiling(
    harness: tuple[int, int, int], gap: int, width: int
) -> None:
    """Agreeing with the comparator does not excuse an ``E - O`` above the ceiling ``E - D``.

    The clause is strict: a low bound exactly ON the ceiling's high bound is still within it.
    """
    low = harness[0]
    estimate = _grid(harness)
    top = low - gap
    above = classify_agreement(
        harness=estimate, comparator=estimate, ceiling=_grid((top - width, top, top))
    )
    assert above.verdict == "harness_mis_measuring"
    assert above.reasons == ("exceeds_information_ceiling",)
    touching = classify_agreement(
        harness=estimate, comparator=estimate, ceiling=_grid((low - width, low, low))
    )
    assert touching.verdict == "agrees"
    assert touching.reasons == ()


@pytest.mark.parametrize(
    ("ceiling_low", "ceiling_high"),
    [(0.59583, 0.66606), (0.59486, 0.66380)],
    ids=["out-of-sample", "in-sample"],
)
def test_the_measured_b_prime_e_minus_o_agrees_with_itself_under_the_measured_ceiling(
    ceiling_low: float, ceiling_high: float
) -> None:
    """A harness that reproduced the comparator's measured ``E - O`` exactly must agree."""
    measured = _measured_e_minus_o()
    reading = classify_agreement(
        harness=measured,
        comparator=measured,
        ceiling=_at_alpha(ceiling_low, _CEILING_POINT, ceiling_high),
    )
    assert reading.verdict == "agrees"
    assert reading.reasons == ()
    assert reading.difference is not None
    assert reading.difference.point == 0.0
    assert reading.difference.low < 0.0 < reading.difference.high
    assert reading.harness == reading.comparator == JudgedInterval.of(measured)


def test_a_harness_estimate_above_the_measured_ceiling_breaks_both_clauses_in_order() -> None:
    """A harness ``E - O`` of ``[0.70, 0.80]`` breaks both clauses against the measured values.

    It disagrees with the comparator's ``[0.21442, 0.27600]`` and its low bound exceeds the
    ceiling's ``0.66606``: both are named, in declared order, and the harness is convicted.
    """
    reading = classify_agreement(
        harness=_at_alpha(0.70, 0.75, 0.80),
        comparator=_measured_e_minus_o(),
        ceiling=_measured_ceiling(),
    )
    assert reading.verdict == "harness_mis_measuring"
    assert reading.reasons == ("disagrees_with_comparator", "exceeds_information_ceiling")


# ---------------------------------------------------------------------------
# Absent, malformed and foreign-alpha estimates
# ---------------------------------------------------------------------------


def test_a_missing_estimate_is_unavailable_and_never_an_agreement() -> None:
    """Without all three estimates nothing is shown either way, and that is not a pass (I-7).

    The same three estimates, all present, do agree, so each ``unavailable`` is the absence's;
    and no absence can be recorded as either verdict.
    """
    measured, ceiling = _measured_e_minus_o(), _measured_ceiling()
    complete = classify_agreement(harness=measured, comparator=measured, ceiling=ceiling)
    assert complete.verdict == "agrees"
    presence = itertools.product((True, False), repeat=3)
    absences = [present for present in presence if not all(present)]
    assert absences
    for has_harness, has_comparator, has_ceiling in absences:
        reading = classify_agreement(
            harness=measured if has_harness else None,
            comparator=measured if has_comparator else None,
            ceiling=ceiling if has_ceiling else None,
        )
        assert reading.verdict == "unavailable"
        assert reading.reasons == ()
        assert reading.difference is None
        assert (reading.harness is not None) is has_harness
        assert (reading.comparator is not None) is has_comparator
        assert (reading.ceiling is not None) is has_ceiling
        assert reading.explanation.strip()
        payload = reading.model_dump()
        for verdict in ("agrees", "harness_mis_measuring"):
            with pytest.raises(ValueError, match="do not license"):
                AgreementReading.model_validate({**payload, "verdict": verdict})


def test_an_estimate_at_another_alpha_is_refused_even_beside_an_absent_one() -> None:
    """A defect is never masked as ``unavailable``: the level is checked before absence is."""
    measured = _measured_e_minus_o()
    alphas = _neighbouring_alphas()
    assert alphas
    for alpha, position in itertools.product(alphas, ("harness", "comparator", "ceiling")):
        stray = _RawBounds(low=measured.low, high=measured.high, point=measured.point, alpha=alpha)
        arguments: dict[str, IntervalBounds | None] = {
            "harness": None,
            "comparator": None,
            "ceiling": None,
        }
        arguments[position] = stray
        with pytest.raises(ValueError, match="committed alpha"):
            classify_agreement(**arguments)


def test_two_estimates_at_different_alphas_form_no_difference_interval() -> None:
    """At two levels the half-widths are in different units, so no difference is formed."""
    measured = JudgedInterval.of(_measured_e_minus_o())
    other = JudgedInterval(
        low=measured.low, high=measured.high, point=measured.point, alpha=_neighbouring_alphas()[0]
    )
    with pytest.raises(ValueError, match="different units"):
        agreement_difference(measured, other)


@pytest.mark.parametrize("position", ["harness", "comparator", "ceiling"])
@pytest.mark.parametrize(
    ("low", "high", "point"),
    [
        (math.nan, 1.0, 0.5),
        (0.0, math.inf, 0.5),
        (1.0, 0.0, 0.5),
        (0.0, 1.0, 2.0),
    ],
    ids=["nan-low", "infinite-high", "inverted", "point-outside"],
)
def test_a_malformed_estimate_is_refused_rather_than_read(
    position: str, low: float, high: float, point: float
) -> None:
    """Non-finite, inverted or not bracketing its own point, wherever it is supplied."""
    measured = _measured_e_minus_o()
    arguments: dict[str, IntervalBounds | None] = {
        "harness": measured,
        "comparator": measured,
        "ceiling": _measured_ceiling(),
    }
    arguments[position] = _RawBounds(low=low, high=high, point=point, alpha=_committed_alpha())
    with pytest.raises(ValueError, match="malformed"):
        classify_agreement(**arguments)


# ---------------------------------------------------------------------------
# Task 16.2: the committed detection probability, and the absence of a tolerance number
# ---------------------------------------------------------------------------


def _policy_file(tmp_path: Path, document: dict[str, object]) -> Path:
    """A minimal policy file holding ``document`` and nothing else."""
    target = tmp_path / "policy.yaml"
    target.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
    return target


def test_the_committed_detection_probability_is_r6s_pre_registered_target() -> None:
    """R6 introduces one number, ``0.80``: a pre-registered target, not a measurement.

    Read here through its reader rather than transcribed beside it.
    """
    assert detection_probability() == 0.80


def test_no_numeric_oracle_tolerance_is_committed_beside_the_detection_probability() -> None:
    """R6.3's tolerance is a rule since the 2026-09-29 re-scope; no tolerance number is committed.

    A number here would be judged against, which is exactly what the re-scope withdrew.
    """
    block = load_policy()["positive_control"]
    assert isinstance(block, dict)
    assert set(block) == {"detection_probability"}


def test_the_reader_returns_the_value_its_file_commits(tmp_path: Path) -> None:
    """The reader reads the file it is given; it does not return a constant."""
    path = _policy_file(tmp_path, {"positive_control": {"detection_probability": 0.9}})
    assert detection_probability(path) == 0.9


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"positive_control": {}},
        {"positive_control": None},
        {"positive_control": 0.8},
        {"positive_control": {"detection_probabilty": 0.8}},
    ],
    ids=["no-block", "empty-block", "null-block", "scalar-block", "misspelt-key"],
)
def test_a_missing_detection_probability_is_refused_and_never_defaulted(
    tmp_path: Path, document: dict[str, object]
) -> None:
    """A missing key raises naming it; nothing is substituted for a committed target."""
    with pytest.raises(PolicyUnavailableError, match="positive_control"):
        detection_probability(_policy_file(tmp_path, document))


@pytest.mark.parametrize(
    "value",
    [0.0, 1.0, -0.5, 1.5, 0, 1, math.nan, math.inf, -math.inf, True, False, "0.80", None, [0.8]],
)
def test_a_detection_probability_outside_the_open_unit_interval_or_not_a_number_is_refused(
    tmp_path: Path, value: object
) -> None:
    """Outside ``(0, 1)`` there is no finite quantile to state an effect at.

    A boolean or a string is not a probability anybody committed, and is not coerced into one.
    """
    path = _policy_file(tmp_path, {"positive_control": {"detection_probability": value}})
    with pytest.raises(PolicyUnavailableError, match="detection_probability"):
        detection_probability(path)
