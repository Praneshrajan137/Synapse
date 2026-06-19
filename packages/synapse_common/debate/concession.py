"""Pure, shared rule-based concession math for debate revision (ADR-052, R3).

All eight agents must apply the *identical* bounded-concession arithmetic when they
revise a proposal toward the round's consensus. Keeping that math here — pure, with no
I/O and no dependency on the LLM, A2A transport, or the world — means there is exactly
one property-tested implementation rather than eight copies drifting apart.

The three helpers map directly to the requirements:

* :func:`consensus_position` — the arithmetic mean of the round's ``utility_score`` values (R3.2).
* :func:`within_convergence_band` — whether an agent is already close enough to maintain
  rather than concede, using the same variance bound as ``_check_convergence`` (R3.9).
* :func:`concede_toward` — a bounded, monotone move toward consensus that never overshoots (R3.3).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def consensus_position(utility_scores: Sequence[float]) -> float:
    """Return the arithmetic mean of the current round's proposal ``utility_score`` values.

    This is the consensus position an agent concedes toward during a debate round (R3.2).

    Args:
        utility_scores: The current round's proposal utility scores. Must be non-empty.

    Returns:
        The arithmetic mean of ``utility_scores``.

    Raises:
        ValueError: If ``utility_scores`` is empty (no consensus is defined).
    """
    if not utility_scores:
        raise ValueError("consensus_position requires at least one utility score")
    return math.fsum(utility_scores) / len(utility_scores)


def within_convergence_band(
    current: float,
    consensus: float,
    *,
    variance_threshold: float = 0.1,
) -> bool:
    """Return ``True`` when ``current`` is close enough to ``consensus`` to maintain.

    An agent whose ``utility_score`` already lies within the convergence band of the
    consensus should return a maintained position rather than a revision (R3.9). The band
    half-width is ``sqrt(variance_threshold)``, mirroring the variance bound used by
    ``_check_convergence`` (variance < 0.1).

    Args:
        current: The agent's current ``utility_score``.
        consensus: The consensus position to compare against.
        variance_threshold: The variance bound whose square root defines the band
            half-width. Must be non-negative.

    Returns:
        ``True`` when ``abs(current - consensus) <= sqrt(variance_threshold)``.

    Raises:
        ValueError: If ``variance_threshold`` is negative.
    """
    if variance_threshold < 0:
        raise ValueError("variance_threshold must be non-negative")
    return abs(current - consensus) <= math.sqrt(variance_threshold)


def concede_toward(
    current: float,
    consensus: float,
    *,
    max_fraction: float = 0.5,
) -> float:
    """Move ``current`` toward ``consensus`` by at most ``max_fraction`` of the gap.

    A single concession moves the ``utility_score`` toward the consensus position by no
    more than ``max_fraction`` (50% by default) of the distance between the current value
    and the consensus, and never crosses past the consensus (R3.3). The move is monotone
    toward consensus and reduces to a no-op when ``current`` already equals ``consensus``.

    Args:
        current: The agent's current ``utility_score``.
        consensus: The consensus position to concede toward.
        max_fraction: The maximum fraction of the gap to close in one round, in ``[0, 1]``.

    Returns:
        The revised ``utility_score`` lying on the segment between ``current`` and
        ``consensus``.

    Raises:
        ValueError: If ``max_fraction`` is outside ``[0, 1]``.
    """
    if not 0.0 <= max_fraction <= 1.0:
        raise ValueError("max_fraction must lie within [0, 1]")
    return current + max_fraction * (consensus - current)
