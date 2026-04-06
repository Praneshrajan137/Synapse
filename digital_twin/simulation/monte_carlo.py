"""
SYNAPSE Digital Twin — Monte Carlo scenario runner.

INV-TW-002: Every query MUST run >= 1000 scenarios.
Uses ProcessPoolExecutor for CPU-parallel simulation batches.
"""
from __future__ import annotations

import dataclasses
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

import numpy as np
import structlog

from digital_twin.config import TwinConfig

logger = structlog.get_logger(__name__)

MIN_SCENARIOS = 1000


@dataclasses.dataclass(frozen=True)
class ShockParams:
    """Exogenous shock parameters for scenario generation."""

    demand_multiplier: float = 1.0
    lead_time_multiplier: float = 1.0
    failure_rate_multiplier: float = 1.0
    spoilage_rate_multiplier: float = 1.0


@dataclasses.dataclass
class ScenarioResult:
    """Output from a single Monte Carlo scenario."""

    seed: int
    orders_created: int
    orders_delivered: int
    avg_delivery_time_min: float
    spoilage_rate: float
    restocks_triggered: int


@dataclasses.dataclass
class MonteCarloOutput:
    """Aggregated Monte Carlo results with confidence intervals."""

    n_scenarios: int
    elapsed_seconds: float
    kpi_means: dict[str, float]
    kpi_p5: dict[str, float]
    kpi_p50: dict[str, float]
    kpi_p95: dict[str, float]
    kpi_std: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _run_single_scenario(
    seed: int,
    duration_hours: float,
    shock: ShockParams,
) -> dict[str, Any]:
    """Run one SimPy scenario in a worker process (picklable top-level function)."""
    from digital_twin.simulation.engine import SupplyChainSimulation, TwinConfig

    config = TwinConfig(
        order_arrival_rate=2.0 * shock.demand_multiplier,
        pick_pack_mean_min=8.0 * shock.lead_time_multiplier,
    )
    sim = SupplyChainSimulation(config=config, seed=seed)
    metrics = sim.run(duration_hours=duration_hours)
    return {
        "seed": seed,
        "orders_created": metrics.orders_created,
        "orders_delivered": metrics.orders_delivered,
        "avg_delivery_time_min": metrics.avg_delivery_time_min,
        "spoilage_rate": metrics.spoilage_rate,
        "restocks_triggered": metrics.restocks_triggered,
    }


class MonteCarloRunner:
    """Parallel Monte Carlo simulation runner.

    INV-TW-002: n must be >= 1000.
    """

    def __init__(self, config: TwinConfig | None = None) -> None:
        self._config = config or TwinConfig()

    def run_scenarios(
        self,
        n: int = 1000,
        shock_params: ShockParams | None = None,
        duration_hours: float = 4.0,
    ) -> MonteCarloOutput:
        """Run n parallel scenarios and return probability distributions over KPIs.

        Args:
            n: Number of scenarios. Must be >= 1000 (INV-TW-002).
            shock_params: Exogenous shock multipliers.
            duration_hours: Simulation duration per scenario.

        Returns:
            MonteCarloOutput with means, percentiles, and confidence intervals.

        Raises:
            ValueError: If n < MIN_SCENARIOS.
        """
        if n < MIN_SCENARIOS:
            raise ValueError(
                f"INV-TW-002 violated: n={n} < {MIN_SCENARIOS}. "
                "Monte Carlo requires >= 1000 scenarios per query."
            )

        shock = shock_params or ShockParams()
        start = time.monotonic()
        results: list[dict[str, Any]] = []

        max_workers = min(self._config.monte_carlo_max_workers, n)

        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_single_scenario, seed, duration_hours, shock): seed
                for seed in range(n)
            }
            for future in as_completed(futures):
                results.append(future.result())

        elapsed = time.monotonic() - start

        kpi_keys = [
            "orders_created",
            "orders_delivered",
            "avg_delivery_time_min",
            "spoilage_rate",
            "restocks_triggered",
        ]
        arrays: dict[str, np.ndarray] = {
            k: np.array([r[k] for r in results], dtype=np.float64) for k in kpi_keys
        }

        output = MonteCarloOutput(
            n_scenarios=n,
            elapsed_seconds=round(elapsed, 3),
            kpi_means={k: float(np.mean(v)) for k, v in arrays.items()},
            kpi_p5={k: float(np.percentile(v, 5)) for k, v in arrays.items()},
            kpi_p50={k: float(np.percentile(v, 50)) for k, v in arrays.items()},
            kpi_p95={k: float(np.percentile(v, 95)) for k, v in arrays.items()},
            kpi_std={k: float(np.std(v)) for k, v in arrays.items()},
        )

        logger.info(
            "monte_carlo_complete",
            n_scenarios=n,
            elapsed_s=output.elapsed_seconds,
            mean_delivery_min=output.kpi_means.get("avg_delivery_time_min"),
        )
        return output
