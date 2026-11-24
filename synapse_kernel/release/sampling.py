"""Samplers built from exact arithmetic only, so a draw has the same bits on every platform.

IEEE 754 fixes the result of every addition, subtraction, multiplication, division and comparison,
and scaling by a power of two is exact; the C library's ``exp`` and ``log``, and numpy's
distribution code, are not fixed across platforms, builds or versions (numpy's own policy, truth
finding F-36). So nothing here calls them:

* :func:`exp_neg` computes ``e**-x`` by Cody and Waite's reduction and a fixed polynomial: not
  correctly rounded, but the same bits everywhere, within a few units in the last place;
* :func:`poisson_inverse` turns one uniform into one Poisson count by inversion, summing the
  probabilities by their recurrence, so a count is a monotone function of its uniform and its mean.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt

__all__ = ["exp_neg", "exp_neg_reference", "poisson_inverse", "poisson_inverse_reference"]

F64 = npt.NDArray[np.float64]

# fdlibm's split of ln 2: LN2_HI has 21 trailing zero bits, so n * LN2_HI is exact for |n| < 2**21.
LN2_HI: Final[float] = 6.93147180369123816490e-01
LN2_LO: Final[float] = 1.90821492927058770002e-10
INV_LN2: Final[float] = 1.44269504088896338700e00
#: Taylor coefficients of e**-r, 1/k! as exact as a double holds them, k = 0..15.
_COEFFS: Final[tuple[float, ...]] = tuple(1.0 / math.factorial(k) for k in range(16))
#: The largest mean a single draw may have: beyond it exp_neg underflows long before the CDF does.
MAX_MEAN: Final[float] = 600.0


def exp_neg(x: npt.ArrayLike) -> F64:
    """``e**-x`` for finite ``x >= 0``, elementwise, from + - * / and ``ldexp`` only.

    ``x = n ln2 + r`` with ``|r| <= ln2 / 2`` (Cody and Waite); ``e**-r`` by a degree-15 Taylor
    polynomial in Horner form (truncation error below ``2e-18`` there); then scaled by ``2**-n``.

    Raises:
        ValueError: Any value negative, not finite, or above :data:`MAX_MEAN`.
    """
    arr = np.asarray(x, dtype=np.float64)
    if arr.size and not (
        bool(np.all(np.isfinite(arr))) and float(arr.min()) >= 0.0 and float(arr.max()) <= MAX_MEAN
    ):
        raise ValueError("exp_neg needs finite values in [0, MAX_MEAN]")
    n = np.floor(arr * INV_LN2 + 0.5)
    r = (arr - n * LN2_HI) - n * LN2_LO
    neg = -r
    poly = np.full_like(arr, _COEFFS[-1])
    for coeff in reversed(_COEFFS[:-1]):
        poly = poly * neg + coeff
    out: F64 = np.ldexp(poly, -n.astype(np.int32))
    return out


def exp_neg_reference(x: float) -> float:
    """:func:`exp_neg` for one Python float, step for step: the form the tests compare against."""
    if not (math.isfinite(x) and 0.0 <= x <= MAX_MEAN):
        raise ValueError("exp_neg needs a finite value in [0, MAX_MEAN]")
    n = math.floor(x * INV_LN2 + 0.5)
    r = (x - n * LN2_HI) - n * LN2_LO
    neg = -r
    poly = _COEFFS[-1]
    for coeff in reversed(_COEFFS[:-1]):
        poly = poly * neg + coeff
    return math.ldexp(poly, -n)


def poisson_inverse(u: npt.ArrayLike, mean: npt.ArrayLike) -> npt.NDArray[np.int64]:
    """The Poisson count at uniform ``u`` and mean ``mean``, elementwise, by inversion.

    The smallest ``k`` with ``u < F(k)``, where ``F`` sums ``p_0 = e**-mean`` and
    ``p_k = p_{k-1} * mean / k`` in order. A mean of 0 gives 0. If rounding leaves ``F`` below ``u``
    in the far tail, the search stops at a bound ``mean + 40 sqrt(mean) + 60`` (probability below
    1e-300 under the true law), which is deterministic too.

    Raises:
        ValueError: ``u`` outside ``[0, 1)`` or a mean outside ``[0, MAX_MEAN]``.
    """
    uu, mu = np.broadcast_arrays(
        np.asarray(u, dtype=np.float64), np.asarray(mean, dtype=np.float64)
    )
    if uu.size and (float(uu.min()) < 0.0 or float(uu.max()) >= 1.0):
        raise ValueError("uniforms must lie in [0, 1)")
    p = exp_neg(mu)
    cdf = p.copy()
    k = np.zeros(uu.shape, dtype=np.int64)
    # sqrt is correctly rounded in IEEE 754, so each element's bound is the same everywhere.
    bound = np.ceil(mu + 40.0 * np.sqrt(mu) + 60.0)
    active = (uu >= cdf) & (bound > 0)
    step = 0
    while bool(active.any()):
        step += 1
        p = np.where(active, p * mu / step, p)
        cdf = np.where(active, cdf + p, cdf)
        k = np.where(active, step, k)
        active = active & (uu >= cdf) & (step < bound)
    return k


def poisson_inverse_reference(u: float, mean: float) -> int:
    """:func:`poisson_inverse` for one draw, step for step in Python floats."""
    if not 0.0 <= u < 1.0:
        raise ValueError("a uniform must lie in [0, 1)")
    p = exp_neg_reference(mean)
    cdf = p
    bound = math.ceil(mean + 40.0 * math.sqrt(mean) + 60.0)
    k = 0
    while u >= cdf and k < bound:
        k += 1
        p = p * mean / k
        cdf = cdf + p
    return k
