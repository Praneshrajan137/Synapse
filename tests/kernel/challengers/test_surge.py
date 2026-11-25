"""The store's surge evidence against a brute force; the detector's memory; the threshold rule.

* The evidence equals an independent computation on real windows (the lane incumbent's memory in
  cells N and S1 at development seeds): scipy's Poisson log-probabilities hour by hour (exact hours
  as counts, censored hours as ``P(D >= s)``), log-sum-exp over the 16 item levels and the 16 store
  levels, the share mixture and the product over items in the log domain. Planted: the first
  design's defect, a no-sales day normalised per hypothesis, is caught.
* A complete day's likelihoods, kept between decisions, give the same bits as a fresh detector
  given the same 72 hours (truth session 6, gate item 10). Planted: a kept day altered in its last
  bit is caught.
* The threshold is the smallest power of two strictly above the largest evidence, so no fitted run
  alarms. Planted: "at or above" alarms on an exact power of two.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from synapse_kernel.challengers import surge
from synapse_kernel.challengers.history import CENSORED, EXACT, WINDOW_HOURS
from synapse_kernel.challengers.sensing import declared_means
from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.release import seeds
from synapse_kernel.release.engine import run
from synapse_kernel.release.incumbent import load_incumbent_tables
from synapse_kernel.release.scenario import build_scenario
from synapse_kernel.release.world import load_release_world

stats = pytest.importorskip("scipy.stats")
special = pytest.importorskip("scipy.special")


class _Window:
    """A stand-in memory holding one fixed window (one replicate)."""

    def __init__(self, sales: Any, state: Any, week_hour: Any) -> None:
        self.sales = np.asarray(sales, dtype=np.int64)
        self.state = np.asarray(state, dtype=np.int8)
        self.week_hour = np.asarray(week_hour, dtype=np.int64)
        self.replicates, self.items = self.sales.shape[1], self.sales.shape[2]

    def window(self, hours: int) -> tuple[Any, Any, Any]:
        return self.sales[-hours:], self.state[-hours:], self.week_hour[-hours:]


@pytest.fixture(scope="module")
def world() -> Any:
    return load_release_world()


def _memory(world: Any, cell: str, k: int) -> list[_Window]:
    """The lane incumbent's 72-hour memory at every decision of one replicate."""
    tables = load_incumbent_tables()
    lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
    seen: list[_Window] = []

    class Capture:
        def start(self, replicates: int) -> None:
            lane.start(replicates)

        def decide(self, obs: Any) -> Any:
            lane.observe(obs)
            sales, state, hours = lane.history.window(WINDOW_HOURS)
            seen.append(_Window(sales.copy(), state.copy(), hours.copy()))
            return lane.incumbent_orders(obs)

    run(world, [build_scenario(world, cell, seeds.explore_seed(k))], Capture())
    return seen


@pytest.fixture(scope="module")
def windows(world: Any) -> list[_Window]:
    """Three memories: N mid-run; S1 before the onset and after it.

    Decision d falls at hour 24 (d // 4) + (2, 11, 17, 22)[d % 4]; S1's surge at k 67 starts at hour
    152.4, so decision 16 (hour 98) is before it and decision 30 (hour 185) after, its onset day
    then complete and kept.
    """
    surged = _memory(world, "S1", 67)
    return [_memory(world, "N", 64)[30], surged[16], surged[30]]


def _brute_log2(world: Any, window: _Window) -> float:
    """The store's evidence, log2, computed independently in the log domain with scipy."""
    means = declared_means(world)
    store = np.asarray(world.day_store_factors)
    item = np.asarray(world.day_item_factors)
    mults = np.asarray((1.0, *surge.MULTIPLIERS))
    c = (mults[:, None, None] * store[None, :, None] * item[None, None, :]).reshape(-1)
    sales, state, week_hour = window.window(WINDOW_HOURS)
    labels = surge.day_labels(week_hour)
    last = int(labels.max())
    day_logs: list[list[float]] = []
    for d in range(last + 1):
        on = labels == d
        if int(np.count_nonzero(on)) != 24 and d != last:
            continue
        ll = np.zeros((window.items, c.size))
        for h, s_h, st_h in zip(week_hour[on], sales[on][:, 0, :], state[on][:, 0, :], strict=True):
            lam = means[h][:, None] * c[None, :]
            ll += np.where((st_h == EXACT)[:, None], stats.poisson.logpmf(s_h[:, None], lam), 0.0)
            ll += np.where(
                (st_h == CENSORED)[:, None], stats.poisson.logsf(s_h[:, None] - 1, lam), 0.0
            )
        a = special.logsumexp(ll.reshape(window.items, mults.size, 16, 16), axis=-1)  # over f
        a0 = a[:, 0, :]
        abar = special.logsumexp(a[:, 1:, :], axis=1) - math.log(len(surge.MULTIPLIERS))
        den = special.logsumexp(a0.sum(axis=0))
        day_logs.append(
            [
                special.logsumexp(
                    np.logaddexp(math.log(1 - p) + a0, math.log(p) + abar).sum(axis=0)
                )
                - den
                for p in surge.FRACTIONS
            ]
        )
    best = -math.inf
    for k in range(len(day_logs)):
        totals = [sum(day[j] for day in day_logs[k:]) for j in range(len(surge.FRACTIONS))]
        best = max(best, float(special.logsumexp(totals)) - math.log(len(surge.FRACTIONS)))
    return best / math.log(2)


