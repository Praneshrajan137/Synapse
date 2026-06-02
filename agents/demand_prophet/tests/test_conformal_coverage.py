"""Calibration-truth: split-conformal intervals achieve nominal coverage (C40).

The deepest substance check for demand_prophet — it proves the prediction
intervals are *real*, not decorative. We construct a deliberately MIS-calibrated
base predictor (its raw 90% interval covers far less than 90%), calibrate the
:class:`ConformalCalibrator` on a held-out calibration split, and assert the
recalibrated interval hits the nominal target on a *separate* test split.

This is the finite-sample manifestation of the split-conformal guarantee
(Gibbs & Candès / Conformalized Quantile Regression): regardless of how wrong the
base model's intervals are, conformal recalibration restores coverage. Pure
numpy — runs on any runner, no torch.
"""

from __future__ import annotations

import numpy as np

from agents.demand_prophet.training.conformal import ConformalCalibrator

HORIZONS = ["15min", "1h", "6h", "24h", "7d"]


def _miscalibrated_predictions(
    rng: np.random.Generator, n: int, *, true_mean: float = 20.0, true_sd: float = 6.0
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """A base model whose raw 90% band is far too NARROW (under-covers badly).

    Returns (predictions, actuals) where predictions[h] is (n, 3) = [lo, mid, hi]
    and the raw [lo, hi] band is ±0.3·sd → ~24% coverage, not 90%.
    """
    preds: dict[str, np.ndarray] = {}
    actuals: dict[str, np.ndarray] = {}
    for h in HORIZONS:
        truth = rng.normal(true_mean, true_sd, size=n)
        point = truth + rng.normal(0.0, 4.0, size=n)  # noisy point forecast
        narrow = 0.25 * true_sd  # band far too tight for that noise
        preds[h] = np.stack([point - narrow, point, point + narrow], axis=1)
        actuals[h] = truth
    return preds, actuals


def _empirical_coverage(
    intervals: dict[str, tuple[np.ndarray, np.ndarray]], actuals: dict[str, np.ndarray]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for h, (lo, hi) in intervals.items():
        out[h] = float(np.mean((actuals[h] >= lo) & (actuals[h] <= hi)))
    return out


def test_raw_intervals_undercover_badly() -> None:
    """Sanity: without calibration the base 90% band covers far below target."""
    rng = np.random.default_rng(7)
    preds, actuals = _miscalibrated_predictions(rng, 2000)
    raw = {h: (preds[h][:, 0], preds[h][:, 2]) for h in HORIZONS}
    cov = _empirical_coverage(raw, actuals)
    assert all(c < 0.5 for c in cov.values()), cov  # genuinely miscalibrated


def test_split_conformal_restores_nominal_coverage() -> None:
    """After conformal calibration, held-out coverage >= the 0.85 floor (INV-DP-002)."""
    rng = np.random.default_rng(42)
    cal_preds, cal_actuals = _miscalibrated_predictions(rng, 3000)
    test_preds, test_actuals = _miscalibrated_predictions(rng, 3000)

    calib = ConformalCalibrator(alpha=0.1, coverage_target=0.85)
    cal_coverage = calib.fit(cal_preds, cal_actuals)

    # Calibration-set coverage should already meet the nominal 1-alpha target.
    assert all(c >= 0.85 for c in cal_coverage.values()), cal_coverage

    # The real test: apply the SAME adjustments to UNSEEN data.
    test_intervals = calib.predict_intervals(test_preds)
    test_coverage = _empirical_coverage(test_intervals, test_actuals)
    for h, c in test_coverage.items():
        assert c >= 0.85, f"horizon {h}: held-out coverage {c:.3f} < 0.85 floor"


def test_last_coverage_p90_is_populated_and_in_range() -> None:
    """The serving pipeline reads last_coverage_p90; it must be a real [0,1] number."""
    rng = np.random.default_rng(1)
    preds, actuals = _miscalibrated_predictions(rng, 1500)
    calib = ConformalCalibrator(alpha=0.1)
    assert calib.last_coverage_p90 is None  # before fit
    calib.fit(preds, actuals)
    assert calib.last_coverage_p90 is not None
    assert 0.0 <= calib.last_coverage_p90 <= 1.0
    assert calib.last_coverage_p90 >= 0.85  # the calibrated aggregate
    assert set(calib.last_coverage_per_horizon) == set(HORIZONS)


def test_calibration_is_deterministic_under_seed() -> None:
    """Same data → same adjustments (determinism discipline)."""
    rng1 = np.random.default_rng(99)
    rng2 = np.random.default_rng(99)
    p1, a1 = _miscalibrated_predictions(rng1, 800)
    p2, a2 = _miscalibrated_predictions(rng2, 800)
    c1, c2 = ConformalCalibrator(), ConformalCalibrator()
    c1.fit(p1, a1)
    c2.fit(p2, a2)
    assert c1.get_adjustments() == c2.get_adjustments()
