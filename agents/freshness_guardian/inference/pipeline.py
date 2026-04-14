"""
SYNAPSE Freshness Guardian — Inference Pipeline.
Processes freshness assessment requests and produces FreshnessAlert outputs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from agents.freshness_guardian.models.markdown import DynamicMarkdownEngine
from agents.freshness_guardian.models.shelf_life import ShelfLifeModel

logger = structlog.get_logger(__name__)


class FreshnessRequest(BaseModel):
    """Input request for freshness assessment."""

    store_id: str = Field(..., min_length=1)
    sku_id: str = Field(..., min_length=1)
    days_since_receipt: float = 0.0
    initial_shelf_life_days: float = Field(default=7.0, gt=0.0)
    temperature_deviation_hours: float = 0.0
    humidity_deviation_pct: float = 0.0
    is_cold_chain: bool = False
    current_stock: int = 50
    daily_demand_forecast: float = 10.0


class FreshnessAlert(BaseModel):
    """Output freshness alert — validates against freshness_alert.schema.json."""

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    store_id: str
    sku_id: str
    days_to_expiry: float
    quality_score: float = Field(ge=0.0, le=1.0)
    markdown_applied: bool
    markdown_pct: float = Field(ge=0.0, le=100.0)
    temperature_deviation_hours: float
    rebalance_recommended: bool
    target_store_id: str | None = None
    fssai_compliant: bool
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float = Field(ge=0.0, le=1.0)


class FreshnessGuardianPipeline:
    """End-to-end freshness assessment pipeline."""

    def __init__(
        self,
        shelf_life_model: Any | None = None,
        markdown_engine: Any | None = None,
    ) -> None:
        self.shelf_life_model = shelf_life_model or ShelfLifeModel()
        self.markdown_engine = markdown_engine or DynamicMarkdownEngine()

        if not self.shelf_life_model.fitted:
            training_data = self.shelf_life_model.generate_synthetic_training_data()
            self.shelf_life_model.fit(training_data)

    def assess(self, request: FreshnessRequest) -> FreshnessAlert:
        """Run full freshness assessment pipeline."""
        prediction = self.shelf_life_model.predict(
            sku_id=request.sku_id,
            store_id=request.store_id,
            temperature_deviation_hours=request.temperature_deviation_hours,
            humidity_deviation_pct=request.humidity_deviation_pct,
            initial_shelf_life_days=request.initial_shelf_life_days,
            is_cold_chain=request.is_cold_chain,
            days_since_receipt=request.days_since_receipt,
        )

        markdown = self.markdown_engine.compute_markdown(
            days_to_expiry=prediction.days_to_expiry,
            initial_shelf_life_days=request.initial_shelf_life_days,
            quality_score=prediction.quality_score,
            current_stock=request.current_stock,
            daily_demand_forecast=request.daily_demand_forecast,
        )

        fssai_compliant = request.temperature_deviation_hours <= 4.0

        rebalance = (
            prediction.quality_score > 0.5
            and request.current_stock > request.daily_demand_forecast * 3
            and prediction.days_to_expiry > 2
        )

        confidence = 0.85 if self.shelf_life_model.fitted else 0.5

        return FreshnessAlert(
            store_id=request.store_id,
            sku_id=request.sku_id,
            days_to_expiry=prediction.days_to_expiry,
            quality_score=prediction.quality_score,
            markdown_applied=markdown.markdown_applied,
            markdown_pct=markdown.markdown_pct,
            temperature_deviation_hours=request.temperature_deviation_hours,
            rebalance_recommended=rebalance,
            fssai_compliant=fssai_compliant,
            confidence=confidence,
        )
