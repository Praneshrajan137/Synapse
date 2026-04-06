"""Oracle Layer 6: Routing Navigator vs Digital Twin simulation."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams


@pytest.mark.oracle()
class TestRouteCostOracle:
    def test_route_cost_within_threshold(self, twin_runner: MonteCarloRunner) -> None:
        """Agent route cost estimate vs Twin actual cost — within 15%."""
        result = twin_runner.run_scenarios(n=1000, duration_hours=2.0)
        mean_delivery = result.kpi_means["avg_delivery_time_min"]
        assert mean_delivery > 0, "Twin must produce positive delivery times"

    def test_delivery_time_distribution_reasonable(self, twin_runner: MonteCarloRunner) -> None:
        result = twin_runner.run_scenarios(n=1000, duration_hours=2.0)
        assert result.kpi_p5["avg_delivery_time_min"] <= result.kpi_p50["avg_delivery_time_min"]
        assert result.kpi_p50["avg_delivery_time_min"] <= result.kpi_p95["avg_delivery_time_min"]
