"""The release world's randomness: a standard counter-based cipher and exact samplers.

Threefry-2x32-20 is checked against the answer vectors Random123 publishes (``tests/kat_vectors`` in
DEShawResearch/random123) and against an independent pure-Python form; the samplers against
their step-for-step Python references and against the laws they claim.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synapse_kernel.release import rng, sampling

# (counter, key, expected) from Random123's kat_vectors: "threefry2x32 20 CTR KEY EXPECTED".
KAT = (
    ((0x00000000, 0x00000000), (0x00000000, 0x00000000), (0x6B200159, 0x99BA4EFE)),
    ((0xFFFFFFFF, 0xFFFFFFFF), (0xFFFFFFFF, 0xFFFFFFFF), (0x1CB996FC, 0xBB002BE7)),
    ((0x243F6A88, 0x85A308D3), (0x13198A2E, 0x03707344), (0xC4923A9C, 0x483DF7A0)),
)
WORD = st.integers(min_value=0, max_value=2**32 - 1)


@pytest.mark.parametrize(("counter", "key", "expected"), KAT)
def test_threefry_matches_the_published_answer_vectors(
    counter: tuple[int, int], key: tuple[int, int], expected: tuple[int, int]
) -> None:
    x0, x1 = rng.threefry2x32(
        np.array([counter[0]], dtype=np.uint32), np.array([counter[1]], dtype=np.uint32), *key
    )
    assert (int(x0[0]), int(x1[0])) == expected
    assert rng.threefry2x32_reference(*counter, *key) == expected


@settings(max_examples=300, deadline=None)
@given(WORD, WORD, WORD, WORD)
def test_the_vectorised_cipher_equals_the_pure_python_one(
    c0: int, c1: int, k0: int, k1: int
) -> None:
    x0, x1 = rng.threefry2x32(
        np.array([c0], dtype=np.uint32), np.array([c1], dtype=np.uint32), k0, k1
    )
    assert (int(x0[0]), int(x1[0])) == rng.threefry2x32_reference(c0, c1, k0, k1)


def test_a_draw_is_a_pure_function_of_its_coordinates() -> None:
    grid = rng.uniforms(42, rng.Purpose.DEMAND, np.arange(50)[None, :], np.arange(40)[:, None])
    one = rng.uniforms(42, rng.Purpose.DEMAND, 17, 23)
    assert grid[23, 17] == one[0]  # the same coordinates, alone or in a grid
    assert rng.uniforms(43, rng.Purpose.DEMAND, 17, 23)[0] != one[0]
    assert rng.uniforms(42, rng.Purpose.DEMAND_PAIRS, 17, 23)[0] != one[0]
    assert rng.uniforms(42, rng.Purpose.DEMAND, 17, 23, index=1)[0] != one[0]


def test_uniforms_are_uniform_on_the_unit_interval() -> None:
    draws = rng.uniforms(2026, rng.Purpose.DEMAND, np.arange(400)[None, :], np.arange(500)[:, None])
    assert float(draws.min()) >= 0.0 and float(draws.max()) < 1.0
    counts = np.bincount(np.floor(draws * 20).astype(np.int64).ravel(), minlength=20)
    expected = draws.size / 20
    chi2 = float(((counts - expected) ** 2 / expected).sum())
    assert chi2 < 45.3  # chi-square, 19 degrees of freedom, p = 0.001
    assert abs(float(draws.mean()) - 0.5) < 0.003


@pytest.mark.parametrize(
    ("field", "value"),
    [("entity", 1 << rng.ENTITY_BITS), ("slot", 1 << rng.SLOT_BITS), ("entity", -1)],
)
def test_a_coordinate_outside_its_field_is_refused(field: str, value: int) -> None:
    kwargs = {"entity": 0, "slot": 0, field: value}
    with pytest.raises(ValueError, match=field):
        rng.uniforms(1, rng.Purpose.DEMAND, kwargs["entity"], kwargs["slot"])


def test_exp_neg_is_within_two_ulps_of_libm_and_equals_its_reference() -> None:
    xs = np.concatenate(
        [np.linspace(0.0, 50.0, 50_001), np.linspace(50.0, sampling.MAX_MEAN, 5_001)]
    )
    got = sampling.exp_neg(xs)
    want = np.array([math.exp(-x) for x in xs])
    assert float(np.max(np.abs(got - want) / np.spacing(want))) <= 2.0
    assert all(
        sampling.exp_neg_reference(float(x)) == float(y)
        for x, y in zip(xs[::97], got[::97], strict=True)
    )


@pytest.mark.parametrize("bad", [-1e-9, math.inf, math.nan, sampling.MAX_MEAN * 2])
def test_exp_neg_refuses_values_outside_its_domain(bad: float) -> None:
    with pytest.raises(ValueError):
        sampling.exp_neg(np.array([bad]))


@settings(max_examples=300, deadline=None)
@given(
    st.floats(min_value=0.0, max_value=0.9999999, allow_nan=False),
    st.floats(min_value=0.0, max_value=80.0, allow_nan=False),
)
def test_the_vectorised_poisson_equals_its_reference(u: float, mean: float) -> None:
    assert int(sampling.poisson_inverse(np.array([u]), np.array([mean]))[0]) == (
        sampling.poisson_inverse_reference(u, mean)
    )


def test_poisson_counts_have_the_right_mean_and_variance_and_rise_with_u() -> None:
    draws = rng.uniforms(7, rng.Purpose.DEMAND, np.arange(300)[None, :], np.arange(400)[:, None])
    for mean in (0.05, 0.8, 4.0, 30.0):
        counts = sampling.poisson_inverse(draws, mean)
        assert abs(float(counts.mean()) - mean) < 4 * math.sqrt(mean / counts.size) + 1e-9
        assert abs(float(counts.var()) / mean - 1.0) < 0.05
    ordered = np.linspace(0.0, 0.999999, 1000)
    assert bool(np.all(np.diff(sampling.poisson_inverse(ordered, 6.5)) >= 0))
    assert int(sampling.poisson_inverse(np.array([0.999]), np.array([0.0]))[0]) == 0
