"""The confirmatory analysis against answers known before it ran (truth session 6, stage D1).

Each test pins one sealed rule of PREREG-1 section 6 or 7, or one choice the session-6 gate fixed
where the sealed text is silent; ``scratchpad/plants/analysis.json`` (recorded in the session's log)
shows each one failing on a planted fault. The scipy cross-check is exact: scipy recomputes z0, the
acceleration and the endpoints from the very bootstrap distribution this module drew.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from synapse_kernel.proof import analysis as a

ROOT = Path(__file__).resolve().parents[3]
F64 = npt.NDArray[np.float64]


def _tiled(patterns: list[list[int]], rows: int = a.RESAMPLES) -> npt.NDArray[np.int64]:
    reps = rows // len(patterns)
    return np.tile(np.asarray(patterns, dtype=np.int64), (reps, 1))


# -- the resamples -------------------------------------------------------------------------------


def test_the_bootstrap_seed_is_prereg_1s() -> None:
    sealed = json.loads((ROOT / "docs/truth/sealed/prereg-1.json").read_text(encoding="utf-8"))
    assert "'synapse/prereg-1/bootstrap/' || sig" in sealed["analysis"]["generator"]
    assert a.BOOTSTRAP_LABEL == b"synapse/prereg-1/bootstrap/"
    sig = bytes(range(48))
    digest = hashlib.sha256(b"synapse/prereg-1/bootstrap/" + sig).hexdigest()
    assert a.bootstrap_seed(sig) == int(digest[:16], 16) // 2


def test_the_cells_draw_from_one_generator_in_the_sealed_order() -> None:
    sizes = {"N": 5, "L": 6, "S1": 7, "S2": 8, "S3": 9}
    got = a.index_stream(123, sizes, resamples=50)
    rng = np.random.Generator(np.random.PCG64(123))
    for cell in ("N", "L", "S1", "S2", "S3"):
        want = rng.integers(0, sizes[cell], size=(50, sizes[cell]), dtype=np.int64)
        assert np.array_equal(got[cell], want), cell
    assert a.CELLS == ("N", "L", "S1", "S2", "S3")
    assert a.RESAMPLES == 10_000


def test_numpys_stream_is_the_frozen_one() -> None:
    a.assert_stream_pinned()
    sizes = dict.fromkeys(a.CELLS, a.GOLDEN_N)
    assert a.stream_digest(a.index_stream(a.GOLDEN_SEED, sizes)) == a.GOLDEN_DIGEST


def test_a_cell_needs_two_replicates() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        a.index_stream(1, {"N": 1, "L": 2, "S1": 2, "S2": 2, "S3": 2})


# -- means and BCa -------------------------------------------------------------------------------


def test_means_are_sequential_sums() -> None:
    values = np.array([1e16, 1.0, -1e16, 1.0])
    assert a.seq_mean(values) == ((((1e16 + 1.0) - 1e16) + 1.0) / 4)
    idx = np.array([[0, 1, 2, 3], [3, 2, 1, 0]], dtype=np.int64)
    means = a.resample_means(values, idx)
    assert means[0] == a.seq_mean(values)
    assert means[1] == a.seq_mean(values[::-1])


def test_every_value_equal_gives_that_value_exactly() -> None:
    values = np.full(7, 0.1)
    assert a.seq_mean(values) != 0.1  # the sequential mean drifts; the sealed rule does not
    boot = a.bootstrap(values, a.index_stream(5, dict.fromkeys(a.CELLS, 7), resamples=200)["N"])
    for alpha in (0.00625, 0.025, 0.05, 0.5, 0.95, 0.975):
        assert a.endpoint(boot, alpha) == 0.1


def test_the_jackknife_acceleration_worked_by_hand() -> None:
    # Leave-one-out means of [1, 2, 3, 10]: 5, 14/3, 13/3, 2; their mean 4; d = -1, -2/3, -1/3, 2.
    cubes = -1 - 8 / 27 - 1 / 27 + 8
    squares = 1 + 4 / 9 + 1 / 9 + 4
    want = cubes / (6 * squares * math.sqrt(squares))
    assert a.acceleration(np.array([1.0, 2.0, 3.0, 10.0])) == pytest.approx(want, rel=1e-14)
    assert a.acceleration(np.array([1.0, 2.0, 3.0, 10.0])) > 0  # a long right tail
    assert a.acceleration(np.array([3.0, 3.0, 3.0])) == 0.0


def test_a_symmetric_case_gives_the_percentile_interval() -> None:
    values = np.array([-1.0, 1.0])
    idx = _tiled([[0, 0], [0, 1], [1, 0], [1, 1]])
    boot = a.bootstrap(values, idx)
    assert boot.share == 0.5 and boot.z0 == 0.0 and boot.accel == 0.0
    for alpha in (0.025, 0.2, 0.8, 0.975):
        want = float(np.quantile(boot.means, alpha, method="linear"))
        assert a.endpoint(boot, alpha) == pytest.approx(want, abs=1e-12)


def test_ties_with_the_estimate_count_one_half() -> None:
    values = np.array([-1.0, 1.0, 0.0])
    idx = _tiled([[2, 2, 2], [0, 1, 2], [0, 0, 0], [1, 1, 2]])
    boot = a.bootstrap(values, idx)
    means = boot.means
    below = int(np.count_nonzero(means < boot.estimate))
    ties = int(np.count_nonzero(means == boot.estimate))
    assert ties == a.RESAMPLES // 2 and below == a.RESAMPLES // 4
    assert boot.share == (below + 0.5 * ties) / a.RESAMPLES == 0.5


def test_a_share_of_0_or_1_gives_the_extreme_resample_at_both_ends() -> None:
    values = np.array([0.0, 1.0])
    above = a.bootstrap(values, _tiled([[1, 1], [1, 0]]))  # every resample mean >= 0.5
    assert above.share == 0.25  # half the resamples tie: not yet extreme
    only_above = a.bootstrap(values, _tiled([[1, 1]]))
    assert only_above.share == 0.0
    assert a.endpoint(only_above, 0.025) == a.endpoint(only_above, 0.975) == 1.0
    only_below = a.bootstrap(values, _tiled([[0, 0]]))
    assert only_below.share == 1.0
    assert a.endpoint(only_below, 0.025) == a.endpoint(only_below, 0.975) == 0.0


def test_past_the_pole_an_upper_end_takes_level_1_and_a_lower_end_level_0() -> None:
    means = np.arange(100.0)
    upper = a.Boot(estimate=60.0, means=means, share=0.6, z0=1.5, accel=0.5, constant=None)
    assert 1.0 - 0.5 * (1.5 + a._NORMAL.inv_cdf(0.975)) <= 0  # the pole is passed
    assert a.endpoint(upper, 0.975) == 99.0  # unguarded, the formula would give about 0.06
    lower = a.Boot(estimate=40.0, means=means, share=0.4, z0=-1.5, accel=-0.5, constant=None)
    assert a.endpoint(lower, 0.025) == 0.0


def test_the_two_sided_95_interval_is_the_0_025_and_0_975_endpoints() -> None:
    rng = np.random.default_rng(7)
    values = rng.gamma(2.0, 3.0, size=40)
    boot = a.bootstrap(values, a.index_stream(9, dict.fromkeys(a.CELLS, 40))["S1"])
    assert a.interval95(boot) == (a.endpoint(boot, 0.025), a.endpoint(boot, 0.975))
    low, high = a.interval95(boot)
    assert low < boot.estimate < high


def test_bca_equals_scipys_given_the_same_bootstrap_distribution() -> None:
    stats = pytest.importorskip("scipy.stats")
    from scipy.stats._resampling import BootstrapResult

    def seq(x: F64, axis: int = -1) -> Any:
        moved = np.moveaxis(x, axis, -1)
        return np.cumsum(moved, axis=-1)[..., -1] / moved.shape[-1]

    rng = np.random.default_rng(20261124)
    checked = 0
    for case in range(20):
        n = int(rng.integers(8, 60))
        values = rng.gamma(0.7 + case / 10, 2.0, size=n) - 1.0
        idx = a.index_stream(1000 + case, dict.fromkeys(a.CELLS, n), resamples=4000)["L"]
        boot = a.bootstrap(values, idx)
        if boot.share in (0.0, 1.0):
            continue
        prior = BootstrapResult(
            confidence_interval=None, bootstrap_distribution=boot.means, standard_error=None
        )
        res = stats.bootstrap(
            (values,),
            seq,
            n_resamples=0,
            bootstrap_result=prior,
            method="BCa",
            confidence_level=0.95,
            vectorized=True,
        )
        low, high = a.interval95(boot)
        assert res.confidence_interval.low == pytest.approx(low, rel=1e-12, abs=1e-12)
        assert res.confidence_interval.high == pytest.approx(high, rel=1e-12, abs=1e-12)
        checked += 1
    assert checked >= 15


# -- Holm, the claims and the marks --------------------------------------------------------------


def test_holm_steps_down_as_sealed() -> None:
    def at_least(h: int) -> Any:
        return lambda gamma: gamma >= 0.025 / h

    rejected, steps = a.holm(
        {"A": at_least(4), "B": at_least(3), "C": at_least(2), "D": lambda gamma: False}
    )
    assert rejected == {"A", "B", "C"}
    assert [s["h"] for s in steps] == [4, 3, 2, 1]
    assert [s["rejected"] for s in steps] == [["A"], ["B"], ["C"], []]
    none, only = a.holm({"A": lambda g: False, "B": lambda g: False})
    assert none == frozenset() and len(only) == 1


def _arm(cost: F64, fill: F64 | None = None, wasted: F64 | None = None) -> a.Arm:
    n = cost.size
    return a.Arm(
        cost=cost,
        fill=np.full(n, 0.9) if fill is None else fill,
        lost=np.full(n, 100.0),
        wasted=np.full(n, 500.0) if wasted is None else wasted,
        held=np.full(n, 1000.0),
        end_on_hand=np.full(n, 10.0),
    )


def _runs(
    gain: dict[str, float], fill_drop: dict[str, float] | None = None, waste_cut_l: float = 0.0
) -> dict[str, a.CellRun]:
    rng = np.random.default_rng(3)
    out: dict[str, a.CellRun] = {}
    for cell in a.CELLS:
        base = 200.0 + rng.normal(0.0, 5.0, size=200)
        noise = rng.normal(0.0, 1.0, size=200)
        syn_cost = base - gain.get(cell, 0.0) + noise
        syn_fill = np.full(200, 0.9) - (fill_drop or {}).get(cell, 0.0) + noise / 1000
        syn_waste = np.full(200, 500.0) - (waste_cut_l if cell == "L" else 0.0) + noise
        out[cell] = a.CellRun(
            margin=15.0,
            incumbent=_arm(base),
            synapse=_arm(syn_cost, syn_fill, syn_waste),
            lane=_arm(base),
            ablations={"surge": _arm(syn_cost + 0.5), "lanes": _arm(syn_cost + 40.0)},
            clipped=3,
            decisions=100,
        )
    return out


def test_c1_holds_only_when_every_cell_passes_both_parts() -> None:
    assert a.analyse(_runs({}), seed=11)["C1"] is True
    worse = a.analyse(_runs({"S2": -20.0}), seed=11)
    assert worse["C1"] is False
    assert worse["cells"]["S2"]["c1"]["cost_upper_below_margin"] is False
    assert all(worse["cells"][c]["c1"]["passes"] for c in a.CELLS if c != "S2")
    thin = a.analyse(_runs({}, fill_drop={"N": 0.02}), seed=11)
    assert thin["C1"] is False and thin["cells"]["N"]["c1"]["fill_lower_above_floor"] is False


def test_c2_and_c3_on_data_whose_answer_is_known() -> None:
    # 300 units fewer over 7 days at cost 0.62: 26.6 a store-day, clear of M_L = 15.
    report = a.analyse(_runs({"S1": 30.0}, waste_cut_l=300.0), seed=11)
    holm = report["holm"]
    assert holm["C2_cells"] == {"S1": True, "S2": False, "S3": False}
    assert holm["C2"] is True and holm["C3"] is True
    # A gain of 15.05 against 15: over the margin, but its bound (SE about 0.07) is not.
    flat = a.analyse(_runs({"S1": 15.05}), seed=11)["holm"]
    assert flat["C2"] is False and flat["C3"] is False


def test_the_autonomy_mark_and_the_ablations() -> None:
    report = a.analyse(_runs({"S1": 30.0}), seed=11)
    assert report["cells"]["S1"]["autonomy"]["against_cell_incumbent"] is True
    assert report["cells"]["N"]["autonomy"]["against_cell_incumbent"] is False  # no gain: upper > 0
    assert report["ablations"]["surge"]["no_measured_effect"] is True  # 0.5 inside (-15, 15)
    assert report["ablations"]["lanes"]["no_measured_effect"] is False  # 40 outside
    assert report["cells"]["S1"]["clipped_share"] == 0.03
    assert len(report["cells"]["N"]["band"]) == 27


def test_replicates_per_cell_follow_prereg_1_section_6() -> None:
    assert a.replicates_for(0.0, 14.527) == 200
    assert a.replicates_for(1.0, 14.527) == 200
    ratio = 2 * 1.96 * 60.0 / 14.527
    assert a.replicates_for(60.0, 14.527) == math.ceil(ratio * ratio) == 263
    assert a.replicates_for(1000.0, 14.527) == 2000


def test_the_sample_sd_divides_by_n_minus_1() -> None:
    assert a.sample_sd([1.0, 2.0, 3.0, 4.0]) == pytest.approx(math.sqrt(5 / 3), rel=1e-15)
    with pytest.raises(ValueError):
        a.sample_sd([1.0])
