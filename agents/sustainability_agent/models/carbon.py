"""
SYNAPSE Sustainability Agent -- Carbon Tracker.
Wraps CodeCarbon EmissionsTracker for compute emissions and provides
fuel-based CO2 estimation for delivery routes. Integrates with
Routing Navigator fuel_estimate_liters (PRE-SA-001).
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

CO2_KG_PER_LITER_DIESEL: float = 2.68


class CarbonTracker:
    """
    Dual-mode carbon tracker:
    1. Route emissions via fuel consumption (deterministic formula).
    2. Compute emissions via CodeCarbon (empirical measurement).
    """

    def __init__(
        self,
        co2_per_liter_kg: float = CO2_KG_PER_LITER_DIESEL,
        codecarbon_project: str = "synapse_sustainability",
    ) -> None:
        self._co2_per_liter_kg = co2_per_liter_kg
        self._codecarbon_project = codecarbon_project
        self._emissions_tracker: Any = None

    def track_route(self, fuel_liters: float, distance_km: float) -> float:
        """
        Estimate CO2 for a delivery route from fuel consumption.

        Args:
            fuel_liters: Fuel consumed (from Routing Navigator fuel_estimate_liters).
            distance_km: Total route distance (from Routing Navigator total_distance_km).

        Returns:
            CO2 emissions in kg.
        """
        if fuel_liters < 0.0:
            raise ValueError(f"fuel_liters must be >= 0, got {fuel_liters}")
        if distance_km < 0.0:
            raise ValueError(f"distance_km must be >= 0, got {distance_km}")

        co2_kg = fuel_liters * self._co2_per_liter_kg

        logger.info(
            "route_carbon_tracked",
            fuel_liters=fuel_liters,
            distance_km=distance_km,
            co2_kg=round(co2_kg, 4),
        )
        return co2_kg

    def track_compute(self) -> float:
        """
        Measure CO2 from compute workload using CodeCarbon.
        Falls back to zero if CodeCarbon is unavailable (I-7: graceful degradation).

        Returns:
            CO2 emissions in kg.
        """
        try:
            from codecarbon import EmissionsTracker

            if self._emissions_tracker is None:
                self._emissions_tracker = EmissionsTracker(
                    project_name=self._codecarbon_project,
                    log_level="error",
                    save_to_file=False,
                )

            self._emissions_tracker.start()
            self._emissions_tracker.stop()
            emissions_kg: float = self._emissions_tracker.final_emissions

            logger.info("compute_carbon_tracked", co2_kg=round(emissions_kg, 6))
            return max(emissions_kg, 0.0)

        except ImportError:
            logger.warning("codecarbon_unavailable", fallback="zero compute emissions")
            return 0.0
        except Exception as exc:
            logger.error("codecarbon_error", error=str(exc), fallback="zero compute emissions")
            return 0.0

    def estimate_from_route_plan(self, route_plan_payload: dict[str, Any]) -> float:
        """
        Convenience method to extract fuel and distance from a RoutePlan payload
        and compute delivery CO2.
        """
        fuel = float(route_plan_payload.get("fuel_estimate_liters", 0.0))
        distance = float(route_plan_payload.get("total_distance_km", 0.0))
        return self.track_route(fuel, distance)