def test_the_evidence_equals_a_brute_force(world: Any, windows: list[_Window]) -> None:
    got = [math.log2(float(surge.SurgeDetector(world).assess(w).evidence[0])) for w in windows]
    want = [_brute_log2(world, w) for w in windows]
    assert got[2] > 20 > got[0]  # S1 after the onset stands out; N does not
    for g, w in zip(got, want, strict=True):
        assert abs(g - w) < 1e-8, (g, w)


def test_a_no_sales_day_normalised_per_hypothesis_is_caught(
    world: Any, windows: list[_Window], monkeypatch: pytest.MonkeyPatch
) -> None:
    true = surge.likelihood

    def planted(levels: Any, log_levels: Any, sold: Any, mean: Any) -> Any:
        out = true(levels, log_levels, sold, mean)
        lows = levels.reshape(-1, 256).min(axis=1).repeat(256)  # each hypothesis's own lowest
        none = (sold == 0)[:, :, None]
        return np.where(none, out * np.exp(lows[None, None, :] * mean[:, :, None]), out)

    monkeypatch.setattr(surge, "likelihood", planted)
    gaps = [
        abs(
            math.log2(float(surge.SurgeDetector(world).assess(w).evidence[0]))
            - _brute_log2(world, w)
        )
        for w in windows
    ]
    assert max(gaps) > 1e-3


def test_kept_days_give_the_bits_a_fresh_detector_computes(world: Any) -> None:
    tables = load_incumbent_tables()
    warm = surge.SurgeDetector(world)
    lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
    states: list[tuple[Any, Any]] = []

    class Watch:
        def start(self, replicates: int) -> None:
            lane.start(replicates)
            warm.reset()

        def decide(self, obs: Any) -> Any:
            lane.observe(obs)
            deciding = np.nonzero(obs.deciding)[0]
            if len(states) in (20, 30, 41):
                fresh = surge.SurgeDetector(world).assess(lane.history, deciding)
                kept = warm.assess(lane.history, deciding)
                states.append((kept, fresh))
            else:
                warm.assess(lane.history, deciding)
                states.append((None, None))
            return lane.incumbent_orders(obs)

    run(world, [build_scenario(world, "S1", seeds.explore_seed(67))], Watch())
    pairs = [p for p in states if p[0] is not None]
    assert len(pairs) == 3
    for kept, fresh in pairs:
        for field in ("evidence", "prob", "size"):
            assert np.array_equal(getattr(kept, field), getattr(fresh, field))


def test_an_altered_kept_day_is_caught(world: Any, windows: list[_Window]) -> None:
    detector = surge.SurgeDetector(world)
    window = windows[2]
    first = detector.assess(window).evidence.copy()
    assert len(detector.days) == 2  # the two complete days in memory were kept
    for key in detector.days:  # planted: every kept value one bit off
        detector.days[key] = np.nextafter(detector.days[key], np.inf)
    assert not np.array_equal(detector.assess(window).evidence, first)


def test_the_threshold_is_strictly_above_the_largest_evidence() -> None:
    from scripts.challengers.calibrate_surge import threshold_above

    for largest in (1.0, 2.0**7, 2.0**7 * 1.0000001, 2.0**8 - 1e-9, 7.6175):
        t = threshold_above(largest)
        assert t > largest and t / 2 <= largest and math.log2(t).is_integer()
    planted = 2.0 ** math.ceil(math.log2(2.0**7))  # "at or above"
    assert not planted > 2.0**7  # alarms on the run that set it
