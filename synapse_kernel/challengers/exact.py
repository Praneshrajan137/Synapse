"""Exact arithmetic for the challengers: the same bits on every platform.

IEEE 754 fixes the result of +, -, *, / and the square root, and numpy's ``cumsum`` adds in order;
the C library's ``exp``, ``log`` and ``pow`` and numpy's pairwise or SIMD reductions are not fixed
across platforms (truth finding F-36's lesson for the world). So the challengers' decision paths use
only these helpers, the kernel's exact :func:`~synapse_kernel.release.sampling.exp_neg`, integer
arithmetic, comparisons, ``floor`` and ``ceil``; ``tests/kernel/challengers/test_rules.py`` refuses
any other numerical call in a challenger module.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
import numpy.typing as npt

from synapse_kernel.release.sampling import MAX_MEAN, exp_neg

__all__ = [
    "EXP_LIMIT",
    "exp_neg",
    "exp_neg_clamped",
    "exp_neg_live",
    "exp_pos",
    "ipow",
    "isum",
    "log_pos",
    "scaled_float",
    "scaled_product",
    "scaled_ratio",
    "scaled_sum",
    "seq_sum",
]

F64 = npt.NDArray[np.float64]
I64 = npt.NDArray[np.int64]
#: Beyond this, ``e**-x`` (below 1e-260) is taken as exactly 0: far below any weight that matters.
EXP_LIMIT: Final[float] = MAX_MEAN


def isum(values: npt.ArrayLike, axis: int | tuple[int, ...] | None = None) -> I64:
    """An integer sum: exact whatever the order.

    Raises:
        TypeError: The values are not integers (a float sum is :func:`seq_sum`'s).
    """
    array = np.asarray(values)
    if not np.issubdtype(array.dtype, np.integer):
        raise TypeError("isum adds integers only")
    out: I64 = np.asarray(np.sum(array.astype(np.int64), axis=axis), dtype=np.int64)
    return out


def seq_sum(values: npt.ArrayLike, axis: int = -1) -> F64:
    """A float sum in order along ``axis`` (a running sum's last entry)."""
    array = np.asarray(values, dtype=np.float64)
    if array.shape[axis] == 0:
        out_shape = list(array.shape)
        del out_shape[axis]
        return np.zeros(out_shape, dtype=np.float64)
    out: F64 = np.take(np.cumsum(array, axis=axis), -1, axis=axis)
    return out


def ipow(base: npt.ArrayLike, power: npt.ArrayLike) -> F64:
    """``base ** power`` elementwise for whole ``power >= 0``, by repeated squaring."""
    x = np.asarray(base, dtype=np.float64)
    k = np.asarray(power, dtype=np.int64)
    shape = np.broadcast_shapes(x.shape, k.shape)
    result = np.ones(shape, dtype=np.float64)
    square = np.broadcast_to(x, shape).copy()
    left = np.broadcast_to(k, shape).copy()
    if bool((left < 0).any()):
        raise ValueError("ipow takes whole powers >= 0")
    while bool((left > 0).any()):
        odd = (left & 1) == 1
        result = np.where(odd, result * square, result)
        square = square * square
        left = left >> 1
    return result


def exp_pos(x: npt.ArrayLike) -> F64:
    """``e**x`` for finite ``x >= 0``, as ``1 / e**-x`` (exactly rounded division of exact
    parts)."""
    out: F64 = 1.0 / exp_neg(x)
    return out


#: The kernel's split of ``ln 2`` and Taylor coefficients, re-stated so :func:`exp_neg_live` gives
#: the kernel's bits (a test checks it against :func:`exp_neg` itself).
_LN2_HI: Final[float] = 6.93147180369123816490e-01
_LN2_LO: Final[float] = 1.90821492927058770002e-10
_INV_LN2: Final[float] = 1.44269504088896338700e00
_TAYLOR: Final[tuple[float, ...]] = tuple(1.0 / math.factorial(k) for k in range(16))


def exp_neg_live(x: npt.ArrayLike) -> F64:
    """:func:`exp_neg_clamped` for ``x >= 0`` already known finite, computing only the entries at or
    below :data:`EXP_LIMIT` (the others are exactly 0): the same bits, with less work."""
    v = np.asarray(x, dtype=np.float64)
    out: F64 = np.zeros(v.shape, dtype=np.float64)
    live = v <= EXP_LIMIT
    u = v[live]
    if u.size == 0:
        return out
    n = np.floor(u * _INV_LN2 + 0.5)
    neg = -((u - n * _LN2_HI) - n * _LN2_LO)
    poly = np.full(u.shape, _TAYLOR[-1], dtype=np.float64)
    for coeff in reversed(_TAYLOR[:-1]):
        poly = poly * neg + coeff
    out[live] = np.ldexp(poly, -n.astype(np.int32))
    return out


def exp_neg_clamped(x: npt.ArrayLike) -> F64:
    """``e**-x`` for finite ``x >= 0``, exactly 0 beyond :data:`EXP_LIMIT` (the same everywhere).

    The kernel's exact ``exp_neg`` accepts at most :data:`EXP_LIMIT`; a likelihood relative to its
    largest term never needs a smaller value than ``e**-600``, about 1e-261.
    """
    v = np.asarray(x, dtype=np.float64)
    out: F64 = np.where(v > EXP_LIMIT, 0.0, exp_neg(np.minimum(v, EXP_LIMIT)))
    return out


#: Mantissas multiplied before each renormalisation: ``0.5 ** 512`` is far above float underflow.
_CHUNK: Final[int] = 512
_NO_EXPONENT: Final[int] = -(2**62)


def scaled_product(values: npt.ArrayLike, axis: int = -1) -> tuple[F64, I64]:
    """A product of non-negative floats along ``axis`` as ``(mantissa, exponent)``, in range.

    The value is ``mantissa * 2**exponent`` with the mantissa in ``[0.5, 1)``, or ``(0, 0)`` for a
    zero product. Mantissas multiply in order (a running product), exponents add as integers, and
    :func:`numpy.frexp` and :func:`numpy.ldexp` are exact, so the bits are the same everywhere.

    Raises:
        ValueError: A value is negative or not finite.
    """
    x = np.moveaxis(np.asarray(values, dtype=np.float64), axis, -1)
    if x.size and not (bool(np.all(np.isfinite(x))) and float(x.min()) >= 0.0):
        raise ValueError("scaled_product takes finite values >= 0")
    mant, expo = np.frexp(x)
    m = np.ones(x.shape[:-1], dtype=np.float64)
    e = isum(expo, axis=-1) if x.shape[-1] else np.zeros(x.shape[:-1], dtype=np.int64)
    for start in range(0, x.shape[-1], _CHUNK):
        m = m * np.take(np.cumprod(mant[..., start : start + _CHUNK], axis=-1), -1, axis=-1)
        m, shift = np.frexp(m)
        e = e + shift.astype(np.int64)
    zero = m == 0.0
    out_m: F64 = np.where(zero, 0.0, m)
    out_e: I64 = np.where(zero, 0, e).astype(np.int64)
    return out_m, out_e


def scaled_sum(mant: npt.ArrayLike, expo: npt.ArrayLike, axis: int = -1) -> tuple[F64, I64]:
    """The sum along ``axis`` of values given as ``(mantissa, exponent)``, in the same form.

    Each term is brought to the largest exponent by an exact :func:`numpy.ldexp` (a term more than
    about 1074 binary orders below it becomes 0, the same everywhere), then the terms add in order.
    """
    m = np.moveaxis(np.asarray(mant, dtype=np.float64), axis, -1)
    e = np.moveaxis(np.asarray(expo, dtype=np.int64), axis, -1)
    live = m != 0.0
    top = np.where(live, e, _NO_EXPONENT).max(axis=-1, initial=_NO_EXPONENT)
    top = np.where(live.any(axis=-1), top, 0)
    shift = np.clip(np.where(live, e - top[..., None], 0), -1100, 0).astype(np.int32)
    total = seq_sum(np.where(live, np.ldexp(m, shift), 0.0), axis=-1)
    out_m, more = np.frexp(total)
    out_e: I64 = np.where(out_m == 0.0, 0, top + more.astype(np.int64)).astype(np.int64)
    result_m: F64 = np.asarray(out_m, dtype=np.float64)
    return result_m, out_e


def scaled_ratio(
    num_m: npt.ArrayLike,
    num_e: npt.ArrayLike,
    den_m: npt.ArrayLike,
    den_e: npt.ArrayLike,
    huge: int,
) -> tuple[F64, I64]:
    """``num / den`` for values as ``(mantissa, exponent)``; ``den = 0`` gives ``2**huge`` where
    ``num > 0`` and 1 where both are 0."""
    nm = np.asarray(num_m, dtype=np.float64)
    dm = np.asarray(den_m, dtype=np.float64)
    live = dm != 0.0
    q, shift = np.frexp(nm / np.where(live, dm, 1.0))
    e = np.asarray(num_e, dtype=np.int64) - np.asarray(den_e, dtype=np.int64) + shift
    out_m: F64 = np.where(live, q, 0.5).astype(np.float64)
    fallback = np.where(nm > 0.0, huge + 1, 1)
    out_e: I64 = np.where(live, np.where(q == 0.0, 0, e), fallback).astype(np.int64)
    return out_m, out_e


def scaled_float(mant: npt.ArrayLike, expo: npt.ArrayLike, cap_log2: int) -> F64:
    """``mantissa * 2**exponent`` as a float, at most ``2**cap_log2`` (exact below the cap)."""
    m = np.asarray(mant, dtype=np.float64)
    e = np.asarray(expo, dtype=np.int64)
    over = e > cap_log2
    value = np.ldexp(m, np.clip(e, -1100, cap_log2).astype(np.int32))
    out: F64 = np.where(over & (m > 0.0), np.ldexp(1.0, cap_log2), value)
    return out


#: ``ln 2`` and ``sqrt(1/2)`` as the nearest doubles (literals, not library calls).
_LN2: Final[float] = 0.6931471805599453
_SQRT_HALF: Final[float] = 0.7071067811865476
#: ``1 / (2k + 1)`` for the atanh series, highest first (``|t| <= 0.1716``: error below 1e-21).
_ATANH: Final[tuple[float, ...]] = tuple(1.0 / k for k in range(25, 0, -2))


def log_pos(x: npt.ArrayLike) -> F64:
    """``ln x`` for finite ``x > 0``, elementwise, from + - * / and ``frexp`` only.

    ``x = m 2**e`` with ``m`` in ``[sqrt(1/2), sqrt(2))``; ``ln m = 2 atanh(t)``, ``t = (m - 1) /
    (m + 1)``, by its odd series in Horner form to ``t**25``; then ``e ln 2`` is added. No library
    transcendental, so the bits are the same on every platform.

    Raises:
        ValueError: A value not finite or not above 0.
    """
    arr = np.asarray(x, dtype=np.float64)
    if arr.size and not (bool(np.all(np.isfinite(arr))) and float(arr.min()) > 0.0):
        raise ValueError("log_pos needs finite values above 0")
    m, e = np.frexp(arr)
    small = m < _SQRT_HALF
    m = np.where(small, m * 2.0, m)
    e = np.where(small, e - 1, e)
    t = (m - 1.0) / (m + 1.0)
    t2 = t * t
    poly = np.full(arr.shape, _ATANH[0], dtype=np.float64)
    for coeff in _ATANH[1:]:
        poly = poly * t2 + coeff
    out: F64 = 2.0 * t * poly + e.astype(np.float64) * _LN2
    return out
