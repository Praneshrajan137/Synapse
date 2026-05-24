"""Newsvendor + conformal calibration — L1 reorder-quantity policy.

Closed-form optimum for the single-period newsvendor problem:

    Q* = F⁻¹( c_u / (c_u + c_o) )

where c_u = under-stocking cost (lost sale + goodwill) and c_o = over-stocking
cost (carrying + spoilage). For perishable quick-commerce SKUs c_u typically
dominates (5-10×) so the critical fractile sits at .85-.95.

Conformal calibration (ADR-009): we wrap Q* in a [Q_lower, Q_upper] interval
calibrated on a holdout so that empirical coverage ≥ 1-α (typically α = .1).
The pipeline orders Q_upper for high-confidence demand bursts (essentials,
holidays) and Q* otherwise, with the bandit picking the safety multiplier on
top.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NewsvendorParams:
    cost_under: float = 8.0
    cost_over: float = 1.0

    @property
    def critical_fractile(self) -> float:
        return self.cost_under / (self.cost_under + self.cost_over)


_DEFAULT_NEWSVENDOR_PARAMS = NewsvendorParams()


def newsvendor_quantity(
    forecast_mean: float,
    forecast_std: float,
    params: NewsvendorParams | None = None,
) -> float:
    """Closed-form Q* for a Normal demand distribution."""

    params = params if params is not None else _DEFAULT_NEWSVENDOR_PARAMS
    p = params.critical_fractile
    # Inverse normal CDF via Acklam's approximation — pure stdlib.
    z = _inv_norm_cdf(p)
    return max(0.0, forecast_mean + z * forecast_std)


def _inv_norm_cdf(p: float) -> float:
    """Acklam's approximation. Accurate to ~1e-9. Avoids scipy dependency."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"p must be in (0, 1); got {p}")
    a = [
        -3.969683028665376e1,
        2.209460984245205e2,
        -2.759285104469687e2,
        1.383577518672690e2,
        -3.066479806614716e1,
        2.506628277459239e0,
    ]
    b = [
        -5.447609879822406e1,
        1.615858368580409e2,
        -1.556989798598866e2,
        6.680131188771972e1,
        -1.328068155288572e1,
    ]
    c = [
        -7.784894002430293e-3,
        -3.223964580411365e-1,
        -2.400758277161838e0,
        -2.549732539343734e0,
        4.374664141464968e0,
        2.938163982698783e0,
    ]
    d_ = [
        7.784695709041462e-3,
        3.224671290700398e-1,
        2.445134137142996e0,
        3.754408661907416e0,
    ]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = (-2 * _ln(p)) ** 0.5
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d_[0] * q + d_[1]) * q + d_[2]) * q + d_[3]) * q + 1)
        )
    if p > phigh:
        q = (-2 * _ln(1 - p)) ** 0.5
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d_[0] * q + d_[1]) * q + d_[2]) * q + d_[3]) * q + 1)
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def _ln(x: float) -> float:
    from math import log

    return log(x)


def conformal_bounds(
    forecast: np.ndarray,
    residuals: np.ndarray,
    alpha: float = 0.1,
) -> tuple[float, float]:
    """Symmetric split-conformal bounds on a point forecast.

    `residuals` are |y_true − ŷ| on a held-out calibration set; the (1-α)
    empirical quantile gives the half-width.
    """
    if len(residuals) == 0:
        return float(forecast.mean()), float(forecast.mean())
    q = float(np.quantile(np.abs(residuals), 1 - alpha, method="higher"))
    pt = float(forecast.mean())
    return pt - q, pt + q


def reorder_point(
    forecast_mean: float,
    forecast_std: float,
    lead_time_days: float,
    safety_multiplier: float,
) -> float:
    """ROP = μ·L + safety_mult·σ·√L."""
    return max(
        0.0,
        forecast_mean * lead_time_days
        + safety_multiplier * forecast_std * (lead_time_days**0.5),
    )


__all__ = [
    "NewsvendorParams",
    "conformal_bounds",
    "newsvendor_quantity",
    "reorder_point",
]
