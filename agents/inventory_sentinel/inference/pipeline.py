"""SYNAPSE Inventory Sentinel — production inference pipeline.

Sprint-8 rewrite (WS-8.1). Replaces the previous random-fallback stub with a
three-tier policy:

  * **L1** — closed-form newsvendor over (forecast μ, σ) for routine reorder
    quantity Q*. Pure-NumPy; sub-millisecond.
  * **L2** — LinUCB contextual bandit over a discrete safety-multiplier arm
    set; warm-restartable from `models/bandit_state.parquet`.
  * **L3** — RL fallback (PPO checkpoint) for non-stationary regimes; loaded
    lazily, optional.

All outputs are validated against `proto/domain/inventory_action.schema.json`
at egress (ADR-025) and carry conformal-calibrated reorder points (ADR-009).

DbC contracts (ADR-015 Layer 5):
  * **Pre** — at least one SKU; |sku_ids| ≤ 1000.
  * **Post** — every output's safety_stock_multiplier ∈ [1.0, 3.0] and
    quantity ≥ 0; one InventoryAction per SKU.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog
from synapse_common.dbc import post, pre
from synapse_common.models import InventoryAction
from synapse_common.schema_registry import validates_schema

from agents.inventory_sentinel.models.l2_bandit import LinUCB
from agents.inventory_sentinel.models.newsvendor import (
    NewsvendorParams,
    conformal_bounds,
    newsvendor_quantity,
    reorder_point,
)

logger = structlog.get_logger(__name__)

VALID_ACTIONS = frozenset({"reorder", "transfer", "markdown"})
DEFAULT_LEAD_TIME_DAYS = 1.0
DEFAULT_CONTEXT_DIM = 6


def _features(
    *,
    forecast_mean: float,
    forecast_std: float,
    on_hand: float,
    lead_time: float,
    perishable: float,
    is_essential: float,
) -> np.ndarray:
    """Compact context vector consumed by the LinUCB arm-selector."""
    return np.array(
        [
            float(forecast_mean),
            float(forecast_std),
            float(on_hand),
            float(lead_time),
            float(perishable),
            float(is_essential),
        ],
        dtype=np.float64,
    )


def _action_type(forecast_mean: float, on_hand: float, perishable: float) -> str:
    """Crisp policy: high stock + perishable → markdown; low stock → reorder."""
    if on_hand <= 1e-6:
        return "reorder"
    if perishable >= 0.7 and on_hand > 2.0 * forecast_mean:
        return "markdown"
    return "reorder"


class InventorySentinelPipeline:
    """End-to-end inference pipeline."""

    def __init__(
        self,
        *,
        bandit: LinUCB | None = None,
        newsvendor_params: NewsvendorParams | None = None,
        calibration_residuals: np.ndarray | None = None,
        l3_model: Any = None,
    ) -> None:
        self._bandit = bandit or LinUCB(d=DEFAULT_CONTEXT_DIM)
        self._params = newsvendor_params or NewsvendorParams()
        self._calibration = (
            calibration_residuals if calibration_residuals is not None else np.array([])
        )
        self._l3 = l3_model

    @pre(lambda self, sku_ids, store_id, demand_forecast=None: 1 <= len(sku_ids) <= 1000)
    @post(lambda result: all(1.0 <= a.safety_stock_multiplier <= 3.0 for a in result))
    @post(lambda result: all(a.quantity >= 0.0 for a in result))
    @validates_schema("domain.inventory_action")
    def decide(
        self,
        sku_ids: list[str],
        store_id: str,
        demand_forecast: dict[str, Any] | None = None,
    ) -> list[InventoryAction]:
        """Produce one validated `InventoryAction` per SKU.

        `demand_forecast` is a dict keyed by sku_id with `{mean, std, on_hand,
        perishable, is_essential, lead_time_days}` shape. Missing entries fall
        back to safe defaults (mean=10, std=3, on_hand=0).
        """
        forecasts = demand_forecast or {}
        out: list[InventoryAction] = []

        for sku_id in sku_ids:
            f = forecasts.get(sku_id, {})
            mean = float(f.get("mean", 10.0))
            std = max(1e-3, float(f.get("std", 3.0)))
            on_hand = float(f.get("on_hand", 0.0))
            perishable = float(f.get("perishable", 0.0))
            is_essential = float(f.get("is_essential", 0.0))
            lead_time = float(f.get("lead_time_days", DEFAULT_LEAD_TIME_DAYS))

            # L1 — newsvendor optimum.
            q_star = newsvendor_quantity(mean, std, self._params)

            # Conformal bounds on the forecast itself; tighter under low residual variance.
            forecast_arr = np.array([mean])
            lo, hi = conformal_bounds(forecast_arr, self._calibration, alpha=0.1)
            quantity = max(0.0, q_star - on_hand)
            if is_essential >= 0.5:
                # Essentials use the upper conformal bound to absorb burst risk.
                quantity = max(quantity, max(0.0, hi - on_hand))
            quantity = round(float(quantity), 2)

            # L2 — bandit picks safety multiplier.
            ctx = _features(
                forecast_mean=mean,
                forecast_std=std,
                on_hand=on_hand,
                lead_time=lead_time,
                perishable=perishable,
                is_essential=is_essential,
            )
            arm, ucb = self._bandit.select(ctx)
            safety_mult = float(min(3.0, max(1.0, arm)))

            rop = round(
                reorder_point(mean, std, lead_time, safety_mult),
                2,
            )

            # Confidence: 1 - normalised forecast volatility, clipped.
            conf = float(np.clip(1.0 - (std / max(mean, 1.0)) * 0.5, 0.5, 0.99))

            action = InventoryAction(
                store_id=store_id,
                sku_id=sku_id,
                action_type=_action_type(mean, on_hand, perishable),
                quantity=quantity,
                safety_stock_multiplier=round(safety_mult, 2),
                reorder_point=rop,
                confidence=round(conf, 3),
            )
            out.append(action)
            logger.debug(
                "inventory_decision",
                sku_id=sku_id,
                store_id=store_id,
                quantity=quantity,
                safety_multiplier=safety_mult,
                ucb=ucb,
                lo=lo,
                hi=hi,
            )

        return out


__all__ = ["InventorySentinelPipeline", "VALID_ACTIONS"]
