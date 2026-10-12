"""Property-based test for the narrative-truth aggregate (design E1.3 / AD-3).

Feature: purpose-achievement-audit, Property 2: No claim can mask an unavailable
required claim

    *For any* set of narrative-truth claim results, the aggregate verdict is
    non-passing whenever any claim marked required is ``fail`` or ``skip``, and no
    number of ``ok`` sibling claims changes that verdict.

Why the property is shaped this way. The audit finding behind Requirement 1.4 / 1.6
is a specific removed defect: ``doc_truth.evaluate()`` returned ``ok`` as soon as
*any* claim was ``ok``, so the README-headline claim skipping - a 900s suite timeout,
an unparseable summary, the recursion guard firing - was absorbed by the unrelated
spec-threshold pin passing. Absence of proof was reported as proof (I-7). A single
example cannot pin that shut, because the defect's severity scales with the number of
``ok`` siblings: the fix is only credible if *no* count of them can flip the verdict.
So the property quantifies over the sibling count as well as over the claim set.

Subject: ``doc_truth.evaluate_claims``, the pure seam. ``evaluate()`` is deliberately
NOT driven here - it spawns the ``verify_claims`` suite with a 900s budget, which I-0
forbids on this machine. The aggregate reads no file and holds no process state, which
is what makes the verdict a total function of its argument and this test cheap.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 1.4, 1.6**
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import doc_truth
from scripts.audit.doc_truth import (
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_UNAVAILABLE,
    ClaimResult,
    DocProbe,
)
from tests.verify.strategies import (
    CLAIM_STATUSES,
    MaskingScenario,
    claim_result_multisets,
    claim_results,
    masking_scenarios,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The three aggregate verdicts, and the exit status each mandates. ``2`` is the
#: honest-degradation code: a required claim could not be evaluated (I-7).
EXPECTED_EXIT_CODES: Final[dict[str, int]] = {
    "ok": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}

#: Verdicts a CI step must not treat as success.
NON_PASSING: Final[tuple[str, ...]] = ("fail", "unavailable")


def expected_status(claims: Sequence[ClaimResult]) -> str:
    """The verdict the declared precedence mandates, recomputed independently.

    Design E1.3's rules, first match wins - written out here rather than imported from
    the gate, so the test compares two implementations instead of one:

    1. no claims at all                  -> ``unavailable`` (nothing was proven)
    2. any claim ``fail``                -> ``fail`` (R1.4: drift keeps exit 1)
    3. any REQUIRED claim ``skip``       -> ``unavailable`` (R1.6, non-maskable)
    4. no claim ``ok``                   -> ``unavailable`` (an all-skip run)
    5. otherwise                         -> ``ok``

    Note what rule 3 does *not* consult: the number of ``ok`` siblings. That absence
    is the whole property.
    """
    if not claims:
        return "unavailable"
    if any(claim.status == "fail" for claim in claims):
        return "fail"
    if any(claim.status == "skip" and claim.required for claim in claims):
        return "unavailable"
    if not any(claim.status == "ok" for claim in claims):
        return "unavailable"
    return "ok"


def assert_well_formed(probe: DocProbe, claims: tuple[ClaimResult, ...]) -> None:
    """Every invariant the aggregate owes regardless of which rule decided it."""
    # Total: exactly one of three verdicts, each mapping to its own exit status, and
    # only ``ok`` is passing - ``unavailable`` is an absence of proof, not a pass.
    assert probe.status in EXPECTED_EXIT_CODES
    assert probe.passing is (probe.status == "ok")
    assert (EXPECTED_EXIT_CODES[probe.status] == EXIT_PASS) is probe.passing

    # A function: no file read, no process state, so re-evaluating must agree.
    assert doc_truth.evaluate_claims(claims) == probe

    # The evidence travels with the verdict, unsummarised, in evaluation order.
    assert probe.claims == claims
    assert probe.detail


# Feature: purpose-achievement-audit, Property 2: No claim can mask an unavailable
# required claim
@given(scenario=masking_scenarios(blocking_statuses=("skip",)))
def test_no_number_of_ok_claims_masks_an_unresolved_required_claim(
    scenario: MaskingScenario,
) -> None:
    """R1.6: a required ``skip`` is non-maskable, at every sibling count.

    This is the removed defect stated as a property. The old aggregate would have
    returned ``ok`` for every example here with at least one ``ok`` sibling.
    """
    for count in range(len(scenario.ok_siblings) + 1):
        claims = scenario.with_ok(count)
        probe = doc_truth.evaluate_claims(claims)

        assert_well_formed(probe, claims)

        # The verdict is non-passing whatever the sibling count, and - because this
        # scenario carries no ``fail`` - it is specifically ``unavailable`` (exit 2).
        assert probe.status == "unavailable"
        assert probe.status in NON_PASSING
        assert not probe.passing
        assert EXPECTED_EXIT_CODES[probe.status] == EXIT_UNAVAILABLE

        # Agrees with the independently recomputed precedence.
        assert probe.status == expected_status(claims)

        # Every unresolved required claim is named, so a CI log says which claim was
        # not evaluated rather than only that something was not.
        for blocked in scenario.blocking:
            assert blocked.name in probe.detail
            assert blocked.detail in probe.detail


@given(scenario=masking_scenarios())
def test_a_required_claim_that_is_fail_or_skip_forces_a_non_passing_verdict(
    scenario: MaskingScenario,
) -> None:
    """R1.4, R1.6: both blocking clauses are non-passing, and drift stays exit 1."""
    claims = scenario.claims
    probe = doc_truth.evaluate_claims(claims)

    assert_well_formed(probe, claims)
    assert probe.status in NON_PASSING
    assert not probe.passing
    assert probe.status == expected_status(claims)

    if scenario.fails:
        # A proven falsehood is more actionable than an unknown, so drift wins the
        # precedence - but an unresolved required claim is still named in the same
        # detail (R1.4) rather than being dropped from the report.
        assert probe.status == "fail"
        assert EXPECTED_EXIT_CODES[probe.status] == EXIT_FAIL
        for failed in scenario.fails:
            assert failed.name in probe.detail
        for unresolved in scenario.required_unresolved:
            assert unresolved.name in probe.detail
    else:
        assert probe.status == "unavailable"


@given(claims=claim_result_multisets())
def test_the_aggregate_is_a_total_function_agreeing_with_the_precedence(
    claims: tuple[ClaimResult, ...],
) -> None:
    """R1.4, R1.6: every claim multiset - the empty one included - lands on one verdict."""
    probe = doc_truth.evaluate_claims(claims)

    assert_well_formed(probe, claims)
    assert probe.status == expected_status(claims)

    # The passing verdict is reachable only when nothing is unresolved-and-required,
    # nothing failed, and at least one claim was actually evaluated.
    if probe.passing:
        assert claims
        assert not any(claim.status == "fail" for claim in claims)
        assert not any(claim.status == "skip" and claim.required for claim in claims)
        assert any(claim.status == "ok" for claim in claims)


@given(oks=st.lists(claim_results(status="ok"), min_size=1, max_size=6).map(tuple))
def test_ok_claims_alone_still_reach_a_passing_verdict(
    oks: tuple[ClaimResult, ...],
) -> None:
    """The converse guard: the aggregate is not vacuously non-passing.

    Without this, every assertion above could hold for a gate that never passes, which
    would satisfy the letter of Property 2 and be useless as a gate.
    """
    probe = doc_truth.evaluate_claims(oks)

    assert_well_formed(probe, oks)
    assert probe.status == "ok"
    assert probe.passing
    assert EXPECTED_EXIT_CODES[probe.status] == EXIT_PASS


@given(
    optional_skips=st.lists(
        claim_results(status="skip", required=False), min_size=1, max_size=4
    ).map(tuple),
    oks=st.lists(claim_results(status="ok"), min_size=1, max_size=4).map(tuple),
)
def test_an_optional_skip_beside_an_ok_claim_does_not_block(
    optional_skips: tuple[ClaimResult, ...],
    oks: tuple[ClaimResult, ...],
) -> None:
    """``required`` is the discriminator: only a required skip is non-maskable (R1.6).

    A pin that is honestly optional must remain skippable, otherwise the fix for
    masking would have turned every unmeasurable claim into a merge blocker.
    """
    claims = (*optional_skips, *oks)
    probe = doc_truth.evaluate_claims(claims)

    assert_well_formed(probe, claims)
    assert probe.status == "ok"
    assert probe.passing

    # And flipping exactly one of those skips to required flips the verdict, so the
    # flag is load-bearing rather than decorative.
    promoted = (
        optional_skips[0].model_copy(update={"required": True}),
        *optional_skips[1:],
        *oks,
    )
    blocked = doc_truth.evaluate_claims(promoted)
    assert blocked.status == "unavailable"
    assert not blocked.passing


def test_the_claim_vocabulary_the_aggregate_partitions_is_the_claim_vocabulary() -> None:
    """The aggregate branches on exactly the statuses a claim can report.

    A fourth status would fall through to the ``ok`` branch, which is the failure mode
    this pins: the three buckets must exhaust the vocabulary.
    """
    assert set(CLAIM_STATUSES) == {"ok", "fail", "skip"}
    assert set(EXPECTED_EXIT_CODES) == {"ok", "fail", "unavailable"}
    assert doc_truth.evaluate_claims(()).status == "unavailable"
