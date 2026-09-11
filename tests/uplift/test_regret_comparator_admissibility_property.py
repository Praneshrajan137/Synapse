"""A negative regret is refused rather than classified: the oracle must bound the subject.

Feature: decision-quality-proof, Property 61: A negative regret is refused rather than
classified, because a comparator that loses to its own subject does not bound it.

Session 7, at checkpoint A. Subject: ``uplift/regret.py::negative_regret_refusal`` (R5.1, R5.3,
R5.35; ADR-055 D2.5.2).

**Why this property exists, measured rather than anticipated.** Run ``34570166681`` -- the first
measurement ever taken against the ``(s, S)`` reference arm -- reported
``regret = -0.8123524459522771`` with a 95% interval of ``[-0.8273, -0.7978]`` over 200 of 200
usable replicates. The interval excludes zero, so the sign is not noise. A negative regret means
the incumbent **outperforms** the arm labelled ``perfect_foresight``, so that arm is not an
oracle and their difference is not a regret.

**The hole this closes is not hypothetical, and clause 4 below proves it rather than asserting
it.** Handed to ``classify_regret`` today, that same number returns ``inconclusive`` -- which
reads as "regret below the margin" and would have been recorded as task 11's verdict. Once tasks
12.3 and 13.3 land the two E2c sensitivity flips, it returns ``sub-margin``, the **one** verdict
whose ``confirms_finding_4`` is true. Conflict M's defect forced ``material``, which stops the
spec loudly; this one would have **confirmed** the premise quietly. A false stop is recoverable;
a false confirmation is the outcome this spec exists to prevent (I-7).

**Why the sibling guard cannot catch it.** ``_measure`` already refuses a run in which
``headroom >= regret`` fails. Substituting the definitions makes that ``(A - C) >= (B - C)``,
which reduces to ``A >= B`` -- and is silent about ``C``, because ``C`` cancels. Clause 5 asserts
that reduction directly, so the reason this clause is separate is mechanical rather than prose.

**No ``DECLARED_INVENTORY`` entry is owed, and this was checked rather than assumed.**
``tests/verify/test_property_inventory_consistency.py``'s table covers properties 1-37; this
spec's own surface (44-54, 60) already sits outside it, which is conflict O's measured scope gap.
Adding an entry for 61 alone would imply the others were absent by oversight rather than by that
table's scope.

Budget inherited from the root ``conftest.py`` profile via ``HYPOTHESIS_PROFILE``. **No
``max_examples`` literal appears in this file** (CF-13).

Locus: ``ci.yml::uplift-verify`` fast step. **Not** slow-marked: every case here is pure
arithmetic over hand-built objectives, with no twin, no subprocess and no network.
"""

from __future__ import annotations

import math

from hypothesis import assume, given
from hypothesis import strategies as st

from uplift.regret import (
    OBJECTIVE_TERMS,
    InsensitiveKpi,
    RegretObjective,
    classify_regret,
    negative_regret_refusal,
)

#: The measured arm means from run 34570166681, kept as a regression pin on the FUNCTION rather
#: than on the world: repairing the comparator must not make this input admissible by accident.
MEASURED_REGRET = -0.8123524459522771
MEASURED_REFERENCE_COST = 2.0849871282327
MEASURED_FORESIGHT_COST = 2.897339574184977
MEASURED_NOOP_COST = 11.835228527152536
MEASURED_INTERVAL = (-0.8273245113311902, -0.7977944274457321)

#: The committed margin, instantiated at checkpoint A from the pre-registered rule.
COMMITTED_MARGIN = 0.40

_COSTS = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
_ANY_REGRET = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
_NEGATIVE = st.floats(min_value=-1e6, max_value=-1e-12, allow_nan=False, allow_infinity=False)
_NON_NEGATIVE = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)


def _objective(*, insensitive: tuple[str, ...] = ()) -> RegretObjective:
    """A hand-built objective, so the verdict logic is tested independently of the real file."""
    return RegretObjective(
        weights=dict.fromkeys(OBJECTIVE_TERMS, 1.0),
        on_hand_normaliser=1000.0,
        delivery_normaliser=27.5,
        aggregation="mean_paired_on_seed",
        sensitivity={term: term not in insensitive for term in OBJECTIVE_TERMS},
        insensitive=tuple(InsensitiveKpi(term=term, blocked_on="fixture") for term in insensitive),
    )


# ---------------------------------------------------------------------------
# 1. The refusal is total, and its boundary is exactly where it is documented
# ---------------------------------------------------------------------------


@given(regret=_ANY_REGRET, reference=_COSTS, foresight=_COSTS)
def test_the_refusal_fires_for_exactly_the_negative_regrets(
    regret: float, reference: float, foresight: float
) -> None:
    """Total, and an iff rather than an implication: no finite regret is unclassified."""
    refusal = negative_regret_refusal(
        regret=regret, mean_reference=reference, mean_foresight=foresight
    )

    assert (refusal is None) == (regret >= 0.0)
    if refusal is not None:
        assert refusal.strip(), "a refusal must carry a reason, never an empty string"


def test_zero_is_admissible_because_matching_the_oracle_is_a_measurement() -> None:
    """The boundary is strict on the negative side ONLY, and that is a deliberate choice.

    A regret of exactly ``0.0`` means the incumbent matched the oracle. That is the strongest
    possible support for Finding 4 and it is a legitimate measurement, so refusing it would
    discard the very outcome the premise predicts. Asserted rather than left to the reader,
    because an off-by-one here would silently suppress the spec's best case.
    """
    assert negative_regret_refusal(regret=0.0, mean_reference=1.0, mean_foresight=1.0) is None
    assert negative_regret_refusal(regret=-0.0, mean_reference=1.0, mean_foresight=1.0) is None
    assert (
        negative_regret_refusal(regret=-1e-12, mean_reference=1.0, mean_foresight=1.0) is not None
    )


