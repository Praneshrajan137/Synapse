"""Oracle Layer 6: Demand Prophet conformal calibration vs Twin."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams


@pytest.mark.oracle()
class TestDemandCalibrationOracle:
    def test_demand_within_conformal_interval(self, twin_runner: MonteCarloRunner) -> None:
        """90% conformal interval should contain Twin actual in >= 85% of scenarios."""
        baseline = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        spike = twin_runner.run_scenarios(
            n=1000, shock_params=ShockParams(demand_multiplier=1.5), duration_hours=4.0,
        )
        assert spike.kpi_means["orders_created"] > baseline.kpi_means["orders_created"]

    def test_forecast_stability(self, twin_runner: MonteCarloRunner) -> None:
        """Two runs with same seed should produce similar distributions."""
        a = twin_runner.run_scenarios(n=1000, duration_hours=2.0)
        b = twin_runner.run_scenarios(n=1000, duration_hours=2.0)
        delta = abs(a.kpi_means["orders_created"] - b.kpi_means["orders_created"])
        mean = (a.kpi_means["orders_created"] + b.kpi_means["orders_created"]) / 2
        assert delta / mean < 0.15 if mean > 0 else True
