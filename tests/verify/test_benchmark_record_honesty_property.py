# Feature: decision-quality-proof, Property 73: An unconfirmed external value is never rendered as
# fact, and a differing definition is not comparable
"""Property 73 -- an unconfirmed external value is never rendered as fact, and a differing
definition is not comparable.

Feature: decision-quality-proof, task 19.8. Requirements **R8.5**, **R8.6**, **R8.7**, **R8.8**,
**R8.12**, **R8.13**, **R8.15**, **R8.18**.

Two claims, and the second is what keeps the first from being vacuous
--------------------------------------------------------------------

R8.8's obligation is negative -- an unconfirmed value must not appear as fact -- and a negative
claim is satisfied perfectly by a renderer that prints nothing at all. So every negative
assertion here is paired with a **positive** one over the same machinery: the renderer *does*
print a confirmed number, with its source and read date, and the assertion is that it does not
print one for an unconfirmed entry. A renderer that had simply been switched off would fail the
positive half and never reach the negative.

What each property would have to do to fail
-------------------------------------------

1. :func:`test_an_unconfirmed_baseline_cannot_carry_a_value_at_all` fails if
   ``UnconfirmedBaseline`` accepts a number. R8.6 asks the record to carry the baseline and R8.8
   forbids an unconfirmed one being asserted as fact; a bare ``baseline: 0.16`` satisfies the
   first while violating the second, so the *type* is where the two are reconciled. This is the
   property that makes "the schema admits no bare number" a mechanism instead of a comment.

2. :func:`test_the_rendered_region_states_a_confirmed_number_and_never_an_unconfirmed_one` fails
   in either direction: if a confirmed value is missing from the document, or if any trace of a
   value appears for an unconfirmed one. The two renderings come from the same record differing
   *only* in its baseline, so the comparison isolates the baseline's contribution.

3. :func:`test_a_differing_definition_is_not_comparable_and_carries_no_rank` fails if any
   non-empty difference set can coexist with ``leaderboard-comparable``, or if a rank survives
   on a non-comparable record. R8.18: a rank against a differently-defined quantity is a
   category error dressed as a measurement, and the two admissible shapes are exactly
   (comparable, no differences) and (not-comparable, at least one named difference, no rank).

4. :func:`test_an_unexplained_incomparability_is_refused` fails if
   ``not-leaderboard-comparable`` can be declared without naming a difference. An unexplained
   incomparability is indistinguishable from an excuse, which is the shape that would let this
   clause be used to duck every comparison.

5. :func:`test_zero_cost_is_derived_from_three_exclusions_and_never_read` fails if the record's
   own ``declared_zero_cost`` flag can move the verdict, or if any single unmet exclusion still
   reads as zero cost. R8.15's reason is that "free" without those exclusions admits a paid
   tier, so the eight combinations are quantified over rather than sampled.

6. :func:`test_the_domain_gap_cannot_be_declared_absent_or_non_distinct` fails if a record can
   omit the domain-gap statement or declare the two domains non-distinct (R8.12, R8.13).

7. :func:`test_an_unconfirmed_baseline_is_never_a_pass_and_never_fatal` fails if the gate reports
   an unconfirmed baseline as passing (I-7: absence of proof is never a pass) **or** as somebody's
   defect. It is neither: nobody wrote a wrong number, and the repair belongs to a human with a
   browser rather than to the change that introduced the record.

Budget and locus
----------------

``max_examples`` is **inherited from the root** ``conftest.py`` profile and appears nowhere in
this file (I-0's authoring rule). Locus: ``ci.yml::uplift-verify`` fast step. Every property is a
pure function of its arguments -- no file IO, no git, no clock, no network -- so the whole file
costs a handful of core-seconds even at the 500-example budget.

**Validates: Requirements 8.5, 8.6, 8.7, 8.8, 8.12, 8.13, 8.15, 8.18.**
"""

