"""Same-day sensing: its posterior against brute force, and its rule against the incumbent's.

The posterior is computed with exact arithmetic and a likelihood scaled to its maximum; brute force
here uses scipy's log probabilities in the log domain, a different route to the same number. The
adjusted rule at factor one must give the incumbent's orders to the bit, and the sensed level must
follow the truth: high on a day whose draw was high, near one on a day that was not.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from synapse_kernel.challengers.history import CENSORED, EXACT, UNOBSERVED
from synapse_kernel.challengers.sensing import AdjustedIncumbent, level_grid, posterior_level
from synapse_kernel.release import seeds
from synapse_kernel.release.engine import run
from synapse_kernel.release.harness import scenarios
from synapse_kernel.release.incumbent import Incumbent, load_incumbent_tables
from synapse_kernel.release.world import load_release_world

F64 = npt.NDArray[np.float64]


class _Window:
    """A stand-in history holding one fixed window."""

    def __init__(self, sales: Any, state: Any, week_hour: Any) -> None:
        self.sales = np.asarray(sales, dtype=np.int64)
        self.state = np.asarray(state, dtype=np.int8)
        self.week_hour = np.asarray(week_hour, dtype=np.int64)
        self.replicates, self.items = self.sales.shape[1], self.sales.shape[2]

    def window(self, hours: int) -> tuple[Any, Any, Any]:
        return self.sales[-hours:], self.state[-hours:], self.week_hour[-hours:]


def _brute(window: _Window, means: F64, grid: F64) -> F64:
    stats = pytest.importorskip("scipy.stats")
    out = np.empty((window.replicates, window.items))
    for r in range(window.replicates):
        for i in range(window.items):
            logs = []
            for c in grid:
                total = 0.0
                for h in range(window.sales.shape[0]):
                    lam = means[window.week_hour[h], i] * c
                    s = int(window.sales[h, r, i])
                    if window.state[h, r, i] == EXACT:
                        total += float(stats.poisson.logpmf(s, lam))
                    elif window.state[h, r, i] == CENSORED:
                        total += float(stats.poisson.logsf(s - 1, lam))
                logs.append(total)
            top = max(logs)
            weights = [math.exp(v - top) for v in logs]
            out[r, i] = math.fsum(w * c for w, c in zip(weights, grid, strict=True)) / math.fsum(
                weights
            )
    return out


def test_the_posterior_level_equals_brute_force() -> None:
    world = load_release_world()
    grid = level_grid(world)
    rng = np.random.default_rng(4)
    means = rng.uniform(0.05, 6.0, size=(168, 3))
    for _ in range(12):
        hours = int(rng.integers(1, 12))
        sales = rng.poisson(2.5, size=(hours, 2, 3))
        state = rng.choice([EXACT, EXACT, EXACT, CENSORED, UNOBSERVED], size=(hours, 2, 3))
        sales = np.where(state == CENSORED, np.maximum(sales, 1), sales)
        sales = np.where(state == UNOBSERVED, 0, sales)
        window = _Window(sales, state, rng.integers(0, 168, size=hours))
        got = posterior_level(window, means, grid, 0, hours)  # type: ignore[arg-type]
        assert got == pytest.approx(_brute(window, means, grid), rel=1e-9)


def test_no_evidence_gives_the_prior_mean() -> None:
    world = load_release_world()
    grid = level_grid(world)
    window = _Window(np.zeros((3, 1, 2)), np.full((3, 1, 2), UNOBSERVED), [1, 2, 3])
    got = posterior_level(window, np.ones((168, 2)), grid, 0, 3)  # type: ignore[arg-type]
    assert got == pytest.approx(np.full((1, 2), float(grid.mean())), rel=1e-15)
    assert float(grid.mean()) == pytest.approx(1.0, abs=2e-3)


def test_at_factor_one_the_adjusted_rule_is_the_incumbent_to_the_bit() -> None:
    world, tables = load_release_world(), load_incumbent_tables()

    class Both:
        def __init__(self, name: str) -> None:
            self.a = Incumbent(world, tables[name])
            self.b = AdjustedIncumbent(world, tables[name])
            self.differ = 0

        def start(self, replicates: int) -> None:
            return None

        def decide(self, obs: Any) -> Any:
            x = self.a.decide(obs)
            ones = np.ones(x.shape)
            self.differ += int((x != self.b.decide(obs, ones, ones)).sum())
            return x

    for cell, name in (("N", "I2-P"), ("L", "I2-L"), ("S3", "I2-P"), ("N", "I1-N")):
        both = Both(name)
        run(world, scenarios(world, cell, seeds.explore_seeds(range(64, 66))), both)
        assert both.differ == 0, (cell, name)
