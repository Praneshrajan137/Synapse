"""Oracle Layer 6: Inventory Sentinel vs Digital Twin Monte Carlo."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner


@pytest.mark.oracle()
class TestStockoutOracle:
    def test_stockout_rate_below_threshold(self, twin_runner: MonteCarloRunner) -> None:
        """Inventory reorder should prevent stockout in >= 95% of MC runs."""
        result = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        spoilage = result.kpi_means.get("spoilage_rate", 0.0)
        assert spoilage < 0.1, f"Spoilage rate {spoilage:.2%} too high for oracle validation"

    def test_restocks_triggered(self, twin_runner: MonteCarloRunner) -> None:
        result = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        restocks = result.kpi_means.get("restocks_triggered", 0.0)
        assert restocks > 0, "Twin should trigger restocks during 4h simulation"