from __future__ import annotations

from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from scripts.audit import benchmark_gen
from scripts.audit.benchmark_truth import (
    BenchmarkRecord,
    Comparability,
    ConfirmedBaseline,
    DomainGap,
    ExecutionEnvironment,
    MetricIdentity,
    UnconfirmedBaseline,
    evaluate_record,
)

#: A complete metric identity. Fictional but well-formed: these properties are about the
#: baseline and the comparability, and an incomplete identity here would make every one of them
#: also measure the identity rule.
METRIC: Final[MetricIdentity] = MetricIdentity(
    metric_id="fixture-metric",
    metric_name="Fixture Scaled Pinball Loss",
    defining_document_id="fixture-document",
    defining_document_uri="https://example.invalid/fixture/evaluation",
    defining_document_confirmed=False,
    provenance="fixture: this identity describes no real metric",
    split_id="fixture-split",
    aggregation_level="fixture-level",
    quantile_levels=(0.1, 0.5, 0.9),
)

GAP: Final[DomainGap] = DomainGap(
    feed_domain="fixture daily domain",
    system_domain="fixture sub-hourly domain",
    distinct_domains=True,
    statement="fixture: the two are distinct domains",
    evidence="fixture: the finer grain is not recoverable from the coarser one",
)

UNCONFIRMED: Final[UnconfirmedBaseline] = UnconfirmedBaseline(
    status="unconfirmed",
    blocked_on="fixture: nobody has read the published document",
    procedure="fixture: read it and record the value with its source",
    limitation="fixture: the published value could not be confirmed at implementation time",
)

#: Values a renderer might be tempted to print. Bounded and finite, and deliberately including
#: integral floats: ``0.0`` is the value a defaulting bug would produce, and a property that
#: never drew it would miss the most likely failure.
_values = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False, width=32
)
_differences = st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz -", min_size=1, max_size=40),
    min_size=1,
    max_size=4,
)
_ranks = st.integers(min_value=1, max_value=500)
_flags = st.booleans()


def _confirmed(value: float) -> ConfirmedBaseline:
    """A confirmed baseline carrying ``value`` with the provenance R8.6 requires."""
    return ConfirmedBaseline(
        status="confirmed",
        value=value,
        source_uri="https://example.invalid/fixture/leaderboard",
        source_title="Fixture leaderboard",
        read_date="2026-09-01",
        read_by="fixture-operator",
    )


def _record(
    baseline: ConfirmedBaseline | UnconfirmedBaseline,
    comparability: Comparability,
    *,
    score: float | None = None,
) -> BenchmarkRecord:
    """A record differing from its siblings only in the fields under test."""
    return BenchmarkRecord(
        score=score,
        score_absent_reason=None if score is not None else "fixture: no run has executed",
        metric=METRIC,
        baseline=baseline,
        comparability=comparability,
        domain_gap=GAP,
        direction="lower-is-better",
    )


_INCOMPARABLE: Final[Comparability] = Comparability(
    status="not-leaderboard-comparable",
    differences=("fixture: the metric definition differs",),
    rank=None,
)


# ---------------------------------------------------------------------------
# 1. The type is the mechanism (R8.6, R8.8)
# ---------------------------------------------------------------------------


@given(value=_values)
def test_an_unconfirmed_baseline_cannot_carry_a_value_at_all(value: float) -> None:
    """``UnconfirmedBaseline`` refuses a number, so R8.8 holds before any renderer runs.

    ``value`` is typed ``None``, not ``float | None``. An unconfirmed entry is not a confirmed
    entry with a field missing -- it is a different fact -- and this is the assertion that stops
    the two being one shape with a flag. Note the complement asserted below: a **confirmed**
    entry accepts the very same number, so the refusal is about the entry's status rather than
    about the value being unacceptable.
    """
    with pytest.raises(ValidationError):
        # Validated from a mapping rather than constructed with keywords, so the refusal is
        # exercised on the path a committed artifact actually takes - and so this assertion
        # needs no `# type: ignore`, which this project forbids.
        UnconfirmedBaseline.model_validate(
            {
                "status": "unconfirmed",
                "value": value,  # the subject of this test
                "blocked_on": "fixture",
                "procedure": "fixture",
                "limitation": "fixture",
            }
        )

    accepted = _confirmed(value)
    assert accepted.value == value
    assert accepted.renderable_value == value
    assert UNCONFIRMED.renderable_value is None
    assert accepted.confirmed is True
    assert UNCONFIRMED.confirmed is False


