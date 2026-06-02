"""SYNAPSE Freshness Guardian — Model components.

``shelf_life`` imports lifelines at module load. To keep the serving path
(numpy Weibull reconstruction) lifelines-free, the shelf-life symbols are exposed
lazily (PEP 562 ``__getattr__``): importing this package — or ``markdown`` through
it — never imports lifelines, but ``from ...models import ShelfLifeModel`` still
works on demand (ADR-043).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agents.freshness_guardian.models.markdown import DynamicMarkdownEngine, MarkdownDecision

if TYPE_CHECKING:
    from agents.freshness_guardian.models.shelf_life import ShelfLifeModel, ShelfLifePrediction

__all__ = ["DynamicMarkdownEngine", "MarkdownDecision", "ShelfLifeModel", "ShelfLifePrediction"]

_LAZY = {"ShelfLifeModel", "ShelfLifePrediction"}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from agents.freshness_guardian.models import shelf_life

        return getattr(shelf_life, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
