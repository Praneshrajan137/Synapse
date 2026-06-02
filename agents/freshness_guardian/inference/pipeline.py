"""
SYNAPSE Freshness Guardian — Inference Pipeline.
Processes freshness assessment requests and produces FreshnessAlert outputs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, Field
from synapse_common.provenance import ConfidenceBasis, FeatureSource, Provenance

from agents.freshness_guardian.models.markdown import DynamicMarkdownEngine

# ShelfLifeModel imports lifelines at module load; imported lazily on the
# fit-per-process fallback so the serving path (numpy Weibull reconstruction) runs
# without the lifelines runtime (ADR-043).
if TYPE_CHECKING:
    from agents.freshness_guardian.inference.serving_model import FreshnessServingModel

logger = structlog.get_logger(__name__)

FALLBACK_CONFIDENCE = 0.5  # documented I-7 floor when no fitted survival model is present


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
        serving_model: FreshnessServingModel | None = None,
    ) -> None:
        # ADR-043: when the fitted Weibull-AFT params are resolved by serve.py via
        # ModelRegistry, prediction + confidence come from the numpy reconstruction
        # (no lifelines runtime). Otherwise fall back to the lifelines ShelfLifeModel
        # (lazy-imported + fit once), honestly degraded.
        self._serving_model = serving_model
        self.markdown_engine = markdown_engine or DynamicMarkdownEngine()
        self.shelf_life_model = shelf_life_model
        self.last_provenance: Provenance = Provenance.degraded_fallback()

        if self._serving_model is None and self.shelf_life_model is None:
            from agents.freshness_guardian.models.shelf_life import (  # noqa: PLC0415
                ShelfLifeModel,
            )

            self.shelf_life_model = ShelfLifeModel()
            if not self.shelf_life_model.fitted:
                self.shelf_life_model.fit(self.shelf_life_model.generate_synthetic_training_data())

    def assess(self, request: FreshnessRequest) -> FreshnessAlert:
        """Run full freshness assessment pipeline."""
        covariates = {
            "temperature_deviation_hours": request.temperature_deviation_hours,
            "humidity_deviation_pct": request.humidity_deviation_pct,
            "initial_shelf_life_days": request.initial_shelf_life_days,
            "is_cold_chain": 1.0 if request.is_cold_chain else 0.0,
        }
        if self._serving_model is not None and getattr(self._serving_model, "is_real", False):
            # ADR-043 serving path: numpy Weibull reconstruction + SURVIVAL_CI_WIDTH.
            prediction: Any = self._serving_model.predict(
                temperature_deviation_hours=request.temperature_deviation_hours,
                humidity_deviation_pct=request.humidity_deviation_pct,
                initial_shelf_life_days=request.initial_shelf_life_days,
                is_cold_chain=request.is_cold_chain,
                days_since_receipt=request.days_since_receipt,
            )
            confidence = float(self._serving_model.confidence(covariates))
            self.last_provenance = Provenance.real(
                model_version=f"freshness_weibull_aft:{self._serving_model.version}",
                confidence_basis=ConfidenceBasis.SURVIVAL_CI_WIDTH,
                feature_source=FeatureSource.DIRECT,
            )
        else:
            prediction = self.shelf_life_model.predict(
                sku_id=request.sku_id,
                store_id=request.store_id,
                temperature_deviation_hours=request.temperature_deviation_hours,
                humidity_deviation_pct=request.humidity_deviation_pct,
                initial_shelf_life_days=request.initial_shelf_life_days,
                is_cold_chain=request.is_cold_chain,
                days_since_receipt=request.days_since_receipt,
            )
            confidence = FALLBACK_CONFIDENCE
            self.last_provenance = Provenance.degraded_fallback(feature_source=FeatureSource.DIRECT)

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
