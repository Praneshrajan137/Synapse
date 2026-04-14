"""
SYNAPSE Orchestrator — Consumer-driven contract: Digital Twin what-if responses.

The Orchestrator (consumer) expects the Digital Twin to return Monte Carlo
results conforming to ``digital_twin.simulation.monte_carlo.MonteCarloOutput``.
"""

from __future__ import annotations

import pytest


class TestTwinSimulationContract:
    """Consumer-driven: Orchestrator expects these fields from Digital Twin MC output."""

    @pytest.mark.contract()
    def test_output_has_n_scenarios(self) -> None:
        from digital_twin.simulation.monte_carlo import MonteCarloOutput

        output = MonteCarloOutput(
            n_scenarios=1000,
            elapsed_seconds=5.0,
            kpi_means={"orders_created": 100.0},
            kpi_p5={"orders_created": 80.0},
            kpi_p50={"orders_created": 100.0},
            kpi_p95={"orders_created": 120.0},
            kpi_std={"orders_created": 10.0},
        )
        assert output.n_scenarios >= 1000

    @pytest.mark.contract()
    def test_output_has_kpi_means(self) -> None:
        from digital_twin.simulation.monte_carlo import MonteCarloOutput

        output = MonteCarloOutput(
            n_scenarios=1000,
            elapsed_seconds=5.0,
            kpi_means={"orders_created": 100.0, "avg_delivery_time_min": 25.0},
            kpi_p5={},
            kpi_p50={},
            kpi_p95={},
            kpi_std={},
        )
        assert "orders_created" in output.kpi_means
        assert "avg_delivery_time_min" in output.kpi_means

    @pytest.mark.contract()
    def test_output_to_dict(self) -> None:
        from digital_twin.simulation.monte_carlo import MonteCarloOutput

        output = MonteCarloOutput(
            n_scenarios=1000,
            elapsed_seconds=1.0,
            kpi_means={},
            kpi_p5={},
            kpi_p50={},
            kpi_p95={},
            kpi_std={},
        )
        d = output.to_dict()
        assert isinstance(d, dict)
        assert "n_scenarios" in d
