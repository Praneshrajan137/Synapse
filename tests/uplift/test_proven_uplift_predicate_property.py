"""Property-based test that "proven uplift" means exactly one thing.

Feature: core-purpose-uplift, Property 26: Uplift is "proven" only for a within-bound,
powered, floor-clearing positive measurement.

    *For any* candidate outcome described by (artifact powered?, headline value,
    ``UPLIFT_FLOOR``, within-fidelity-bound?), the doc/success predicate resolves to
    "proven"/"success" if and only if the run is a ``Powered_Run``, the measured headline
    is ``>= UPLIFT_FLOOR`` and strictly positive, and the result is within the fidelity
    bound; any zero, negative, unavailable, incomplete, or out-of-bound outcome resolves
    to "unproven"/non-success and does not make the floor eligible to ratchet above 0.0.

    Requirement 8.4: docs describe the uplift as proven only when a co-located
    fully-powered proof artifact (>= the INV-TW-002 replicate floor per arm) records a
    Headline_Uplift >= the committed ``UPLIFT_FLOOR``, and as unproven otherwise.

    Requirement 10.6: a zero, negative, unavailable, or incomplete honest measurement is a
    valid non-success and SHALL NOT ratchet ``UPLIFT_FLOOR`` above 0.0.

    Requirement 10.7: a result outside the committed Fidelity_Bound SHALL NOT count as
    success regardless of the Headline_Uplift magnitude.

The expected verdict is recomputed from the raw outcome fields, so this test is an
independent statement of the rule rather than an echo of ``is_proven_uplift``. The second
half ties the verdict to its consequence: an unproven outcome leaves the floor ineligible
to rise above 0.0.

The property is pure and fast: no artifact is written, no twin is built, no arm is run,
no socket is opened, $0.

**Validates: Requirements 8.4, 10.6, 10.7**
"""
from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.uplift_floor import (
    MIN_POWERED_REPLICATES,
    UPLIFT_FLOOR,
    PoweredProof,
    UnprovenFloorRaiseError,
    is_proven_uplift,
    ratchet_to_measured,
)

_MAGNITUDE = 1e6

# Headline values in percentage points, deliberately dense around the 0.0 sign boundary
# and the committed floor so "strictly positive" and ">= floor" are exercised, not skirted.
_headline = st.one_of(
    st.floats(min_value=-_MAGNITUDE, max_value=_MAGNITUDE, allow_nan=False, allow_infinity=False),
    st.sampled_from([0.0, -0.0, 1e-9, -1e-9, 1.0, -1.0, 3.0]),
)

# Replicate counts straddling the INV-TW-002 power bar, with the bar itself weighted.
_replicates = st.one_of(
    st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES + 64),
    st.sampled_from(
        [0, 1, MIN_POWERED_REPLICATES - 1, MIN_POWERED_REPLICATES, MIN_POWERED_REPLICATES + 1]
    ),
)

# Committed floors: the shipped 0.0, plus already-ratcheted positive values.
_floor = st.one_of(
    st.just(UPLIFT_FLOOR),
    st.floats(min_value=0.0, max_value=_MAGNITUDE, allow_nan=False, allow_infinity=False),
    st.sampled_from([0.0, 1e-9, 1.0, 3.0]),
)


@st.composite
def _outcomes(draw):
    """Draw ``(proof_or_None, floor)`` candidate outcomes across every failure mode."""
    headline = draw(_headline)
    floor = draw(_floor)
    # Sometimes pin the headline to the floor's boundary so ``>=`` vs ``>`` is probed.
    headline = draw(st.sampled_from([headline, floor, floor - 1e-9, floor + 1e-9]))
    proof = (
        PoweredProof(
            headline_uplift=headline,
            replicates=draw(_replicates),
            incomplete=draw(st.booleans()),
            # None models "fidelity unavailable", which is not within-bound.
            within_fidelity_bound=draw(st.sampled_from([True, False, None])),
        )
        if draw(st.booleans())
        else None
    )
    return proof, floor


def _expected_proven(proof: PoweredProof | None, floor: float) -> bool:
    """Restate the R8.4 / R10.5-10.7 rule directly from the raw outcome fields."""
    if proof is None:  # unavailable measurement
        return False
    if proof.replicates < MIN_POWERED_REPLICATES:  # not a Powered_Run
        return False
    if proof.incomplete:  # a failed pair anywhere
        return False
    if proof.within_fidelity_bound is not True:  # out-of-bound or unavailable fidelity
        return False
    measured = proof.headline_uplift
    if not math.isfinite(measured):
        return False
    return measured > 0.0 and measured >= floor


@settings(max_examples=300, deadline=None)
@given(outcome=_outcomes())
def test_proven_uplift_requires_powered_within_bound_positive_floor_clearing_measurement(
    outcome,
) -> None:
    """Property 26: the proven/success predicate is exactly the conjunction, and unproven
    outcomes leave the floor ineligible to ratchet above 0.0.

    **Validates: Requirements 8.4, 10.6, 10.7**
    """
    proof, floor = outcome

    # -- half 1: the predicate is the conjunction, nothing more, nothing less ----
    verdict = is_proven_uplift(proof, floor)
    assert verdict is _expected_proven(proof, floor)

    if verdict:
        # A proven verdict implies every conjunct held, so none can be dropped.
        assert proof is not None
        assert proof.is_powered and not proof.incomplete
        assert proof.within_fidelity_bound is True
        assert proof.headline_uplift > 0.0 and proof.headline_uplift >= floor

    # -- half 2: the ratchet consequence at the shipped floor (R10.6, R10.7) -----
    proven_at_zero = is_proven_uplift(proof, 0.0)
    candidates = [1e-9, 1.0, _MAGNITUDE]
    if proof is not None and math.isfinite(proof.headline_uplift):
        candidates.append(proof.headline_uplift)

    for candidate in candidates:
        if candidate <= 0.0:
            continue
        if proven_at_zero and candidate <= proof.headline_uplift:
            # Only a proven measurement makes a raise above 0.0 eligible, and only up to
            # the measured value.
            assert ratchet_to_measured(0.0, candidate, proof) == candidate
        else:
            with pytest.raises(UnprovenFloorRaiseError):
                ratchet_to_measured(0.0, candidate, proof)


def test_shipped_floor_is_unproven_without_a_measurement() -> None:
    """No powered proof exists yet, so the shipped floor stays honest at 0.0 (R8.4)."""
    assert UPLIFT_FLOOR == 0.0
    assert is_proven_uplift(None) is False
    # A perfect measurement that is out of the fidelity bound is still not success (R10.7).
    out_of_bound = PoweredProof(
        headline_uplift=42.0,
        replicates=MIN_POWERED_REPLICATES,
        incomplete=False,
        within_fidelity_bound=False,
    )
    assert is_proven_uplift(out_of_bound) is False
    with pytest.raises(UnprovenFloorRaiseError):
        ratchet_to_measured(UPLIFT_FLOOR, 1.0, out_of_bound)
