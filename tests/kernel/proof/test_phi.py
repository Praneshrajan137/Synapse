"""Phi and its inverse, computed in decimal arithmetic: correct, and the same bits everywhere.

``statistics.NormalDist`` gave different bits on different platforms and Python versions (truth
session 6, F-54). The tests:
- known values and symmetry;
- the inverse undoes Phi;
- agreement to the bit with 60-digit mpmath where mpmath is installed (the analysis's own
  dependencies do not include it);
- a golden digest of Phi's and its inverse's bits over fixed grids. CI on Linux, Windows and Pyodide
  must all reproduce it: a Phi that read the platform's libm would fail it somewhere.
"""

from __future__ import annotations

import hashlib
import math

import pytest

from synapse_kernel.proof.analysis import phi, phi_inverse

#: Phi on 1,001 points in [-38, 38] and its inverse on 199 levels, as float bits (sha256); measured
#: on Windows (CPython 3.11.15) and reproduced on Linux CI and under Pyodide (truth session 6).
GOLDEN: str = "0202d657ff60d1e715241af1d190be0af966e3c3c2f0abdb023ce2d6ffe93c99"


def _grid_bits() -> bytes:
    out = bytearray()
    for i in range(1001):
        out += phi(-38.0 + 76.0 * i / 1000).hex().encode() + b","
    for k in range(1, 200):
        out += phi_inverse(k / 200).hex().encode() + b","
    return bytes(out)


def test_phis_bits_are_the_frozen_ones() -> None:
    assert hashlib.sha256(_grid_bits()).hexdigest() == GOLDEN


def test_known_values() -> None:
    assert phi(0.0) == 0.5
    assert phi(-40.0) == 0.0 and phi(40.0) == 1.0
    assert phi(-math.inf) == 0.0 and phi(math.inf) == 1.0
    assert phi_inverse(0.5) == 0.0
    # The double nearest Phi^-1 of the double 0.975 (whose value is 0.97499999999999997779...).
    assert phi_inverse(0.975) == 1.9599639845400538
    assert phi(-10.0) == 7.619853024160525e-24  # NormalDist (CPython 3.11) gave 0.0 here
    with pytest.raises(ValueError, match="NaN"):
        phi(math.nan)
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="0 < p < 1"):
            phi_inverse(bad)


def test_symmetry_and_the_inverse() -> None:
    for i in range(1, 60):
        x = i / 7.0
        assert abs(phi(x) + phi(-x) - 1.0) <= math.ulp(1.0)
    for k in range(1, 100):
        p = k / 100
        assert abs(phi(phi_inverse(p)) - p) <= 4 * math.ulp(p)


def test_correctly_rounded_against_mpmath() -> None:
    mpmath = pytest.importorskip("mpmath")
    mpmath.mp.dps = 60
    for i in range(0, 761, 7):
        x = -38.0 + i / 10
        assert phi(x) == float(mpmath.ncdf(mpmath.mpf(x))), x
    for p in [10.0**-k for k in range(1, 300, 37)] + [k / 37 for k in range(1, 37)]:
        start = mpmath.mpf(phi_inverse(p))
        level = mpmath.mpf(p)
        root = mpmath.findroot(lambda t, level=level: mpmath.ncdf(t) - level, start)
        assert phi_inverse(p) == float(root), p
