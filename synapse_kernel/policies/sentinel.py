"""The Sentinel alone: SYNAPSE's decision core as the eight-agent consensus arm applies it.

Truth program session 5, stage A (decision S3-D-05). What is ported, rule for rule and in the
legacy order of floating-point operations:

* the request the consensus arm builds for the Inventory Sentinel, only the keys the Sentinel
  reads (``uplift/consensus_arm.py::observation_to_decision_request``);
* how the Sentinel reads that request (``agents/inventory_sentinel/inference/request_state.py::
  forecast_from_request``): demand rate since the run began, the mean landed lead time of the SKU's
  supplier or a one-day prior, a 60-minute review period, a Poisson spread;
* its decision (``agents/inventory_sentinel/inference/pipeline.py::decide``): the newsvendor
  quantity at the critical fractile 8/9 (``models/newsvendor.py``, Acklam's inverse normal, whose
  central branch is a rational function, so no transcendental function is called), less the
  position, rounded to two decimals; ``decide()``'s defaults (mean 10, spread 3) for a SKU with no
  observed demand yet;
* the consensus arm's translation of the binding proposal into reorder quantities.

Measured in session 5 (record S5-M-06, then this module's tests): on E5's twelve replicate seeds the
eight-agent consensus arm costs exactly what this rule costs, seed by seed, as ``float.hex``; the
Sentinel binds every decision there (truth finding F-01) and nothing downstream of its proposal
changes a quantity. So the browser can show SYNAPSE's measured decisions without the agent stack.

The rule runs on the LEGACY world only: it is a component of what session 6 builds, and nothing of
SYNAPSE runs on the release world before freeze W. :meth:`SentinelAlone.decide` therefore accepts
only the legacy :class:`~synapse_kernel.observation.Observation`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from synapse_kernel.observation import Observation, PolicyAction

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "COST_OVER",
    "COST_UNDER",
    "DEFAULT_MEAN",
    "DEFAULT_STD",
    "LEAD_TIME_PRIOR_MIN",
    "REVIEW_PERIOD_MIN",
    "SentinelAlone",
    "critical_fractile",
    "inverse_normal",
    "newsvendor_quantity",
]

#: ``request_state.MINUTES_PER_DAY``.
MINUTES_PER_DAY: Final[float] = 1440.0
#: ``request_state.REVIEW_PERIOD_MIN``: the review period R, in minutes.
REVIEW_PERIOD_MIN: Final[float] = 60.0
#: ``pipeline.DEFAULT_LEAD_TIME_DAYS`` (1.0) in minutes: the lead time planned for a supplier none
#: of whose orders has landed (``request_state.LEAD_TIME_PRIOR_MIN``).
LEAD_TIME_PRIOR_MIN: Final[float] = 1.0 * MINUTES_PER_DAY
#: ``request_state.MIN_EVENTS_FOR_RATE``.
MIN_EVENTS_FOR_RATE: Final[int] = 1
#: ``decide()``'s forecast for a SKU whose entry carries no mean or spread (``pipeline.py``).
DEFAULT_MEAN: Final[float] = 10.0
DEFAULT_STD: Final[float] = 3.0
#: ``pipeline.decide`` floors the spread at this value.
STD_FLOOR: Final[float] = 1e-3
#: ``NewsvendorParams`` defaults (``models/newsvendor.py``): the agent's own costs.
COST_UNDER: Final[float] = 8.0
COST_OVER: Final[float] = 1.0

# Acklam's coefficients, as ``models/newsvendor.py::_inv_norm_cdf`` states them.
_A: Final[tuple[float, ...]] = (
    -3.969683028665376e1,
    2.209460984245205e2,
    -2.759285104469687e2,
    1.383577518672690e2,
    -3.066479806614716e1,
    2.506628277459239e0,
)
_B: Final[tuple[float, ...]] = (
    -5.447609879822406e1,
    1.615858368580409e2,
    -1.556989798598866e2,
    6.680131188771972e1,
    -1.328068155288572e1,
)
_C: Final[tuple[float, ...]] = (
    -7.784894002430293e-3,
    -3.223964580411365e-1,
    -2.400758277161838e0,
    -2.549732539343734e0,
    4.374664141464968e0,
    2.938163982698783e0,
)
_D: Final[tuple[float, ...]] = (
    7.784695709041462e-3,
    3.224671290700398e-1,
    2.445134137142996e0,
    3.754408661907416e0,
)
_P_LOW: Final[float] = 0.02425


def critical_fractile(cost_under: float = COST_UNDER, cost_over: float = COST_OVER) -> float:
    """``c_u / (c_u + c_o)`` (``NewsvendorParams.critical_fractile``)."""
    return cost_under / (cost_under + cost_over)


def inverse_normal(p: float) -> float:
    """Acklam's inverse normal CDF, step for step as ``newsvendor._inv_norm_cdf`` computes it.

    Raises:
        ValueError: If ``p`` is not strictly inside ``(0, 1)``.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1); got {p}")
    a, b, c, d = _A, _B, _C, _D
    p_high = 1 - _P_LOW
    if p < _P_LOW:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def newsvendor_quantity(mean: float, std: float, fractile: float) -> float:
    """``max(0, mean + z * std)`` with ``z`` the inverse normal at ``fractile``."""
    return max(0.0, mean + inverse_normal(fractile) * std)


