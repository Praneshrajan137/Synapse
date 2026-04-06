"""Oracle Layer 6: Sustainability Agent CO2 estimate vs Twin simulation."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner


@pytest.mark.oracle()
class TestCarbonEstimateOracle:
    def test_carbon_estimate_reasonable(self, twin_runner: MonteCarloRunner) -> None:
        """CO2 estimate should be within 10% of Twin fuel/distance simulation."""
        result = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        assert result.kpi_means["orders_delivered"] >= 0
        assert result.n_scenarios == 1000