# ---------------------------------------------------------------------------
# 2. Rendering: the positive half is what keeps the negative half honest (R8.8)
# ---------------------------------------------------------------------------


@given(value=_values)
def test_the_rendered_region_states_a_confirmed_number_and_never_an_unconfirmed_one(
    value: float,
) -> None:
    """A confirmed value reaches the document; an unconfirmed one leaves no trace of a number.

    Both directions over the same renderer and two records that differ **only** in their
    baseline, so nothing else can account for the difference. The positive half is not decoration:
    without it a renderer that printed no baseline at all would satisfy R8.8 while making the
    document useless, and the negative assertion would prove nothing.
    """
    confirmed_region = benchmark_gen.render_region(
        _record(_confirmed(value), _INCOMPARABLE), "fixture"
    )
    unconfirmed_region = benchmark_gen.render_region(
        _record(UNCONFIRMED, _INCOMPARABLE), "fixture"
    )

    # Positive: the machinery can and does publish a confirmed number with its provenance.
    assert str(value) in confirmed_region
    assert "**Value:**" in confirmed_region
    assert "https://example.invalid/fixture/leaderboard" in confirmed_region
    assert "2026-09-01" in confirmed_region

    # Negative: none of that appears for an unconfirmed entry, and the limitation does.
    assert benchmark_gen.UNCONFIRMED_RENDERING in unconfirmed_region
    assert "**Value:**" not in unconfirmed_region
    assert "explicitly unconfirmed" in unconfirmed_region
    assert UNCONFIRMED.limitation in unconfirmed_region
    assert UNCONFIRMED.blocked_on in unconfirmed_region

    # Idempotence, which is what `--check` relies on: the same record renders byte-identically.
    assert benchmark_gen.render_region(
        _record(UNCONFIRMED, _INCOMPARABLE), "fixture"
    ) == unconfirmed_region


@given(score=_values)
def test_an_unmeasured_score_is_rendered_as_words_and_never_as_a_number(score: float) -> None:
    """A record with no score renders prose; one with a score renders the score.

    The same paired construction as the baseline property, for the same reason. ``0.0`` is
    drawable, and a renderer that coerced ``None`` to a number would most plausibly produce
    exactly that -- which would read to every later reader as a perfect score on a
    lower-is-better metric.
    """
    scored = benchmark_gen.render_region(
        _record(UNCONFIRMED, _INCOMPARABLE, score=score), "fixture"
    )
    unscored = benchmark_gen.render_region(_record(UNCONFIRMED, _INCOMPARABLE), "fixture")

    assert str(score) in scored
    assert benchmark_gen.UNSCORED_RENDERING not in scored
    assert benchmark_gen.UNSCORED_RENDERING in unscored
    assert "fixture: no run has executed" in unscored


# ---------------------------------------------------------------------------
# 3. R8.18: a differing definition is not comparable, and carries no rank
# ---------------------------------------------------------------------------


