"""The guard of decision D-4(b), sealed in PREREG-1 section 3: no reorder made without a person
outside half to twice the incumbent's quantity.

A challenger's quantity for an item at a decision is clipped to ``[ceil(q_I / 2), 2 q_I]`` in whole
units (the session-5 gate, section 7, for whole units), ``q_I`` the incumbent's quantity at the same
decision on the same state; ``q_I = 0`` gives ``{0}``, so a challenger cannot order where the
incumbent orders nothing. A pure function with no free parameter, frozen at W: session 6's
composition passes every challenger quantity through it.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

__all__ = ["guard"]

I64 = npt.NDArray[np.int64]


def guard(challenger: I64, incumbent: I64) -> I64:
    """Clip ``challenger`` to ``[ceil(q_I / 2), 2 q_I]`` elementwise; ``q_I = 0`` allows only 0."""
    low = (incumbent + 1) // 2
    high = 2 * incumbent
    out: I64 = np.clip(challenger, low, high)
    return out