@given(regret=_NON_NEGATIVE, reference=_COSTS, foresight=_COSTS)
def test_an_admissible_regret_is_never_refused_whatever_the_arm_costs(
    regret: float, reference: float, foresight: float
) -> None:
    """The converse direction, so the property cannot pass by refusing everything."""
    assert (
        negative_regret_refusal(regret=regret, mean_reference=reference, mean_foresight=foresight)
        is None
    )


# ---------------------------------------------------------------------------
# 2. A refusal is attributable without re-running anything
# ---------------------------------------------------------------------------


@given(regret=_NEGATIVE, reference=_COSTS, foresight=_COSTS)
def test_a_refusal_names_the_two_arm_costs_it_is_about(
    regret: float, reference: float, foresight: float
) -> None:
    """A refusal that does not say WHICH arms inverted sends the reader back to the runner.

    Both means are interpolated with ``!r`` so the reason carries full precision: the whole
    point of the number is that a reader can see 2.08 against 2.90 and know which arm won.
    """
    refusal = negative_regret_refusal(
        regret=regret, mean_reference=reference, mean_foresight=foresight
    )

    assert refusal is not None
    assert repr(reference) in refusal
    assert repr(foresight) in refusal
    assert repr(regret) in refusal
    # It must also say what it does NOT claim, so the refusal is not read as a verdict.
    assert "task 10.4" in refusal and "task 11" in refusal


def test_the_measured_run_is_refused_and_stays_refused() -> None:
    """The numbers run 34570166681 actually produced are inadmissible.

    A regression pin on the FUNCTION, not on the world: if the comparator is later repaired so
    that a fresh run measures a positive regret, this input must still be refused, because the
    question it answers is "would this measurement have been classified?".
    """
    refusal = negative_regret_refusal(
        regret=MEASURED_REGRET,
        mean_reference=MEASURED_REFERENCE_COST,
        mean_foresight=MEASURED_FORESIGHT_COST,
    )

    assert refusal is not None
    assert "NEGATIVE" in refusal
    # The arm ordering that makes this a defect: C beats A, and B beats C.
    assert MEASURED_FORESIGHT_COST < MEASURED_NOOP_COST
    assert MEASURED_REFERENCE_COST < MEASURED_FORESIGHT_COST


# ---------------------------------------------------------------------------
# 3. The hole the refusal closes is real -- proven, not asserted
# ---------------------------------------------------------------------------


def test_without_the_refusal_the_measured_run_reads_as_inconclusive_today() -> None:
    """This is what task 11 would have recorded, and it reads as "regret below the margin"."""
    verdict = classify_regret(
        MEASURED_REGRET,
        objective=_objective(insensitive=("spoilage_rate", "delivery_latency")),
        margin=COMMITTED_MARGIN,
        interval=MEASURED_INTERVAL,
    )

    assert verdict.verdict == "inconclusive"
    assert not verdict.falsifies_finding_4


def test_without_the_refusal_the_same_number_confirms_finding_4_once_e2c_lands() -> None:
    """The load-bearing clause: an EMPTY insensitive set turns this into ``sub-margin``.

    Tasks 12.3 and 13.3 flip ``delivery_latency`` and ``spoilage_rate`` to ``sensitive: true``.
    With both flipped there is no insensitive KPI left to force ``inconclusive``, so the same
    negative number becomes the one verdict that licenses reading the result as consistent with
    Finding 4. **That is why the refusal is a refusal and not a warning**, and asserting it here
    means the reasoning cannot rot into a comment nobody re-derives.
    """
    verdict = classify_regret(
        MEASURED_REGRET,
        objective=_objective(insensitive=()),
        margin=COMMITTED_MARGIN,
        interval=MEASURED_INTERVAL,
    )

    assert verdict.verdict == "sub-margin"
    assert verdict.confirms_finding_4, (
        "if this stops being true the argument for the refusal has changed and this "
        "property must be re-derived, not deleted"
    )
    # And the refusal is what stands between that verdict and the report.
    assert (
        negative_regret_refusal(
            regret=MEASURED_REGRET,
            mean_reference=MEASURED_REFERENCE_COST,
            mean_foresight=MEASURED_FORESIGHT_COST,
        )
        is not None
    )


# ---------------------------------------------------------------------------
# 4. Why the sibling guard is blind to this, asserted as arithmetic
# ---------------------------------------------------------------------------


@given(noop=_COSTS, reference=_COSTS, foresight=_COSTS)
def test_the_headroom_guard_reduces_to_a_claim_that_does_not_mention_the_oracle(
    noop: float, reference: float, foresight: float
) -> None:
    """``headroom >= regret`` is ``A >= B``: the oracle cancels, so it cannot be constrained.

    This is the mechanical statement of why a second clause was needed. A guard built from two
    expressions that share a term cannot say anything about that term, and the existing guard
    shares arm C with the quantity it is checking.
    """
    assume(all(math.isfinite(x) for x in (noop, reference, foresight)))
    headroom = noop - foresight
    regret = reference - foresight

    # The guard's own comparison, and the claim it is equivalent to.
    assert (headroom >= regret) == (noop >= reference)

    # Non-vacuity: the reduced claim really is independent of the oracle, so a run can satisfy
    # the guard while the oracle is invalid. That combination is exactly run 34570166681.
    if noop >= reference and reference < foresight:
        assert headroom >= regret
        assert (
            negative_regret_refusal(
                regret=regret, mean_reference=reference, mean_foresight=foresight
            )
            is not None
        ), "the guard passes and the comparator is still invalid -- the gap this closes"
