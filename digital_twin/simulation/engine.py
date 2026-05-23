"""
SYNAPSE Digital Twin — SimPy discrete-event simulation engine.

Models the full order lifecycle: arrival → pick/pack/dispatch → delivery → restock → spoilage.
Each process draws from calibrated distributions and integrates with agent signals.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Any

import numpy as np
import simpy
import structlog

from digital_twin.config import TwinConfig

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class SimulationMetrics:
    """Accumulated metrics from a single simulation run."""

    orders_created: int = 0
    orders_delivered: int = 0
    orders_spoiled: int = 0
    restocks_triggered: int = 0
    total_delivery_time_min: float = 0.0
    total_pick_pack_time_min: float = 0.0

    @property
    def avg_delivery_time_min(self) -> float:
        """End-to-end customer-visible delivery time = pick/pack + travel.

        Fix for E-DT-004: previously this returned only travel time, leaving
        the metric unresponsive to supplier-failure shocks (which scale
        ``pick_pack_mean_min`` via ``lead_time_multiplier``). The customer
        experiences pick+pack+travel as a single wait, so the SLA metric
        must include both stages.
        """
        if self.orders_delivered == 0:
            return 0.0
        return (
            self.total_pick_pack_time_min + self.total_delivery_time_min
        ) / self.orders_delivered

    @property
    def avg_travel_time_min(self) -> float:
        """Travel-only component (preserved for diagnostics/breakdown)."""
        if self.orders_delivered == 0:
            return 0.0
        return self.total_delivery_time_min / self.orders_delivered

    @property
    def avg_pick_pack_time_min(self) -> float:
        """Pick+pack-only component (preserved for diagnostics/breakdown)."""
        if self.orders_delivered == 0:
            return 0.0
        return self.total_pick_pack_time_min / self.orders_delivered

    @property
    def spoilage_rate(self) -> float:
        if self.orders_created == 0:
            return 0.0
        return self.orders_spoiled / self.orders_created

    def to_dict(self) -> dict[str, Any]:
        return {
            "orders_created": self.orders_created,
            "orders_delivered": self.orders_delivered,
            "orders_spoiled": self.orders_spoiled,
            "restocks_triggered": self.restocks_triggered,
            "avg_delivery_time_min": round(self.avg_delivery_time_min, 2),
            "avg_travel_time_min": round(self.avg_travel_time_min, 2),
            "avg_pick_pack_time_min": round(self.avg_pick_pack_time_min, 2),
            "spoilage_rate": round(self.spoilage_rate, 4),
        }


class SupplyChainSimulation:
    """SimPy-based discrete-event simulation of the supply chain.

    Processes:
      - order_arrival: Poisson inter-arrival times
      - pick_pack_dispatch: Normal(mean=8, std=2) minutes
      - delivery: OSRM travel time estimate + Gaussian noise
      - restock: Triggered when inventory drops below safety stock (Inventory Sentinel)
      - spoilage: Freshness Guardian quality decay model
    """

    def __init__(
        self,
        config: TwinConfig | None = None,
        seed: int | None = None,
        failure_rate_multiplier: float = 1.0,
        spoilage_rate_multiplier: float = 1.0,
    ) -> None:
        self._config = config or TwinConfig()
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._metrics = SimulationMetrics()
        self._inventory: dict[str, float] = {}
        self._freshness: dict[str, float] = {}
        # ShockParams fields not currently in TwinConfig.
        # Bounded to avoid degenerate distributions under aggressive shocks.
        self._failure_rate_multiplier = max(1.0, float(failure_rate_multiplier))
        self._spoilage_rate_multiplier = max(0.0, float(spoilage_rate_multiplier))

    def _init_env(self) -> simpy.Environment:
        if self._seed is not None:
            random.seed(self._seed)
        return simpy.Environment()

    def _order_arrival(self, env: simpy.Environment) -> Any:
        """Poisson-distributed order arrivals."""
        order_id = 0
        while True:
            inter_arrival = self._rng.exponential(1.0 / self._config.order_arrival_rate)
            yield env.timeout(inter_arrival)
            order_id += 1
            self._metrics.orders_created += 1
            env.process(self._pick_pack_dispatch(env, order_id))

    def _pick_pack_dispatch(self, env: simpy.Environment, order_id: int) -> Any:
        """Pick, pack, and dispatch — Normal(mean, std) minutes."""
        duration = max(
            1.0,
            self._rng.normal(
                self._config.pick_pack_mean_min,
                self._config.pick_pack_std_min,
            ),
        )
        self._metrics.total_pick_pack_time_min += duration
        yield env.timeout(duration)
        logger.debug("pick_pack_done", order_id=order_id, duration_min=round(duration, 2))
        env.process(self._delivery(env, order_id))

    def _delivery(self, env: simpy.Environment, order_id: int) -> Any:
        """Delivery with OSRM-estimated travel time + noise.

        Fix for E-DT-005: each completed delivery now decrements inventory for
        a randomly-chosen SKU, coupling order flow to stock levels so the
        Inventory Sentinel restock loop is exercised by the twin.

        ``failure_rate_multiplier`` (>=1.0) raises the probability of a
        delivery retry, which adds the original travel time again. With the
        default multiplier of 1.0 the failure probability is 0.0 — i.e.
        baseline behavior is unchanged.
        """
        base_travel_min = self._rng.uniform(10.0, 45.0)
        noise = self._rng.normal(0.0, 3.0)
        travel_time = max(5.0, base_travel_min + noise)
        yield env.timeout(travel_time)
        # Probabilistic delivery retry under shock.
        failure_prob = min(0.5, 0.05 * (self._failure_rate_multiplier - 1.0))
        if failure_prob > 0.0 and self._rng.random() < failure_prob:
            yield env.timeout(travel_time)
            travel_time *= 2.0
        self._metrics.orders_delivered += 1
        self._metrics.total_delivery_time_min += travel_time
        if self._inventory:
            sku = self._rng.choice(list(self._inventory.keys()))
            self._inventory[sku] = max(0.0, self._inventory[sku] - 1.0)
        logger.debug("delivery_done", order_id=order_id, travel_min=round(travel_time, 2))

    def _restock(self, env: simpy.Environment) -> Any:
        """Inventory Sentinel-triggered restock when stock falls below safety level."""
        safety_stock = 50.0
        restock_amount = 200.0
        check_interval = 5.0

        while True:
            yield env.timeout(check_interval)
            for sku, level in list(self._inventory.items()):
                if level < safety_stock:
                    lead_time = self._rng.uniform(30.0, 120.0)
                    yield env.timeout(lead_time)
                    self._inventory[sku] = level + restock_amount
                    self._metrics.restocks_triggered += 1
                    logger.debug("restock", sku=sku, new_level=self._inventory[sku])

    def _spoilage(self, env: simpy.Environment) -> Any:
        """Freshness Guardian — quality degrades over time; spoiled items are flagged.

        ``spoilage_rate_multiplier`` scales the per-tick decay rate so monsoon /
        cold-chain shocks visibly inflate the spoilage KPI.
        """
        decay_rate = 0.01 * self._spoilage_rate_multiplier
        spoilage_threshold = 0.3
        check_interval = 10.0

        while True:
            yield env.timeout(check_interval)
            for sku in list(self._freshness.keys()):
                self._freshness[sku] -= decay_rate * check_interval
                if self._freshness[sku] < spoilage_threshold:
                    self._metrics.orders_spoiled += 1
                    self._freshness[sku] = 1.0
                    logger.debug("spoilage", sku=sku)

    def run(self, duration_hours: float | None = None) -> SimulationMetrics:
        """Run the simulation for the given duration.

        Returns:
            SimulationMetrics with aggregated KPIs.
        """
        duration = duration_hours or self._config.simpy_default_duration_hours
        duration_min = duration * 60.0

        self._metrics = SimulationMetrics()
        self._inventory = {f"sku_{i}": 100.0 for i in range(10)}
        self._freshness = {f"sku_{i}": 1.0 for i in range(10)}

        env = self._init_env()
        env.process(self._order_arrival(env))
        env.process(self._restock(env))
        env.process(self._spoilage(env))

        env.run(until=duration_min)

        logger.info(
            "simulation_complete",
            duration_hours=duration,
            **self._metrics.to_dict(),
        )
        return self._metrics
