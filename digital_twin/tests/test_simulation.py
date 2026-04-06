"""
SYNAPSE Digital Twin — Simulation layer tests.

Covers:
  - SimPy engine produces valid runs
  - INV-TW-002: Monte Carlo >= 1000 scenarios
  - INV-TW-003: KL divergence alert fires when > 0.1
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.simulation.monte_carlo import (
    MIN_SCENARIOS,
    MonteCarloRunner,
    ShockParams,
)
from digital_twin.sync.divergence_monitor import (
    THRESHOLD,
    DivergenceMonitor,
    compute_kl_divergence,
)


class TestSimPyEngine:
    """SimPy discrete-event simulation engine tests."""

    def test_run_produces_valid_metrics(self, twin_config: TwinConfig) -> None:
        """A short simulation should create and deliver orders."""
        sim = SupplyChainSimulation(config=twin_config, seed=42)
        metrics = sim.run(duration_hours=1)

        assert metrics.orders_created > 0
        assert metrics.orders_delivered >= 0
        assert metrics.spoilage_rate >= 0.0
        assert metrics.avg_delivery_time_min >= 0.0

    def test_run_deterministic_with_seed(self, twin_config: TwinConfig) -> None:
        """Same seed should produce identical results."""
        sim1 = SupplyChainSimulation(config=twin_config, seed=123)
        sim2 = SupplyChainSimulation(config=twin_config, seed=123)

        m1 = sim1.run(duration_hours=1)
        m2 = sim2.run(duration_hours=1)

        assert m1.orders_created == m2.orders_created
        assert m1.orders_delivered == m2.orders_delivered

    def test_metrics_to_dict(self, twin_config: TwinConfig) -> None:
        """Metrics should serialize to a valid dict."""
        sim = SupplyChainSimulation(config=twin_config, seed=42)
        metrics = sim.run(duration_hours=0.5)
        d = metrics.to_dict()

        assert isinstance(d, dict)
        assert "orders_created" in d
        assert "avg_delivery_time_min" in d
        assert "spoilage_rate" in d

    def test_longer_run_more_orders(self, twin_config: TwinConfig) -> None:
        """Running longer should produce more orders (stochastic but very likely)."""
        sim_short = SupplyChainSimulation(config=twin_config, seed=42)
        sim_long = SupplyChainSimulation(config=twin_config, seed=42)

        m_short = sim_short.run(duration_hours=1)
        m_long = sim_long.run(duration_hours=4)

        assert m_long.orders_created >= m_short.orders_created


class TestMonteCarlo:
    """Monte Carlo runner tests — INV-TW-002."""

    def test_min_scenarios_enforced(self, twin_config: TwinConfig) -> None:
        """INV-TW-002: n < 1000 must raise ValueError."""
        runner = MonteCarloRunner(config=twin_config)
        with pytest.raises(ValueError, match="INV-TW-002"):
            runner.run_scenarios(n=500)

    @pytest.mark.slow
    def test_runs_at_least_1000_scenarios(self, twin_config: TwinConfig) -> None:
        """INV-TW-002: Must run >= 1000 scenarios and return valid output."""
        runner = MonteCarloRunner(config=twin_config)
        output = runner.run_scenarios(n=1000, duration_hours=0.5)

        assert output.n_scenarios == 1000
        assert output.elapsed_seconds > 0
        assert "orders_created" in output.kpi_means
        assert output.kpi_means["orders_created"] > 0

    @pytest.mark.slow
    def test_shock_params_affect_output(self, twin_config: TwinConfig) -> None:
        """Shock params should shift KPI distributions."""
        runner = MonteCarloRunner(config=twin_config)

        baseline = runner.run_scenarios(
            n=1000, shock_params=ShockParams(), duration_hours=0.5
        )
        shocked = runner.run_scenarios(
            n=1000,
            shock_params=ShockParams(demand_multiplier=3.0),
            duration_hours=0.5,
        )

        assert shocked.kpi_means["orders_created"] > baseline.kpi_means["orders_created"]


class TestKLDivergence:
    """KL divergence and alert tests — INV-TW-003."""

    def test_kl_divergence_identical_is_zero(self) -> None:
        """KL(P || P) should be ~0."""
        p = np.array([0.25, 0.25, 0.25, 0.25])
        kl = compute_kl_divergence(p, p)
        assert kl < 1e-8

    def test_kl_divergence_different_is_positive(
        self,
        sample_distributions: tuple[np.ndarray, np.ndarray],
    ) -> None:
        """KL(P || Q) should be > 0 for different distributions."""
        p, q = sample_distributions
        kl = compute_kl_divergence(p, q)
        assert kl > 0.0

    def test_alert_fires_above_threshold(
        self,
        twin_config: TwinConfig,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """INV-TW-003: Alert fires on synapse.twin.divergence when KL > 0.1."""
        monitor = DivergenceMonitor(
            config=twin_config, producer=mock_kafka_producer
        )

        p = np.array([0.9, 0.05, 0.05])
        q = np.array([0.1, 0.45, 0.45])

        monitor.update_twin_state("demand_prophet", p)
        monitor.update_live_state("demand_prophet", q)

        kl = monitor.check_divergence("demand_prophet")
        assert kl is not None
        assert kl > THRESHOLD

        mock_kafka_producer.produce.assert_called_once()
        call_args = mock_kafka_producer.produce.call_args
        assert call_args.kwargs["topic"] == "synapse.twin.divergence"
        assert call_args.kwargs["key"] == "demand_prophet"

    def test_no_alert_below_threshold(
        self,
        twin_config: TwinConfig,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """No alert should fire when KL < threshold."""
        monitor = DivergenceMonitor(
            config=twin_config, producer=mock_kafka_producer
        )

        p = np.array([0.34, 0.33, 0.33])
        q = np.array([0.33, 0.34, 0.33])

        monitor.update_twin_state("demand_prophet", p)
        monitor.update_live_state("demand_prophet", q)

        kl = monitor.check_divergence("demand_prophet")
        assert kl is not None
        assert kl < THRESHOLD

        mock_kafka_producer.produce.assert_not_called()

    def test_check_all_returns_divergences(
        self,
        twin_config: TwinConfig,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """check_all should return KL values for all agents with state."""
        monitor = DivergenceMonitor(
            config=twin_config, producer=mock_kafka_producer
        )

        for agent in ("demand_prophet", "routing_navigator"):
            rng = np.random.default_rng(hash(agent) % (2**31))
            monitor.update_twin_state(agent, rng.dirichlet(np.ones(5)))
            monitor.update_live_state(agent, rng.dirichlet(np.ones(5)))

        results = monitor.check_all()
        assert len(results) == 2
        assert all(isinstance(v, float) for v in results.values())
