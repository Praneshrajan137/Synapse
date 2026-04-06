"""
SYNAPSE Freshness Guardian — Dynamic Markdown Engine.
Computes optimal markdown percentage based on remaining shelf life,
quality score, current stock level, and demand forecast.

INV-FG-002: days_to_expiry = 0 -> markdown_applied = True
INV-FG-004: markdown_pct increases monotonically as days_to_expiry decreases
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

_URGENCY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_urgency(a: str, b: str) -> str:
    """Return the higher urgency level using explicit ordering."""
    return a if _URGENCY_ORDER.get(a, 0) >= _URGENCY_ORDER.get(b, 0) else b


@dataclass
class MarkdownDecision:
    """Markdown pricing decision."""

    markdown_applied: bool
    markdown_pct: float
    reason: str
    urgency: str


class DynamicMarkdownEngine:
    """Rule-based + learned markdown engine.

    Markdown tiers (INV-FG-004 compliant — monotonically increasing):
    - shelf_ratio > 0.75:   0% (fresh)
    - 0.50 < ratio <= 0.75: 10%
    - 0.25 < ratio <= 0.50: 20%
    - 0.10 < ratio <= 0.25: 30%
    - 0.03 < ratio <= 0.10: 50%
    - 0.00 < ratio <= 0.03: 70% (last day)
    - ratio = 0:            100% write-off (INV-FG-002)

    The RL agent can only INCREASE markdowns, never decrease below tier floor.
    """

    def __init__(self) -> None:
        self._tiers: list[tuple[float, float]] = [
            (0.75, 0.0),
            (0.50, 10.0),
            (0.25, 20.0),
            (0.10, 30.0),
            (0.03, 50.0),
            (0.00, 70.0),
        ]

    def compute_markdown(
        self,
        days_to_expiry: float,
        initial_shelf_life_days: float,
        quality_score: float,
        current_stock: int,
        daily_demand_forecast: float,
    ) -> MarkdownDecision:
        """Compute optimal markdown percentage."""
        if days_to_expiry <= 0:
            return MarkdownDecision(
                markdown_applied=True,
                markdown_pct=100.0,
                reason="Item expired — full write-off (INV-FG-002)",
                urgency="critical",
            )

        shelf_ratio = min(days_to_expiry / max(initial_shelf_life_days, 1), 1.0)

        base_markdown = 0.0
        for upper_bound, pct in self._tiers:
            if shelf_ratio <= upper_bound:
                base_markdown = pct
            else:
                break

        urgency = "low"

        days_of_stock = current_stock / max(daily_demand_forecast, 0.1)
        if days_of_stock > days_to_expiry * 1.5 and days_to_expiry > 0:
            overstock_factor = min((days_of_stock / days_to_expiry) - 1.0, 1.0)
            base_markdown = min(base_markdown + overstock_factor * 15, 70.0)
            urgency = _max_urgency(urgency, "high")

        if quality_score < 0.3:
            base_markdown = max(base_markdown, 50.0)
            urgency = _max_urgency(urgency, "critical")
        elif quality_score < 0.5:
            base_markdown = max(base_markdown, 30.0)
            urgency = _max_urgency(urgency, "high")

        if days_to_expiry <= 1:
            urgency = _max_urgency(urgency, "critical")
        elif days_to_expiry <= 3:
            urgency = _max_urgency(urgency, "high")
        elif days_to_expiry <= 7:
            urgency = _max_urgency(urgency, "medium")

        markdown_applied = base_markdown > 0

        reason = (
            f"Shelf ratio: {shelf_ratio:.2f}, quality: {quality_score:.2f}, "
            f"stock days: {days_of_stock:.1f}, remaining: {days_to_expiry:.1f}d"
        )

        return MarkdownDecision(
            markdown_applied=markdown_applied,
            markdown_pct=float(base_markdown),
            reason=reason,
            urgency=urgency,
        )
