"""SYNAPSE Inventory Sentinel — model components.

H-MARL agents (StrategicAgent / TacticalAgent / OperationalAgent) require
PyTorch and are imported lazily so callers that only need the lightweight
newsvendor + LinUCB policies do not pay the torch import cost.
"""

from agents.inventory_sentinel.models.l2_bandit import LinUCB
from agents.inventory_sentinel.models.newsvendor import (
    NewsvendorParams,
    conformal_bounds,
    newsvendor_quantity,
    reorder_point,
)


def __getattr__(name: str) -> object:  # pragma: no cover — lazy import shim
    if name in {"OperationalAgent", "StrategicAgent", "TacticalAgent"}:
        from importlib import import_module

        modmap = {
            "OperationalAgent": "operational",
            "StrategicAgent": "strategic",
            "TacticalAgent": "tactical",
        }
        return getattr(
            import_module(f"agents.inventory_sentinel.models.{modmap[name]}"),
            name,
        )
    raise AttributeError(name)


__all__ = [
    "LinUCB",
    "NewsvendorParams",
    "OperationalAgent",
    "StrategicAgent",
    "TacticalAgent",
    "conformal_bounds",
    "newsvendor_quantity",
    "reorder_point",
]
