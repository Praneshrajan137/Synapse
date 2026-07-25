"""Property-based test that the uplift floor is a monotonic, data-gated ratchet.

Feature: core-purpose-uplift, Property 14: The uplift floor is a monotonic ratchet.

    *For any* previously committed floor ``previous`` and proposed value ``proposed``,
    ``ratchet(previous, proposed)`` returns ``proposed`` when ``proposed >= previous`` and
    raises ``FloorRatchetError`` when ``proposed < previous``; and a proposed floor raised
    on a verified positive measurement is accepted only when ``0 < proposed <= measured``.

    Requirement 4.3: "IF a proposed ``UPLIFT_FLOOR`` update is strictly below the
    previously committed value, THEN THE ratchet helper SHALL raise ``FloorRatchetError``
    and reject the update."

    Requirement 4.2: a raise above the committed floor asserts a *measured* gain, so it is
    legitimate only up to the headline uplift of a fully-powered, complete,
    within-fidelity-bound proof — i.e. ``0 < proposed <= measured``.

Both halves are covered here: the pure monotonicity partition of :func:`ratchet` and the
data gate layered on top of it by :func:`ratchet_to_measured`. The expected outcome is
recomputed from the raw proof fields rather than from ``PoweredProof.supports``, so the
test is an independent statement of the rule, not an echo of the implementation.

The property is pure and fast: no artifact is written, no twin is built, no arm is run,
no socket is opened, $0.

**Validates: Requirements 4.2, 4.3**
"""
from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.uplift_floor import (
    MIN_POWERED_REPLICATES,
    UPLIFT_FLOOR,
    FloorRatchetError,
    PoweredProof,
    UnprovenFloorRaiseError,
    ratchet,
    ratchet_to_measured,
)

# ---------------------------------------------------------------------------
# Strategies
#
# The floor is a percentage-point value that starts at 0.0 and ratchets up, so the
# generators stay in a finite band around that domain while deliberately including
# signed zero, sub-unit magnitudes, and negatives so the ``proposed < previous`` and
# ``0 < proposed`` boundaries are exercised rather than skirted.
# ---------------------------------------------------------------------------
_MAGNITUDE = 1e6

_finite = st.floats(
    min_value=-_MAGNITUDE,
    max_value=_MAGNITUDE,
    allow_nan=False,
    allow_infinity=False,
)
_edges = st.sampled_from([0.0, -0.0, 1e-9, -1e-9, 1.0, -1.0, _MAGNITUDE, -_MAGNITUDE])
_floor_value = st.one_of(_finite, _edges)

# Replicate counts straddling the INV-TW-002 power bar, with the bar itself weighted.
_replicates = st.one_of(
    st.integers(min_value=0, max_value=MIN_POWERED_REPLICATES + 64),
    st.sampled_from(
        [0, MIN_POWERED_REPLICATES - 1, MIN_POWERED_REPLICATES, MIN_POWERED_REPLICATES + 1]
    ),
)

# A measurement can be a positive gain, or non-positive (no gain to lock in).
_measured = st.one_of(
    st.floats(min_value=1e-6, max_value=_MAGNITUDE, allow_nan=False, allow_infinity=False),
    st.floats(min_value=-_MAGNITUDE, max_value=0.0, allow_nan=False, allow_infinity=False),
    st.sampled_from([0.0, 1e-9, 3.0]),
)


@st.composite
def _updates(draw):
    """Draw ``(previous, proposed, proof)`` triples aimed at the rule's boundaries.

    ``proposed`` is often derived from ``measured`` (at it, just under it, just over it)
    so the ``0 < proposed <= measured`` edge is hit densely instead of by luck, and
    ``previous`` is sometimes exactly ``proposed`` so the "hold the floor" branch is
    exercised alongside raises and lowers.
    """
    measured = draw(_measured)
    replicates = draw(_replicates)
    incomplete = draw(st.booleans())
    within_bound = draw(st.sampled_from([True, False, None]))
    has_proof = draw(st.booleans())

    proposed = draw(
        st.one_of(
            st.just(measured),
            st.builds(
                lambda factor: measured * factor,
                st.floats(min_value=0.0, max_value=1.5, allow_nan=False, allow_infinity=False),
            ),
            _floor_value,
        )
    )
    previous = draw(st.one_of(st.just(proposed), _floor_value))

    proof = (
        PoweredProof(
            headline_uplift=measured,
            replicates=replicates,
            incomplete=incomplete,
            within_fidelity_bound=within_bound,
        )
        if has_proof
        else None
    )
    return previous, proposed, proof


