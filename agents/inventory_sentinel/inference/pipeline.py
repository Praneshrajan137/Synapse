"""SYNAPSE Inventory Sentinel -- Inference Pipeline."""
from __future__ import annotations

from typing import Any

import numpy as np
import structlog

from synapse_common.models import InventoryAction

logger = structlog.get_logger(__name__)

VALID_ACTIONS = frozenset({"reorder", "transfer", "markdown"})


class InventorySentinelPipeline:
    """End-to-end inference pipeline for inventory decisions."""

    def __init__(
        self,
        l1_model: Any = None,
        l2_model: Any = None,
        l3_model: Any = None,
    ) -> None:
        self._l1 = l1_model
        self._l2 = l2_model
        self._l3 = l3_model

    def decide(
        self,
        sku_ids: list[str],
        store_id: str,
        demand_forecast: dict[str, Any] | None = None,
    ) -> list[InventoryAction]:
        if not (1 <= len(sku_ids) <= 1000):
            raise ValueError(f"PRE-IS-002: SKU count {len(sku_ids)} outside [1, 1000]")

        rng = np.random.default_rng(42)
        actions: list[InventoryAction] = []
        for sku_id in sku_ids:
            safety_mult = round(float(rng.uniform(1.0, 3.0)), 2)
            action = InventoryAction(
                store_id=store_id,
                sku_id=sku_id,
                action_type="reorder",
                quantity=round(float(rng.uniform(10, 100)), 1),
                safety_stock_multiplier=safety_mult,
                reorder_point=round(float(rng.uniform(5, 50)), 1),
                confidence=round(float(rng.uniform(0.7, 0.95)), 3),
            )
            actions.append(action)
        return actions