class SentinelAlone:
    """The Inventory Sentinel's reorder rule as the consensus arm applies it, alone.

    Stateless: each decision reads only the observation in hand, as the legacy request does.
    """

    name: str = "sentinel_alone"

    def __init__(self) -> None:
        self._fractile = critical_fractile()

    def quantities(self, obs: Observation) -> dict[str, float]:
        """The reorder quantity per stocked SKU, zeros included, in sorted SKU order.

        Raises:
            TypeError: ``obs`` is not the legacy world's observation (the rule does not run on the
                release world before freeze W).
            ValueError: A state the legacy request reader refuses (a negative or non-finite
                level, a non-positive landed lead time, a forecast that overflows).
        """
        if type(obs) is not Observation:
            raise TypeError(
                f"the Sentinel alone runs on the legacy world's Observation only, not "
                f"{type(obs).__name__}: nothing of SYNAPSE runs on the release world "
                "before freeze W"
            )
        skus = sorted(obs.inventory)
        position = {
            sku: float(obs.inventory[sku]) + float(obs.on_order.get(sku, 0.0)) for sku in skus
        }
        for sku, level in position.items():
            if not math.isfinite(level) or level < 0.0:
                raise ValueError(f"inventory_position[{sku!r}] = {level!r} is not a stock level")
        exposure = float(obs.sim_time)
        if not math.isfinite(exposure) or exposure < 0.0:
            raise ValueError(f"sim_time = {exposure!r} is not an elapsed time")
        landed = _landed(obs.supplier_lead_time_history)
        out: dict[str, float] = {}
        for sku in skus:
            on_hand = position[sku]
            lead_time = _lead_time(obs.sku_supplier.get(sku), landed)
            observed = float(int(obs.demand_to_date.get(sku, 0)))
            if exposure > 0.0 and observed >= MIN_EVENTS_FOR_RATE:
                mean = observed / exposure * (lead_time + REVIEW_PERIOD_MIN)
                std = math.sqrt(mean)
                if not (math.isfinite(mean) and math.isfinite(std)):
                    raise ValueError(f"the forecast for {sku!r} overflows (mean {mean!r})")
            else:
                mean, std = DEFAULT_MEAN, DEFAULT_STD
            std = max(STD_FLOOR, std)
            q_star = newsvendor_quantity(mean, std, self._fractile)
            out[sku] = 0.0 + round(float(max(0.0, q_star - on_hand)), 2)
        return out

    def decide(self, obs: Observation) -> PolicyAction:
        """The consensus arm's action when the Sentinel binds: every SKU's reorder quantity."""
        return PolicyAction(reorder_quantities=self.quantities(obs))


def _landed(history: Mapping[str, tuple[float, ...]]) -> dict[str, tuple[float, ...]]:
    """Each supplier's landed lead times, each finite and > 0, as the request reader demands."""
    out: dict[str, tuple[float, ...]] = {}
    for supplier in sorted(history):
        times = tuple(float(minutes) for minutes in history[supplier])
        if any(not math.isfinite(minutes) or minutes <= 0.0 for minutes in times):
            raise ValueError(f"supplier {supplier!r} reports a landed lead time that is not > 0")
        out[supplier] = times
    return out


def _lead_time(supplier: str | None, landed: Mapping[str, tuple[float, ...]]) -> float:
    """The mean landed lead time of ``supplier``, or :data:`LEAD_TIME_PRIOR_MIN` (minutes)."""
    times = () if supplier is None else landed.get(supplier, ())
    if not times:
        return LEAD_TIME_PRIOR_MIN
    return math.fsum(times) / len(times)
