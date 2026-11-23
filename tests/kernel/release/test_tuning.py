"""The sealed tuning procedure on objectives whose answer is known.

A separable cost ``J_i(k) = sum over used parts (k[i, d] - target[i, d])**2`` has its lattice
optimum at the target rounded to the 1/32 grid reachable from 1; the search must land there, keep
unused parts at 1, count its replicate-evaluations, and prefer the smaller factor on an exact tie.
"""

from __future__ import annotations

import numpy as np

from synapse_kernel.release.tuning import STEPS, coordinate_search


def _quadratic(target: np.ndarray, used: np.ndarray, calls: list[int]) -> object:
    def evaluate(k: np.ndarray) -> np.ndarray:
        calls.append(1)
        return np.where(used, (k - target) ** 2, 0.0).sum(axis=1)

    return evaluate


def test_the_search_lands_on_the_lattice_optimum_of_a_separable_cost() -> None:
    rng = np.random.default_rng(3)
    items = 20
    used = np.zeros((items, 6), dtype=bool)
    used[:, 5] = True
    used[::2, 0] = True
    target = rng.uniform(0.0, 3.0, (items, 6))
    calls: list[int] = []
    result = coordinate_search(_quadratic(target, used, calls), used, replicates=32)
    grid = np.round(target * 32) / 32  # the 1/32 lattice reachable from 1
    assert np.allclose(result.factors[used], grid[used], atol=1 / 64 + 1e-12)
    assert np.all(result.factors[~used] == 1.0)
    assert result.replicate_evaluations == 32 * len(calls)
    assert len(result.sweeps_per_step) == len(STEPS)
    assert all(count >= 1 for count in result.sweeps_per_step)


def test_an_exact_tie_takes_the_smaller_factor_and_a_flat_cost_never_moves() -> None:
    used = np.zeros((1, 6), dtype=bool)
    used[0, 3] = True
    flat = coordinate_search(lambda k: np.zeros(1), used, replicates=1)
    assert flat.factors[0, 3] == 1.0 and int(flat.last_move[0]) == 0

    def valley(k: np.ndarray) -> np.ndarray:  # equal at 0.5 and 1.5, lower than at 1
        return np.array([-abs(k[0, 3] - 1.0)]) if abs(k[0, 3] - 1.0) <= 0.5 else np.array([0.0])

    tie = coordinate_search(valley, used, replicates=1, steps=(0.5,))
    assert tie.factors[0, 3] == 0.5


def test_factors_never_go_below_zero() -> None:
    used = np.ones((3, 6), dtype=bool)
    target = np.full((3, 6), -5.0)
    result = coordinate_search(_quadratic(target, used, []), used, replicates=1)
    assert float(result.factors.min()) == 0.0
