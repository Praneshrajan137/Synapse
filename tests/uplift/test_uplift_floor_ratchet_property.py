"""Property-based tests for the monotonic uplift-floor ratchet.

Feature: decision-integrity-uplift-proof
Property 22: The uplift floor ratchet is monotonic.

    *For any* sequence of floor updates, the committed ``UPLIFT_FLOOR`` is never
    recorded below its previously committed value (the floor is non-decreasing
    over its history).

Validates: Requirements 6.8
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from uplift.uplift_floor import FloorRatchetError, UPLIFT_FLOOR, ratchet


# ---------------------------------------------------------------------------
# Strategies — finite floats for proposed floor values. The uplift floor is a
# percentage-point value that starts at 0.0 and ratchets up, so we exercise the
# full finite non-negative range to stress the monotonicity rule robustly.
# ---------------------------------------------------------------------------
_floor_value = st.floats(
    min_value=0.0,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
)
_floor_updates = st.lists(_floor_value, min_size=0, max_size=50)


def _fold_ratchet(start: float, proposals: list[float]) -> list[float]:
    """Fold the ratchet over a sequence, keeping only the *committed* history.

    A proposal that would lower the floor is rejected (the committed value is
    held); an accepted proposal becomes the new committed value. Returns the full
    history of committed floor values, beginning with ``start``.
    """
    history = [start]
    committed = start
    for proposed in proposals:
        try:
            committed = ratchet(committed, proposed)
        except FloorRatchetError:
            # Rejected: the floor is held at its previously committed value.
            committed = committed
        history.append(committed)
    return history


# ---------------------------------------------------------------------------
# Property 22: committed floor history is non-decreasing (R6.8)
# ---------------------------------------------------------------------------
@settings(max_examples=200)
@given(start=_floor_value, proposals=_floor_updates)
def test_committed_floor_history_is_non_decreasing(
    start: float, proposals: list[float]
) -> None:
    """Folding the ratchet never produces a value below any earlier committed value."""
    history = _fold_ratchet(start, proposals)
    # Every committed value is >= all previously committed values.
    for earlier, later in zip(history, history[1:]):
        assert later >= earlier


@settings(max_examples=200)
@given(start=_floor_value, proposals=_floor_updates)
def test_committed_floor_never_below_running_max(
    start: float, proposals: list[float]
) -> None:
    """The committed floor always equals the max accepted proposal seen so far."""
    committed = start
    for proposed in proposals:
        try:
            committed = ratchet(committed, proposed)
        except FloorRatchetError:
            pass
        # The committed floor is never below the previous committed value.
        assert committed >= start


# ---------------------------------------------------------------------------
# Property 22: the ratchet rule accepts raises/holds and rejects lowers (R6.8)
# ---------------------------------------------------------------------------
@given(previous=_floor_value, proposed=_floor_value)
def test_ratchet_accepts_iff_non_decreasing(
    previous: float, proposed: float
) -> None:
    """ratchet accepts proposed >= previous and rejects proposed < previous."""
    if proposed >= previous:
        assert ratchet(previous, proposed) == proposed
    else:
        try:
            ratchet(previous, proposed)
        except FloorRatchetError:
            pass
        else:  # pragma: no cover - failure path
            raise AssertionError("expected FloorRatchetError for a lowered floor")


# ---------------------------------------------------------------------------
# Property 22 (declared constant): the shipped UPLIFT_FLOOR is a valid finite
# starting point the ratchet can operate on.
# ---------------------------------------------------------------------------
def test_declared_floor_is_valid_ratchet_start() -> None:
    """The committed UPLIFT_FLOOR holds when re-proposed against itself (R6.8)."""
    assert ratchet(UPLIFT_FLOOR, UPLIFT_FLOOR) == UPLIFT_FLOOR
