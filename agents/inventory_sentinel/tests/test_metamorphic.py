"""SYNAPSE Inventory Sentinel — Metamorphic + Oracle tests (Layers 4 + 6).

Sprint-8 elevation (WS-8.1): the pipeline now does real newsvendor + LinUCB
arithmetic, so the metamorphic relations check the *physics* of inventory
control, not just structural validity.

  * **MR-IS-001 (monotonicity in mean)** — higher demand mean → higher
    reorder quantity for the same on-hand and σ.
  * **MR-IS-002 (monotonicity in σ)** — higher demand variance → higher or
    equal reorder point (more safety stock needed).
  * **MR-IS-003 (essentials buffer)** — flagging an SKU as essential never
    *reduces* the recommended quantity at fixed forecast.
  * **MR-IS-004 (markdown threshold)** — when on_hand far exceeds forecast
    on a perishable, the action becomes 'markdown'.
  * **Oracle** — newsvendor closed-form matches its analytical Q* on a
    synthetic Normal demand fixture.
"""

from __future__ import annotations

import pytest

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline
from agents.inventory_sentinel.models.newsvendor import (
    NewsvendorParams,
    newsvendor_quantity,
)

pytestmark = pytest.mark.metamorphic


@pytest.fixture()
def pipeline() -> InventorySentinelPipeline:
    return InventorySentinelPipeline()


class TestMetamorphicRelations:
    def test_mr_is_001_quantity_monotone_in_mean(
        self, pipeline: InventorySentinelPipeline
    ) -> None:
        """Higher μ → higher (or equal) reorder quantity."""
        low = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={"SKU": {"mean": 5.0, "std": 1.0, "on_hand": 0}},
        )[0]
        high = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={"SKU": {"mean": 50.0, "std": 1.0, "on_hand": 0}},
        )[0]
        assert high.quantity >= low.quantity

    def test_mr_is_002_rop_monotone_in_sigma(
        self, pipeline: InventorySentinelPipeline
    ) -> None:
        """Higher σ → higher (or equal) reorder point."""
        steady = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={"SKU": {"mean": 20.0, "std": 1.0, "on_hand": 0}},
        )[0]
        volatile = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={"SKU": {"mean": 20.0, "std": 10.0, "on_hand": 0}},
        )[0]
        assert volatile.reorder_point >= steady.reorder_point

    def test_mr_is_003_essentials_buffer(
        self, pipeline: InventorySentinelPipeline
    ) -> None:
        """is_essential=1 produces ≥ baseline quantity."""
        baseline = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={
                "SKU": {"mean": 30.0, "std": 5.0, "on_hand": 0, "is_essential": 0.0}
            },
        )[0]
        essential = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={
                "SKU": {"mean": 30.0, "std": 5.0, "on_hand": 0, "is_essential": 1.0}
            },
        )[0]
        assert essential.quantity >= baseline.quantity

    def test_mr_is_004_markdown_on_overstocked_perishable(
        self, pipeline: InventorySentinelPipeline
    ) -> None:
        """on_hand >> demand for a perishable triggers markdown."""
        out = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={
                "SKU": {
                    "mean": 5.0,
                    "std": 1.0,
                    "on_hand": 50.0,
                    "perishable": 0.9,
                }
            },
        )[0]
        assert out.action_type == "markdown"

    def test_mr_is_005_quantity_drops_with_on_hand(
        self, pipeline: InventorySentinelPipeline
    ) -> None:
        """Increasing on_hand by Δ never increases reorder quantity."""
        empty = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={"SKU": {"mean": 30.0, "std": 5.0, "on_hand": 0}},
        )[0]
        stocked = pipeline.decide(
            ["SKU"],
            "STORE_BLR_001",
            demand_forecast={"SKU": {"mean": 30.0, "std": 5.0, "on_hand": 20.0}},
        )[0]
        assert stocked.quantity <= empty.quantity


@pytest.mark.oracle
class TestNewsvendorOracle:
    def test_q_star_matches_closed_form(self) -> None:
        """Q* must satisfy F(Q) = c_u/(c_u+c_o); for c_u=8, c_o=1 the fractile is .888."""
        params = NewsvendorParams(cost_under=8.0, cost_over=1.0)
        # For Normal(μ=10, σ=2) the .888 quantile ≈ 12.42.
        q = newsvendor_quantity(10.0, 2.0, params)
        assert 12.0 < q < 13.0

    def test_q_star_zero_variance_collapses_to_mean(self) -> None:
        params = NewsvendorParams()
        q = newsvendor_quantity(10.0, 1e-9, params)
        assert abs(q - 10.0) < 1e-3

    def test_q_star_higher_when_under_cost_dominates(self) -> None:
        cheap_overstock = newsvendor_quantity(10.0, 2.0, NewsvendorParams(8.0, 1.0))
        cheap_understock = newsvendor_quantity(10.0, 2.0, NewsvendorParams(1.0, 8.0))
        assert cheap_overstock > cheap_understock