@given(differences=_differences, rank=_ranks)
def test_a_differing_definition_is_not_comparable_and_carries_no_rank(
    differences: list[str], rank: int
) -> None:
    """Named differences forbid both ``leaderboard-comparable`` and a rank.

    Quantified over the difference set because R8.18 names three independent sources of
    incomparability -- split, aggregation level, metric definition -- and a rule that held for
    one string and not another would be a rule about strings. The admissible pair is asserted at
    the end so the refusals are shown to be discriminating rather than total: a genuinely
    comparable record with no differences is accepted, and only then may it carry a rank.
    """
    with pytest.raises(ValidationError):
        Comparability(status="leaderboard-comparable", differences=tuple(differences))

    with pytest.raises(ValidationError):
        Comparability(
            status="not-leaderboard-comparable",
            differences=tuple(differences),
            rank=rank,
        )

    incomparable = Comparability(
        status="not-leaderboard-comparable", differences=tuple(differences)
    )
    assert incomparable.rank is None
    assert incomparable.comparable is False
    assert set(incomparable.differences) == set(differences), "each difference is NAMED"

    comparable = Comparability(status="leaderboard-comparable", differences=(), rank=rank)
    assert comparable.comparable is True
    assert comparable.rank == rank


@given(rank=st.one_of(st.none(), _ranks))
def test_an_unexplained_incomparability_is_refused(rank: int | None) -> None:
    """``not-leaderboard-comparable`` with no named difference is refused.

    Without this clause R8.18 becomes an exit from every comparison: declare incomparability,
    name nothing, and no reader can check the claim. An unexplained incomparability is
    indistinguishable from an excuse.
    """
    with pytest.raises(ValidationError):
        Comparability(status="not-leaderboard-comparable", differences=(), rank=rank)


@given(differences=_differences)
def test_comparability_claimed_over_an_unconfirmed_baseline_is_a_defect(
    differences: list[str],
) -> None:
    """Claiming comparability to a value nobody has read is somebody's defect, not an absence.

    The two verdicts are asserted apart because they carry different repairs. An unconfirmed
    baseline is work for a human with a browser (``unavailable``); asserting comparability to it
    is a false statement written in this tree (``fail``), fixable in the change that wrote it.
    """
    overclaimed = evaluate_record(
        _record(UNCONFIRMED, Comparability(status="leaderboard-comparable", differences=())),
        "fixture",
    )
    honest = evaluate_record(
        _record(
            UNCONFIRMED,
            Comparability(
                status="not-leaderboard-comparable", differences=tuple(differences)
            ),
        ),
        "fixture",
    )

    assert any(item.rule == "comparability-overclaimed" for item in overclaimed)
    assert any(item.fatal for item in overclaimed)
    assert not any(item.rule == "comparability-overclaimed" for item in honest)
    assert not any(item.fatal for item in honest), (
        "an incomparable result with an unconfirmed baseline is the honest state; failing it "
        "would make honesty the red option"
    )


# ---------------------------------------------------------------------------
# 4. R8.15: three exclusions, derived, never read
# ---------------------------------------------------------------------------


@given(billable=_flags, trial=_flags, granted_credits=_flags, declared=_flags)
def test_zero_cost_is_derived_from_three_exclusions_and_never_read(
    billable: bool, trial: bool, granted_credits: bool, declared: bool
) -> None:
    """``zero_cost`` is a function of the three exclusions alone; the flag cannot move it.

    All sixteen combinations, because R8.15's reason is that "free" without these exclusions
    admits a paid tier and a rule verified on one combination is not a rule. Two things are
    asserted: the derivation ignores ``declared_zero_cost`` entirely, and the disagreement is
    **asymmetric** -- over-claiming is a false self-statement, while under-claiming is an
    operator being cautious about somebody else's billing terms and is not a defect.
    """
    environment = ExecutionEnvironment(
        environment_id="fixture",
        locus="ci-pipeline",
        detail="fixture",
        billable_account_required=billable,
        trial_linked_to_billing_required=trial,
        purchased_or_granted_credits_used=granted_credits,
        declared_zero_cost=declared,
        cost_basis="fixture",
        new_dependencies=(),
        dependency_basis="fixture",
    )

    expected = not (billable or trial or granted_credits)
    assert environment.zero_cost is expected
    assert bool(environment.unmet_exclusions) is (not expected)
    assert environment.flag_disagrees() is (declared and not expected)

    # Each unmet exclusion is NAMED, so a reader is told which term to go and check.
    if billable:
        assert "billable_account_required" in environment.unmet_exclusions
    if trial:
        assert "trial_linked_to_billing_required" in environment.unmet_exclusions
    if granted_credits:
        assert "purchased_or_granted_credits_used" in environment.unmet_exclusions

    # The derivation does not consult the flag: the same three facts under the opposite flag
    # yield the same verdict. This is what "derived, never read" means, asserted rather than
    # described.
    flipped = environment.model_copy(update={"declared_zero_cost": not declared})
    assert flipped.zero_cost is environment.zero_cost
    assert flipped.unmet_exclusions == environment.unmet_exclusions


