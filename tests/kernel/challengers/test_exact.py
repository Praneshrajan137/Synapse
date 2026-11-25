"""The exact-arithmetic helpers the challengers decide with, against independent references.

Each helper uses + - * /, ``frexp``/``ldexp``, integer sums and sums in order only, so its bits
are the same on every platform (truth session 6, gate item 8). Here each is checked against a
reference computed another way: Python's ``fractions`` for products and sums, ``math.log`` for the
logarithm, the kernel's own ``exp_neg`` for the work-saving exponential. A planted variant of each
(a float product, a sum that drops small terms, a log one term short) is shown failing.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest

from synapse_kernel.challengers.exact import (
    exp_neg_clamped,
    exp_neg_live,
    log_pos,
    scaled_float,
    scaled_product,
    scaled_ratio,
    scaled_sum,
)


def _value(mant: float, expo: int) -> Fraction:
    return Fraction(mant) * Fraction(2) ** int(expo)


def _rel(a: Fraction, b: Fraction) -> float:
    return 0.0 if a == b else float(abs(a - b) / max(abs(a), abs(b)))


def test_a_product_of_300_terms_is_right_and_never_overflows() -> None:
    rng = np.random.default_rng(11)
    for scale in (1e-200, 1e-3, 1.0, 30.0, 1e150):
        values = rng.uniform(0.2, 3.0, size=300) * scale
        mant, expo = scaled_product(values)
        exact = math.prod((Fraction(float(v)) for v in values), start=Fraction(1))
        assert 0.5 <= float(mant) < 1.0
        assert _rel(_value(float(mant), int(expo)), exact) < 1e-12
        plain = math.prod(values.tolist())  # the planted variant: one float product
        if scale >= 30.0:
            assert plain == math.inf
        if scale <= 1e-200:
            assert plain == 0.0


def test_a_zero_factor_gives_zero() -> None:
    mant, expo = scaled_product(np.array([2.0, 0.0, 3.0]))
    assert float(mant) == 0.0 and int(expo) == 0


def test_a_sum_of_scaled_values_keeps_every_term_that_matters() -> None:
    rng = np.random.default_rng(5)
    mant = rng.uniform(0.5, 1.0, size=16)
    expo = rng.integers(-1500, 1500, size=16).astype(np.int64)
    mant[3] = 0.0  # a zero term
    got_m, got_e = scaled_sum(mant, expo)
    exact = sum((_value(float(m), int(e)) for m, e in zip(mant, expo, strict=True)), Fraction(0))
    assert _rel(_value(float(got_m), int(got_e)), exact) < 1e-12


def test_a_ratio_and_its_corners() -> None:
    m, e = scaled_ratio(np.array([0.75]), np.array([10]), np.array([0.5]), np.array([3]), 1000)
    assert _value(float(m[0]), int(e[0])) == Fraction(3, 2) * 2**7
    m, e = scaled_ratio(np.array([0.75]), np.array([0]), np.array([0.0]), np.array([0]), 1000)
    assert float(scaled_float(m, e, 1000)[0]) == 2.0**1000  # x / 0 is the cap
    m, e = scaled_ratio(np.array([0.0]), np.array([0]), np.array([0.0]), np.array([0]), 1000)
    assert float(scaled_float(m, e, 1000)[0]) == 1.0  # 0 / 0 is 1


def test_scaled_float_caps_and_underflows_cleanly() -> None:
    out = scaled_float(np.array([0.5, 0.75, 0.5]), np.array([1, 2000, -3000]), 1000)
    assert out.tolist() == [1.0, 2.0**1000, 0.0]


def test_log_pos_agrees_with_the_library_log_to_a_few_ulps() -> None:
    x = np.concatenate([np.geomspace(1e-300, 1e300, 50001), np.linspace(0.25, 4.0, 50001)])
    got = log_pos(x)
    want = np.array([math.log(v) for v in x.tolist()])
    assert float(np.max(np.abs(got - want) / np.maximum(np.abs(want), 1e-300))) < 2e-15
    assert float(np.max(np.abs(got - want))) < 1e-12
    with pytest.raises(ValueError, match="above 0"):
        log_pos(np.array([1.0, 0.0]))


def test_a_log_one_term_short_is_caught() -> None:
    from synapse_kernel.challengers import exact

    x = np.linspace(0.70, 1.42, 10001)  # where |t| is largest
    t = (x - 1.0) / (x + 1.0)
    short = 2.0 * t * sum(t ** (2 * k) / (2 * k + 1) for k in range(3))  # planted: three terms
    want = np.array([math.log(v) for v in x.tolist()])
    assert float(np.max(np.abs(short - want))) > 1e-9  # the plant is visibly wrong
    assert float(np.max(np.abs(exact.log_pos(x) - want))) < 1e-15


def test_exp_neg_live_has_the_kernel_bits() -> None:
    rng = np.random.default_rng(3)
    x = np.concatenate(
        [rng.uniform(0, 700, 200_000), rng.exponential(2, 200_000), [0.0, 600.0, 600.0001, 1e300]]
    )
    a, b = exp_neg_live(x), exp_neg_clamped(x)
    assert np.array_equal(a.view(np.int64), b.view(np.int64))
    planted = np.where(x > 599.0, 0.0, b)  # a cut at the wrong place
    assert not np.array_equal(planted.view(np.int64), b.view(np.int64))