def _raise_is_supported(proposed: float, proof: PoweredProof | None) -> bool:
    """Restate the design rule for an accepted raise, independent of the implementation."""
    if proof is None:
        return False
    if proof.replicates < MIN_POWERED_REPLICATES:
        return False
    if proof.incomplete:
        return False
    if proof.within_fidelity_bound is not True:
        return False
    measured = proof.headline_uplift
    if not math.isfinite(measured) or measured <= 0.0:
        return False
    return 0.0 < proposed <= measured


# ---------------------------------------------------------------------------
# Property 14
# ---------------------------------------------------------------------------
@settings(max_examples=300, deadline=None)
@given(update=_updates())
def test_uplift_floor_is_a_monotonic_data_gated_ratchet(update) -> None:
    """Property 14: monotonicity is total, and raises are bounded by the measurement.

    **Validates: Requirements 4.2, 4.3**
    """
    previous, proposed, proof = update

    # -- half 1: the pure monotonicity partition (R4.3) --------------------------
    if proposed >= previous:
        assert ratchet(previous, proposed) == proposed
    else:
        with pytest.raises(FloorRatchetError) as exc:
            ratchet(previous, proposed)
        # A lowered floor is the monotonicity failure, not the unproven-raise failure.
        assert not isinstance(exc.value, UnprovenFloorRaiseError)
        assert "may not be lowered" in str(exc.value)

    # -- half 2: the data gate layered on the same partition (R4.2) --------------
    if proposed < previous:
        # Lowering stays rejected even when a supporting measurement exists.
        with pytest.raises(FloorRatchetError):
            ratchet_to_measured(previous, proposed, proof)
    elif proposed == previous:
        # Holding the committed floor asserts nothing new, so it needs no proof.
        assert ratchet_to_measured(previous, proposed, proof) == proposed
        assert ratchet_to_measured(previous, proposed, None) == proposed
    elif _raise_is_supported(proposed, proof):
        assert ratchet_to_measured(previous, proposed, proof) == proposed
    else:
        with pytest.raises(UnprovenFloorRaiseError):
            ratchet_to_measured(previous, proposed, proof)
        # Absence of proof is never a pass: the same raise with no measurement fails too.
        with pytest.raises(UnprovenFloorRaiseError):
            ratchet_to_measured(previous, proposed, None)


@settings(max_examples=200, deadline=None)
@given(
    start=st.floats(min_value=0.0, max_value=_MAGNITUDE, allow_nan=False, allow_infinity=False),
    updates=st.lists(_updates(), min_size=0, max_size=16),
)
def test_folded_data_gated_updates_never_lower_the_committed_floor(start, updates) -> None:
    """Property 14: over any update sequence the committed floor is non-decreasing.

    Rejected proposals (lowering, or an unproven raise) hold the previously committed
    value, so no history of attempts can walk the floor back down.

    **Validates: Requirements 4.2, 4.3**
    """
    committed = start
    for _previous, proposed, proof in updates:
        before = committed
        try:
            committed = ratchet_to_measured(committed, proposed, proof)
        except FloorRatchetError:
            committed = before
        assert committed >= before
        # An accepted change is either a hold or a measurement-bounded positive raise.
        if committed != before:
            assert committed > before
            assert _raise_is_supported(committed, proof)
    assert committed >= start


def test_declared_floor_holds_under_the_data_gate() -> None:
    """The shipped ``UPLIFT_FLOOR`` is a valid, proof-free starting point (R4.2)."""
    assert ratchet(UPLIFT_FLOOR, UPLIFT_FLOOR) == UPLIFT_FLOOR
    assert ratchet_to_measured(UPLIFT_FLOOR, UPLIFT_FLOOR, None) == UPLIFT_FLOOR
    # Raising it without a measurement is rejected, so the floor cannot drift upward.
    with pytest.raises(UnprovenFloorRaiseError):
        ratchet_to_measured(UPLIFT_FLOOR, UPLIFT_FLOOR + 1.0, None)
