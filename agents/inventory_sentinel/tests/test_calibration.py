"""Calibration-truth for inventory_sentinel's newsvendor conformal interval (C40).

The newsvendor Q* is closed-form optimal (no gradient loop — the analytical
branch of the ADR-042 training contract), so its substance is proven by interval
coverage, not a loss curve. This shows the split-conformal bounds achieve nominal
coverage on held-out data. Pure numpy.
"""

from __future__ import annotations

import numpy as np

from agents.inventory_sentinel.models.newsvendor import conformal_bounds


def test_conformal_bounds_achieve_nominal_coverage() -> None:
    """Held-out coverage of [pt - q, pt + q] meets the 1 - alpha target."""
    rng = np.random.default_rng(42)
    alpha = 0.1

    # A point forecaster with N(0, sigma) error; calibrate on one split, test on another.
    sigma = 5.0
    cal_truth = rng.normal(50.0, sigma, size=4000)
    cal_forecast = cal_truth + rng.normal(0.0, sigma, size=4000)
    cal_residuals = cal_truth - cal_forecast

    test_truth = rng.normal(50.0, sigma, size=4000)
    test_forecast_pt = test_truth + rng.normal(0.0, sigma, size=4000)

    # Half-width from calibration residuals.
    lower, upper = conformal_bounds(np.array([0.0]), cal_residuals, alpha=alpha)
    q = (upper - lower) / 2.0  # symmetric

    covered = np.mean(np.abs(test_truth - test_forecast_pt) <= q)
    assert covered >= 1 - alpha - 0.03, f"held-out coverage {covered:.3f} below nominal"


def test_wider_residuals_give_wider_interval() -> None:
    """More uncertain residuals → wider conformal half-width (monotone)."""
    tight = conformal_bounds(np.array([10.0]), np.array([0.1, -0.2, 0.15, -0.1]), alpha=0.1)
    wide = conformal_bounds(np.array([10.0]), np.array([5.0, -6.0, 4.5, -5.5]), alpha=0.1)
    tight_w = tight[1] - tight[0]
    wide_w = wide[1] - wide[0]
    assert wide_w > tight_w


def test_empty_residuals_degrade_to_point() -> None:
    lo, hi = conformal_bounds(np.array([12.0, 14.0]), np.array([]), alpha=0.1)
    assert lo == hi == 13.0  # mean of the forecast, zero width (honest no-info)
