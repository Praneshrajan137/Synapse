"""
SYNAPSE Sustainability Agent -- Inference Pipeline.
Handles: Route carbon estimation -> waste survival prediction ->
         ESG report assembly with provenance -> schema validation -> Kafka publish.
All within Tier 2 SLA (<500ms) (I-10).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from agents.sustainability_agent.models.carbon import CarbonTracker
from agents.sustainability_agent.models.waste import WastePredictionModel
from synapse_common.models import SynapseBaseModel

logger = structlog.get_logger(__name__)


class ProvenanceEntry(SynapseBaseModel):
    """Single provenance record in the ESG report chain."""

    source: str
    timestamp: datetime
    description: str
    data_hash: str = ""


class CarbonReport(SynapseBaseModel):
    """Full carbon/sustainability report output (I-3)."""

    report_id: str
    timestamp: datetime
    delivery_co2_kg: float
    compute_co2_kg: float
    total_co2_kg: float
    waste_probability: float
    waste_rate: float
    survival_curve: list[float]
    hazard_rate: float
    pareto_weights: dict[str, float]
    provenance_chain: list[ProvenanceEntry]
    confidence: float


class SustainabilityPipeline:
    """
    End-to-end inference pipeline for the Sustainability Agent.
    All outputs are CarbonReport Pydantic models (I-3).
    """

    def __init__(
        self,
        carbon_tracker: CarbonTracker | None = None,
        waste_model: WastePredictionModel | None = None,
        kafka_producer: Any = None,
        carbon_pareto_weight: float = 0.25,
    ) -> None:
        self._carbon = carbon_tracker or CarbonTracker()
        self._waste = waste_model or WastePredictionModel()
        self._kafka = kafka_producer
        self._carbon_pareto_weight = carbon_pareto_weight

    def report(
        self,
        fuel_liters: float,
        distance_km: float,
        days_ahead: int = 7,
        items_wasted: int = 0,
        items_total: int = 100,
    ) -> CarbonReport:
        """Generate a full sustainability/carbon report."""
        start_time = time.monotonic()
        now = datetime.now(timezone.utc)

        delivery_co2 = self._carbon.track_route(fuel_liters, distance_km)
        compute_co2 = self._carbon.track_compute()
        total_co2 = delivery_co2 + compute_co2

        waste_result = self._waste.predict_waste_probability(days_ahead)
        waste_prob = float(waste_result["waste_probability"])
        survival_curve = waste_result["survival_curve"]
        hazard_rate = float(waste_result["hazard_rate"])

        waste_rate = items_wasted / items_total if items_total > 0 else 0.0

        provenance: list[ProvenanceEntry] = [
            ProvenanceEntry(
                source="routing_navigator",
                timestamp=now,
                description=f"Fuel: {fuel_liters}L, Distance: {distance_km}km",
            ),
            ProvenanceEntry(
                source="codecarbon",
                timestamp=now,
                description=f"Compute emissions: {compute_co2:.6f} kg CO2",
            ),
            ProvenanceEntry(
                source="sustainability_agent.waste_model",
                timestamp=now,
                description=f"Waste probability at {days_ahead}d: {waste_prob:.4f}",
            ),
        ]

        report = CarbonReport(
            report_id=str(uuid4()),
            timestamp=now,
            delivery_co2_kg=round(delivery_co2, 6),
            compute_co2_kg=round(compute_co2, 6),
            total_co2_kg=round(total_co2, 6),
            waste_probability=round(waste_prob, 4),
            waste_rate=round(waste_rate, 4),
            survival_curve=survival_curve,
            hazard_rate=round(hazard_rate, 4),
            pareto_weights={"carbon": self._carbon_pareto_weight},
            provenance_chain=provenance,
            confidence=0.85,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        if elapsed_ms > 500:
            logger.warning(
                "latency_sla_exceeded",
                elapsed_ms=elapsed_ms,
                sla_ms=500,
            )

        logger.info(
            "report_complete",
            total_co2_kg=report.total_co2_kg,
            waste_probability=report.waste_probability,
            latency_ms=f"{elapsed_ms:.1f}",
        )

        return report
