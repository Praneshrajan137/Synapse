"""
SYNAPSE Digital Twin — What-If scenario engine.

INV-TW-004: What-If API must respond within 10 seconds for 1000 scenarios.
Composes the SimPy engine and Monte Carlo runner for scenario exploration.
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

from digital_twin.config import TwinConfig
from digital_twin.simulation.monte_carlo import (
    MonteCarloOutput,
    MonteCarloRunner,
    ShockParams,
)

logger = structlog.get_logger(__name__)


class ScenarioSpec(BaseModel):
    """Specification for a What-If scenario."""

    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    demand_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)
    lead_time_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)
    failure_rate_multiplier: float = Field(default=1.0, ge=0.0, le=10.0)
    spoilage_rate_multiplier: float = Field(default=1.0, ge=0.0, le=10.0)
    n_scenarios: int = Field(default=1000, ge=1000)
    duration_hours: float = Field(default=4.0, gt=0.0)


class WhatIfResult(BaseModel):
    """Result of a What-If simulation."""

    scenario_name: str
    elapsed_seconds: float
    within_sla: bool
    monte_carlo: dict[str, Any]


class WhatIfEngine:
    """Scenario testing engine exposed via FastAPI.

    Runs Monte Carlo batches with customizable shock parameters.
    INV-TW-004: enforces 10-second SLA awareness.
    """

    def __init__(self, config: TwinConfig | None = None) -> None:
        self._config = config or TwinConfig()
        self._runner = MonteCarloRunner(config=self._config)

    def simulate(self, scenario_spec: ScenarioSpec) -> WhatIfResult:
        """Run a What-If scenario and return aggregated results.

        Args:
            scenario_spec: Scenario parameters including shock multipliers.

        Returns:
            WhatIfResult with Monte Carlo output and SLA compliance flag.
        """
        start = time.monotonic()

        shock = ShockParams(
            demand_multiplier=scenario_spec.demand_multiplier,
            lead_time_multiplier=scenario_spec.lead_time_multiplier,
            failure_rate_multiplier=scenario_spec.failure_rate_multiplier,
            spoilage_rate_multiplier=scenario_spec.spoilage_rate_multiplier,
        )

        mc_output: MonteCarloOutput = self._runner.run_scenarios(
            n=scenario_spec.n_scenarios,
            shock_params=shock,
            duration_hours=scenario_spec.duration_hours,
        )

        elapsed = time.monotonic() - start
        within_sla = elapsed <= self._config.what_if_sla_seconds

        if not within_sla:
            logger.warning(
                "what_if_sla_breach",
                scenario=scenario_spec.name,
                elapsed_s=round(elapsed, 3),
                sla_s=self._config.what_if_sla_seconds,
            )

        result = WhatIfResult(
            scenario_name=scenario_spec.name,
            elapsed_seconds=round(elapsed, 3),
            within_sla=within_sla,
            monte_carlo=mc_output.to_dict(),
        )

        logger.info(
            "what_if_complete",
            scenario=scenario_spec.name,
            elapsed_s=result.elapsed_seconds,
            within_sla=result.within_sla,
        )
        return result
