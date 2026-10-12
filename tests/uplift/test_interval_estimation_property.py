"""
Feature: decision-quality-proof, Property 60: The interval is estimated at 1 - alpha, brackets
the point estimate and is order-invariant.

Task 15.3, for the estimator task 15.2 landed early. Subject: ``uplift/interval.py``
(R6.13, R7.14). Design section **E3.1**.

**Why this property landed before its session.** ``uplift.regret.classify_regret`` reaches
``material`` -- the verdict that falsifies Finding 4 and stops this spec -- on ``regret >=
margin`` alone when no interval is supplied. Checkpoint A is the run that decides. So the
estimator came forward out of session 3, and this is the property that says it is an estimator
and not an arithmetic accident.

**The three declared clauses, each asserted rather than described.**

* *Estimated at ``1 - alpha``.* ``alpha`` is the Metric_Contract's committed ``0.05``, read
  from the artifact. The figure "95%" is ``1 - alpha`` and appears nowhere as a literal, here
  or in the subject. A separate deterministic test pins the narrow YAML read against
  ``uplift.contract.load_contract``'s validating one, because two readers of one artifact with
  nothing comparing them is the ``None == None`` shape C75 exists to close.
* *Brackets the point estimate.* Asserted unconditionally over the generated space, **not**
  wrapped in a tolerated-exception disjunct. The percentile bootstrap of a mean does not
  guarantee bracketing as a theorem, so if a generator ever finds a case that misses, that is a
  finding about the estimator and the repair is the subject -- never the assertion (R2.10). The
  refusal path is proven separately, by constructing an inadmissible ``Interval`` directly.
* *Order-invariant.* Under any permutation of the replicate-aligned pairs, for a fixed seed,
  the result is identical field for field. **This is the clause that found a design defect:**
  E3.1 said sorting the resample *statistics* delivers it, and it does not -- the seeded index
  stream is fixed, so permuting the inputs changes which values each resample draws. Sorting
  the statistics makes the percentile well defined; input-order invariance needs the paired
  *differences* sorted before resampling. The subject does both.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file.**

Locus: ``ci.yml::uplift-verify`` fast step. **Not** slow-marked: pure arithmetic over stdlib
``random``, with no twin, no subprocess and no network.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from uplift.interval import (
    INTERVAL_SEED,
    METHOD,
    TAIL_ORDER_STATISTICS,
    Interval,
    IntervalUnavailableError,
    contract_alpha,
    headline_interval,
    paired_difference_interval,
    resamples_for,
)
from uplift.regret import OBJECTIVE_TERMS, InsensitiveKpi, RegretObjective, classify_regret

# ---------------------------------------------------------------------------
# Strategies and scales
# ---------------------------------------------------------------------------

#: Resample count used by the PROPERTIES, and deliberately not the committed one. The clauses
#: below are about the estimator's structure -- bracketing, order-invariance, purity, tail
#: monotonicity -- none of which is a function of how many resamples are drawn. Drawing the
#: production 2000 for every generated example would spend the fast step's wall clock on
#: re-confirming the same structure. The committed count is pinned by its own test, from the
#: committed alpha, which is where that number belongs.
_RESAMPLES = 128

_COSTS = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)

#: Two replicate-aligned cost samples of equal length. Short on purpose: a paired bootstrap's
#: interesting behaviour is at small n, where the resample distribution is coarse.
_PAIRS = st.integers(min_value=1, max_value=8).flatmap(
    lambda n: st.tuples(
        st.lists(_COSTS, min_size=n, max_size=n),
        st.lists(_COSTS, min_size=n, max_size=n),
    )
)

#: Significance levels away from the endpoints, where `1 - alpha` names a real level.
_ALPHAS = st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False)


def _objective(*, insensitive: tuple[str, ...] = ()) -> RegretObjective:
    """A hand-built objective, so composition is tested independently of the real policy file."""
    return RegretObjective(
        weights=dict.fromkeys(OBJECTIVE_TERMS, 1.0),
        on_hand_normaliser=1000.0,
        delivery_normaliser=27.5,
        aggregation="mean_paired_on_seed",
        sensitivity={term: term not in insensitive for term in OBJECTIVE_TERMS},
        insensitive=tuple(
            InsensitiveKpi(term=term, blocked_on="fixture") for term in insensitive
        ),
    )


# ---------------------------------------------------------------------------
# Clause 1 -- estimated at 1 - alpha, from the committed contract
# ---------------------------------------------------------------------------


def test_the_committed_alpha_is_the_one_the_validating_contract_reader_reports() -> None:
    """The narrow YAML read and ``MetricContract`` must agree, mechanically.

    ``uplift/interval.py`` reads ``alpha`` with ``yaml`` rather than through
    :func:`uplift.contract.load_contract`, because ``contract.py`` imports ``scipy`` at module
    scope and ``scipy`` is not in ``uplift.yml::twin-regret``'s install closure -- so the
    validating reader cannot be imported inside the job that runs the regret measurement. This
    test is the price of that, and it is the whole anti-drift mechanism: two readers of one
    artifact with nothing comparing them is exactly the hole C75 was written to close.

    It runs here rather than in the twin-regret job because ``scipy`` IS present in
    ``ci.yml::uplift-verify``'s closure, which is the point.
    """
    from uplift.contract import load_contract

    assert contract_alpha() == load_contract().alpha


@given(pair=_PAIRS)
def test_the_interval_records_the_confidence_level_it_was_estimated_at(
    pair: tuple[list[float], list[float]]
) -> None:
    """``alpha`` is carried on the record, so ``1 - alpha`` is derivable and never a literal."""
    first, second = pair
    alpha = contract_alpha()
    interval = paired_difference_interval(
        first, second, alpha=alpha, resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    assert interval.alpha == alpha
    assert interval.resamples == _RESAMPLES
    assert interval.seed == INTERVAL_SEED
    assert interval.method == METHOD
    # The rendered level is computed from the recorded alpha, not transcribed beside it.
    assert f"{(1.0 - alpha) * 100.0:.6g}%" in interval.describe()


def test_the_resample_count_is_derived_from_the_committed_alpha() -> None:
    """The production count follows from ``alpha`` plus one flagged choice, not from a literal.

    At the committed ``alpha = 0.05`` and ``TAIL_ORDER_STATISTICS = 50`` the derivation gives
    2000. The assertion is stated as the derivation rather than as ``== 2000`` so that changing
    the contract's alpha moves the count instead of failing this test with an arithmetic
    complaint about a number nobody can locate.
    """
    alpha = contract_alpha()
    assert resamples_for(alpha) == math.ceil(TAIL_ORDER_STATISTICS / (alpha / 2.0))


@given(alpha=_ALPHAS)
def test_every_derived_resample_count_leaves_the_declared_tail_populated(alpha: float) -> None:
    """Each tail bound is at least the declared order statistic in from the extreme draw."""
    resamples = resamples_for(alpha)
    assert resamples >= 1
    assert resamples * (alpha / 2.0) >= TAIL_ORDER_STATISTICS - 1e-9


# ---------------------------------------------------------------------------
# Clause 2 -- brackets the point estimate
# ---------------------------------------------------------------------------


@given(pair=_PAIRS)
def test_the_interval_brackets_the_point_estimate(
    pair: tuple[list[float], list[float]]
) -> None:
    """``low <= point <= high``, and the point is the mean paired difference.

    Asserted with no tolerated-exception escape: a generated case that misses is a finding
    about the estimator, and the repair is the subject, not this line (R2.10).
    """
    first, second = pair
    interval = paired_difference_interval(
        first, second, alpha=contract_alpha(), resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    assert interval.low <= interval.point <= interval.high
    assert interval.width >= 0.0
    expected = sum(a - b for a, b in zip(first, second, strict=True)) / len(first)
    assert math.isclose(interval.point, expected, rel_tol=1e-9, abs_tol=1e-12)


@given(pair=_PAIRS, shift=_COSTS)
def test_a_shift_applied_to_both_arms_leaves_the_interval_unchanged(
    pair: tuple[list[float], list[float]], shift: float
) -> None:
    """The estimator sees only the paired differences, which a common shift does not move.

    This is what "paired" means operationally, and it is the reason the estimator is the right
    one for both call sites: regret and headline uplift are each a mean paired difference, so
    neither carries the level of the two arms into its precision.
    """
    first, second = pair
    baseline = paired_difference_interval(
        first, second, alpha=contract_alpha(), resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    shifted = paired_difference_interval(
        [value + shift for value in first],
        [value + shift for value in second],
        alpha=contract_alpha(),
        resamples=_RESAMPLES,
        seed=INTERVAL_SEED,
    )
    assert math.isclose(shifted.point, baseline.point, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(shifted.low, baseline.low, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(shifted.high, baseline.high, rel_tol=1e-9, abs_tol=1e-9)


@given(value=_COSTS, count=st.integers(min_value=1, max_value=8))
def test_a_degenerate_sample_yields_a_degenerate_interval_not_a_refusal(
    value: float, count: int
) -> None:
    """Every difference identical means zero dispersion, and zero width is the honest report.

    A degenerate interval is a real answer -- the data carried no variance -- and collapsing it
    to a refusal would make a deterministic measurement indistinguishable from a failed one.

    **Two different comparisons, and the difference is the point.** The three bounds must agree
    *exactly*, because they are the identical computation over the identical multiset, and any
    drift between them would be a real defect. The point's agreement with ``value`` is a
    *closeness* test, because ``fmean`` of ``count`` copies of ``value`` sums and divides, and
    ``(count * value) / count`` is not bit-identical to ``value`` at every magnitude. This was a
    genuine finding rather than a guess: the exact form passed at ``HYPOTHESIS_PROFILE=dev`` and
    failed at ``heavy`` on ``value=4.413920275115946e-253, count=5``, one ulp apart. **The
    precondition was corrected, not the assertion weakened** -- the substantive claims (zero
    width, bounds identical, point equal to the common difference) all still hold, and the
    subject was not touched (R2.10).
    """
    interval = paired_difference_interval(
        [value] * count,
        [0.0] * count,
        alpha=contract_alpha(),
        resamples=_RESAMPLES,
        seed=INTERVAL_SEED,
    )
    assert interval.low == interval.high == interval.point
    assert interval.width == 0.0
    assert math.isclose(interval.point, value, rel_tol=1e-12, abs_tol=0.0)


# ---------------------------------------------------------------------------
# Clause 3 -- order-invariance for a fixed seed
# ---------------------------------------------------------------------------


@given(pair=_PAIRS, data=st.data())
def test_the_interval_is_invariant_to_input_order_for_a_fixed_seed(
    pair: tuple[list[float], list[float]], data: st.DataObject
) -> None:
    """Permuting the replicate-aligned pairs changes nothing, field for field.

    The permutation is applied to the PAIRS, not to either arm alone: permuting one arm would
    re-pair the replicates and is a different measurement, not a reordering of this one.
    """
    first, second = pair
    order = data.draw(st.permutations(range(len(first))))
    alpha = contract_alpha()
    baseline = paired_difference_interval(
        first, second, alpha=alpha, resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    permuted = paired_difference_interval(
        [first[i] for i in order],
        [second[i] for i in order],
        alpha=alpha,
        resamples=_RESAMPLES,
        seed=INTERVAL_SEED,
    )
    assert permuted == baseline


@given(pair=_PAIRS)
def test_the_interval_is_a_pure_function_of_its_declared_inputs(
    pair: tuple[list[float], list[float]]
) -> None:
    """Two calls with the same declared inputs agree exactly, so the interval replays."""
    first, second = pair
    alpha = contract_alpha()
    once = paired_difference_interval(
        first, second, alpha=alpha, resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    twice = paired_difference_interval(
        first, second, alpha=alpha, resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    assert once == twice
    # E3.1's declared entry point is an alias, not a second estimator.
    assert (
        headline_interval(first, second, alpha=alpha, resamples=_RESAMPLES, seed=INTERVAL_SEED)
        == once
    )


# ---------------------------------------------------------------------------
# Monotonicity in the confidence level
# ---------------------------------------------------------------------------


@given(pair=_PAIRS, wide=_ALPHAS, narrow=_ALPHAS)
def test_a_higher_confidence_level_is_never_a_narrower_interval(
    pair: tuple[list[float], list[float]], wide: float, narrow: float
) -> None:
    """A smaller ``alpha`` (higher confidence) never yields a tighter interval.

    ``resamples`` is held fixed across the two calls deliberately: the production count is
    derived FROM alpha, so letting it move would compare two different resample sets and the
    comparison would be about sampling noise rather than about the percentile rule.
    """
    assume(narrow < wide)
    first, second = pair
    tighter_level = paired_difference_interval(
        first, second, alpha=wide, resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    higher_confidence = paired_difference_interval(
        first, second, alpha=narrow, resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    assert higher_confidence.low <= tighter_level.low
    assert higher_confidence.high >= tighter_level.high
    assert higher_confidence.width >= tighter_level.width


# ---------------------------------------------------------------------------
# Exclusion is strict at both endpoints -- the R5.13 clause
# ---------------------------------------------------------------------------


@given(pair=_PAIRS)
def test_exclusion_is_strict_so_an_endpoint_on_the_margin_excludes_nothing(
    pair: tuple[list[float], list[float]]
) -> None:
    """A closed interval whose endpoint sits ON a value CONTAINS it (R5.13).

    This is the clause session 1r found the hard way: a property built its "excluding" interval
    from an absolute width and asserted ``material`` for an interval that touched the margin.
    ``classify_regret`` was right to refuse it, because ``low > margin`` is strict.
    """
    first, second = pair
    interval = paired_difference_interval(
        first, second, alpha=contract_alpha(), resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    assert not interval.excludes(interval.low)
    assert not interval.excludes(interval.high)
    assert not interval.excludes(interval.point)
    if interval.width > 0.0:
        assert interval.excludes(math.nextafter(interval.low, -math.inf))
        assert interval.excludes(math.nextafter(interval.high, math.inf))


@given(pair=_PAIRS, insensitive=st.booleans())
def test_a_regret_whose_interval_contains_the_margin_is_never_material(
    pair: tuple[list[float], list[float]], insensitive: bool
) -> None:
    """Composition with the verdict: the point may reach the margin; the interval decides.

    This is the whole reason the estimator came forward. ``material`` falsifies Finding 4 and
    stops the spec, and with an interval supplied it can only be reached when the interval
    excludes the margin -- which is what ``RegretVerdict``'s docstring and
    ``SESSION_PROTOCOL.md``'s checkpoint-A table have always claimed.
    """
    first, second = pair
    interval = paired_difference_interval(
        first, second, alpha=contract_alpha(), resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    # A margin the interval contains, chosen at the point estimate itself. Skip the degenerate
    # case where a zero-width interval sits exactly on it: there the margin is the point and a
    # non-positive margin is refused by the policy reader anyway.
    assume(interval.low < interval.high)
    margin = interval.point
    objective = _objective(insensitive=("spoilage_rate",) if insensitive else ())
    verdict = classify_regret(
        interval.point, objective=objective, margin=margin, interval=interval.bounds
    )
    assert verdict.verdict != "material"
    assert not verdict.falsifies_finding_4
    assert verdict.verdict == ("inconclusive" if insensitive else "sub-margin")


# ---------------------------------------------------------------------------
# Refusals -- an inadmissible interval is never substituted with a bound
# ---------------------------------------------------------------------------


@given(pair=_PAIRS, extra=st.lists(_COSTS, min_size=1, max_size=3))
def test_unpaired_samples_are_refused_rather_than_truncated(
    pair: tuple[list[float], list[float]], extra: list[float]
) -> None:
    """An unpaired difference is a different estimator with a different variance."""
    first, second = pair
    with pytest.raises(IntervalUnavailableError, match="equal sample counts"):
        paired_difference_interval(
            first,
            second + extra,
            alpha=contract_alpha(),
            resamples=_RESAMPLES,
            seed=INTERVAL_SEED,
        )


def test_an_empty_sample_is_refused() -> None:
    """Nothing measured is not a wide interval; it is no interval."""
    with pytest.raises(IntervalUnavailableError, match="at least one replicate"):
        paired_difference_interval(
            [], [], alpha=contract_alpha(), resamples=_RESAMPLES, seed=INTERVAL_SEED
        )


@given(alpha=st.sampled_from([0.0, 1.0, -0.1, 1.5, math.inf, math.nan]))
def test_an_alpha_outside_the_open_unit_interval_is_refused(alpha: float) -> None:
    """Outside ``(0, 1)``, ``1 - alpha`` names no confidence level."""
    with pytest.raises(IntervalUnavailableError):
        paired_difference_interval(
            [1.0], [0.0], alpha=alpha, resamples=_RESAMPLES, seed=INTERVAL_SEED
        )
    with pytest.raises(IntervalUnavailableError):
        resamples_for(alpha)


@given(resamples=st.integers(min_value=-5, max_value=0))
def test_a_non_positive_resample_count_is_refused(resamples: int) -> None:
    """Zero resamples estimate nothing, so no bound is produced from them."""
    with pytest.raises(IntervalUnavailableError):
        paired_difference_interval(
            [1.0], [0.0], alpha=contract_alpha(), resamples=resamples, seed=INTERVAL_SEED
        )


@given(value=st.sampled_from([math.inf, -math.inf, math.nan]))
def test_a_non_finite_difference_is_refused(value: float) -> None:
    """A replicate that produced a non-finite cost is a failed run, not a wide bound."""
    with pytest.raises(IntervalUnavailableError):
        paired_difference_interval(
            [value, 1.0],
            [0.0, 0.0],
            alpha=contract_alpha(),
            resamples=_RESAMPLES,
            seed=INTERVAL_SEED,
        )


def test_an_interval_that_does_not_bracket_its_point_is_refused_not_widened() -> None:
    """The bracketing claim is enforced at construction, and enforced by refusing.

    This is the path the property above asserts is never reached by the estimator. Proven here
    directly, because "no generated example triggered it" is not evidence that the guard works
    -- and a guard that silently widened the bound instead would make the bracketing claim
    unfalsifiable (I-7).
    """
    with pytest.raises(IntervalUnavailableError, match="does not bracket"):
        Interval(
            method=METHOD, alpha=0.05, resamples=10, seed=0, low=0.0, high=1.0, point=2.0
        )


def test_inverted_non_finite_and_countless_intervals_are_refused() -> None:
    """The remaining three construction guards, each named in its own message."""
    with pytest.raises(IntervalUnavailableError, match="inverted"):
        Interval(method=METHOD, alpha=0.05, resamples=10, seed=0, low=1.0, high=0.0, point=0.5)
    with pytest.raises(IntervalUnavailableError, match="not finite"):
        Interval(
            method=METHOD,
            alpha=0.05,
            resamples=10,
            seed=0,
            low=-math.inf,
            high=1.0,
            point=0.5,
        )
    with pytest.raises(IntervalUnavailableError, match="resamples"):
        Interval(method=METHOD, alpha=0.05, resamples=0, seed=0, low=0.0, high=1.0, point=0.5)


def test_the_seven_recorded_fields_are_exactly_the_artifact_intervals_declared_fields() -> None:
    """``as_dict`` is what task 15.1's ``ArtifactInterval`` is constructed from.

    Pinned by name here so the two forms cannot drift while 15.1 is still open. The computation
    form and the serialisation form are deliberately separate -- see the class docstring for why
    ``interval.py`` must not import ``harness.py`` -- and this is what keeps that split honest
    rather than a fork.
    """
    interval = paired_difference_interval(
        [2.0, 3.0], [1.0, 1.0], alpha=contract_alpha(), resamples=_RESAMPLES, seed=INTERVAL_SEED
    )
    assert set(interval.as_dict()) == {
        "method",
        "alpha",
        "resamples",
        "seed",
        "low",
        "high",
        "point",
    }