# ---------------------------------------------------------------------------
# 5. R8.12, R8.13: the domain gap is not optional
# ---------------------------------------------------------------------------


@given(statement=st.sampled_from(("", "   ", "\n")), evidence=st.text(max_size=8))
def test_the_domain_gap_cannot_be_declared_absent_or_non_distinct(
    statement: str, evidence: str
) -> None:
    """A blank statement, a blank evidence, or non-distinct domains are each refused.

    R8.12 requires the gap to accompany every feed-derived claim and R8.13 requires the two to
    be described as distinct. Both are enforced at construction, so a record that omitted them
    could not exist to be rendered -- which is what makes the generated document's compliance
    structural rather than a habit.
    """
    with pytest.raises(ValidationError):
        DomainGap(
            feed_domain="a",
            system_domain="b",
            distinct_domains=True,
            statement=statement,  # the subject of this test
            evidence=evidence or "fixture",
        )

    with pytest.raises(ValidationError):
        DomainGap(
            feed_domain="a",
            system_domain="b",
            distinct_domains=False,  # the subject of this test
            statement="fixture",
            evidence="fixture",
        )

    accepted = DomainGap(
        feed_domain="a",
        system_domain="b",
        distinct_domains=True,
        statement="fixture",
        evidence="fixture",
    )
    assert accepted.distinct_domains is True


# ---------------------------------------------------------------------------
# 6. An unconfirmed baseline is non-passing and non-fatal (I-7, R8.7)
# ---------------------------------------------------------------------------


@given(differences=_differences)
def test_an_unconfirmed_baseline_is_never_a_pass_and_never_fatal(
    differences: list[str],
) -> None:
    """The gate reports an unconfirmed baseline, names why, and calls it neither pass nor defect.

    Three assertions, and the middle one is the one that would be quietly dropped: the finding
    must NAME what the confirmation is blocked on, so a reader learns what to do rather than
    that something is missing. The confirmed case is asserted alongside so the finding is shown
    to be about the baseline's status rather than always emitted.
    """
    comparability = Comparability(
        status="not-leaderboard-comparable", differences=tuple(differences)
    )

    unconfirmed = evaluate_record(_record(UNCONFIRMED, comparability), "fixture")
    confirmed = evaluate_record(_record(_confirmed(0.25), comparability), "fixture")

    named = [item for item in unconfirmed if item.rule == "baseline-unconfirmed"]
    assert named, "an unconfirmed baseline with no finding is one nobody was told about"
    assert all(item.verdict_contribution == "unavailable" for item in named)
    assert not any(item.fatal for item in named), (
        "nobody wrote a wrong number; the repair belongs to a human with a browser, so this is "
        "an absence rather than a defect (I-7)"
    )
    assert any(UNCONFIRMED.blocked_on in item.detail for item in named), (
        "the finding must name what the confirmation is blocked ON, or a reader learns that "
        "something is missing without learning what to do about it"
    )
    assert not [item for item in confirmed if item.rule == "baseline-unconfirmed"]
