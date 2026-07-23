"""The ratcheted :data:`UPLIFT_FLOOR` constant (ADR-042, C60).

This is the single source of truth for the minimum measured decision-integrity
uplift SYNAPSE must sustain. It is imported by the ``uplift_truth`` honesty gate
(:mod:`scripts.audit.uplift_truth`), which fails CI when the measured headline
uplift regresses below this floor — the same BASELINE-ratchet pattern
``scripts/audit/training_truth.py`` uses to lock in a proven gain so it cannot
silently rot away.

Ratchet discipline (R6.2, R6.8):

  * :data:`UPLIFT_FLOOR` is a single declared numeric constant.
  * It is **never lowered**. Once a gain is verified, the floor is raised (in a
    version-controlled commit) to lock it in; a later regression below the
    committed value fails the gate. Lowering it would erase a proven gain and is
    forbidden by the monotonic-ratchet invariant.

The headline uplift is the relative percentage improvement of the Consensus_Arm
over the Baseline_Arm on the contract's primary KPI, so the floor is expressed in
the same unit (percentage points). It starts at ``0.0``: before the harness has
produced and committed a verified positive result, the honest floor is "no proven
uplift yet" — the gate must not assert a gain the repo has not yet demonstrated.
The floor ratchets *up* one PR at a time as verified gains land.
"""

from __future__ import annotations

# Minimum sustained headline uplift, in percentage points of relative improvement
# of the Consensus_Arm over the Baseline_Arm on the primary KPI. Ratchet UP only;
# never record a value below the previously committed floor (R6.8).
UPLIFT_FLOOR: float = 0.0


class FloorRatchetError(ValueError):
    """Raised when a proposed :data:`UPLIFT_FLOOR` update would lower the floor.

    Lowering the floor erases a proven gain and violates the monotonic-ratchet
    invariant (R6.8), mirroring the way ``training_truth.BASELINE`` only ever
    ratchets in the direction that locks a gain in.
    """


def ratchet(previous: float, proposed: float) -> float:
    """Return the committed floor after proposing ``proposed`` over ``previous``.

    The uplift floor is a monotonic ratchet (R6.8): a verified gain is locked in
    by raising the floor, and it is **never lowered**. This pure helper enforces
    that discipline for a single update:

      * accept the update when ``proposed >= previous`` (raise or hold the floor),
        returning the new committed value ``proposed``;
      * reject the update when ``proposed < previous`` by raising
        :class:`FloorRatchetError`, since committing it would record a floor below
        the previously committed value.

    Args:
        previous: The previously committed floor value.
        proposed: The candidate new floor value.

    Returns:
        The new committed floor (``proposed``) when the update is monotonic.

    Raises:
        FloorRatchetError: If ``proposed`` is strictly below ``previous``.
    """
    if proposed < previous:
        raise FloorRatchetError(
            f"uplift floor may not be lowered: proposed {proposed!r} < "
            f"previously committed {previous!r} (R6.8 monotonic ratchet)"
        )
    return proposed


__all__ = ["UPLIFT_FLOOR", "FloorRatchetError", "ratchet"]
