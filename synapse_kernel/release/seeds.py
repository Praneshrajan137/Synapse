"""The exploratory seeds of PREREG-1 section 5: public, derived from a label by SHA-256.

``seed_k`` is the first 8 bytes, big-endian, of ``SHA-256("synapse/prereg-1/explore/" || k)``,
shifted right by one bit, with ``k`` as 8 bytes big-endian. ``k`` in [0, 32) are the tuning seeds,
[32, 64) the validation seeds, 64 and above development. ``tests/kernel/release/test_seeds.py``
checks the derivation against the vectors sealed in ``docs/truth/sealed/prereg-1.json``.
The confirmatory seeds come from a beacon round that does not exist yet; they are not here.
"""

from __future__ import annotations

import hashlib
from typing import Final

__all__ = ["DEVELOPMENT_FROM", "LABEL", "TUNING", "VALIDATION", "explore_seed", "explore_seeds"]

LABEL: Final[bytes] = b"synapse/prereg-1/explore/"
TUNING: Final[range] = range(0, 32)
VALIDATION: Final[range] = range(32, 64)
DEVELOPMENT_FROM: Final[int] = 64


def explore_seed(k: int) -> int:
    """Exploratory seed number ``k`` (``k >= 0``)."""
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    digest = hashlib.sha256(LABEL + k.to_bytes(8, "big")).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def explore_seeds(ks: range) -> tuple[int, ...]:
    """The exploratory seeds for every ``k`` in ``ks``, in order."""
    return tuple(explore_seed(k) for k in ks)
