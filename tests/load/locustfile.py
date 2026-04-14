from __future__ import annotations

"""Locust load test for SYNAPSE API Gateway.

Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
Scenarios: Sustained throughput, burst demand (IPL sim), multi-disruption.
Success criteria: 500 orders/min sustained; p99 < 2s; no crashes.
"""

import random
import uuid
from datetime import UTC, datetime

from locust import HttpUser, between, tag, task


class SynapseAPIUser(HttpUser):
    """Simulates API gateway traffic at sustained and burst loads."""

    wait_time = between(0.1, 0.5)

    STORE_IDS = [f"STORE-BLR-{i:02d}" for i in range(1, 26)]
    SKU_IDS = [f"SKU-{i:04d}" for i in range(1, 101)]
    HORIZONS = ["15min", "1h", "6h", "24h", "7d"]

    def on_start(self) -> None:
        self.order_count = 0

    @tag("sustained")
    @task(10)
    def demand_forecast(self) -> None:
        payload = {
            "sku_ids": random.sample(self.SKU_IDS, k=min(5, len(self.SKU_IDS))),
            "store_id": random.choice(self.STORE_IDS),
            "horizons": random.sample(self.HORIZONS, k=random.randint(1, 3)),
            "include_uncertainty": True,
        }
        self.client.post(
            "/api/v1/agents/demand_prophet/predict",
            json=payload,
            name="demand_forecast",
        )

    @tag("sustained")
    @task(8)
    def route_optimization(self) -> None:
        orders = [
            {
                "order_id": str(uuid.uuid4()),
                "pickup_store": random.choice(self.STORE_IDS),
                "delivery_lat": 12.9716 + random.uniform(-0.05, 0.05),
                "delivery_lon": 77.5946 + random.uniform(-0.05, 0.05),
                "weight_kg": round(random.uniform(0.5, 15.0), 2),
                "temp_class": random.choice(["ambient", "chilled", "frozen"]),
                "deadline_minutes": random.randint(15, 60),
            }
            for _ in range(random.randint(3, 10))
        ]
        self.client.post(
            "/api/v1/agents/routing_navigator/optimize",
            json={"orders": orders},
            name="route_optimization",
        )

    @tag("sustained")
    @task(5)
    def inventory_state(self) -> None:
        self.client.get(
            f"/api/v1/agents/inventory_sentinel/state/{random.choice(self.STORE_IDS)}",
            name="inventory_state",
        )

    @tag("sustained")
    @task(3)
    def orchestrator_decision(self) -> None:
        payload = {
            "decision_type": random.choice([
                "restock", "reroute", "reprice", "rebalance",
            ]),
            "store_id": random.choice(self.STORE_IDS),
            "priority": random.choice(["low", "medium", "high", "critical"]),
            "context": {
                "source": "load_test",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }
        self.client.post(
            "/api/v1/orchestrator/decide",
            json=payload,
            name="orchestrator_decision",
        )

    @tag("sustained")
    @task(2)
    def agent_health(self) -> None:
        agents = [
            "demand_prophet", "routing_navigator", "inventory_sentinel",
            "pricing_oracle", "freshness_guardian", "disruption_shield",
            "supplier_trust", "sustainability_agent",
        ]
        agent = random.choice(agents)
        self.client.get(
            f"/api/v1/agents/{agent}/health",
            name=f"health_{agent}",
        )

    @tag("burst")
    @task(1)
    def ipl_burst_demand(self) -> None:
        """Simulates 5x demand spike during IPL match."""
        for _ in range(5):
            payload = {
                "sku_ids": random.sample(self.SKU_IDS[:20], k=10),
                "store_id": random.choice(self.STORE_IDS[:10]),
                "horizons": ["15min", "1h"],
                "include_uncertainty": True,
                "event_context": {
                    "type": "ipl_match",
                    "team": "RCB",
                    "venue_proximity_km": 2.0,
                },
            }
            self.client.post(
                "/api/v1/agents/demand_prophet/predict",
                json=payload,
                name="ipl_burst_demand",
            )


class HITLWebSocketUser(HttpUser):
    """Stress tests HITL escalation WebSocket connections."""

    wait_time = between(1, 3)

    @tag("hitl_flood")
    @task
    def escalation_request(self) -> None:
        payload = {
            "decision_id": str(uuid.uuid4()),
            "confidence": round(random.uniform(0.3, 0.6), 3),
            "agent_proposals": [
                {"agent": "demand_prophet", "utility": 0.8},
                {"agent": "pricing_oracle", "utility": 0.75},
            ],
        }
        self.client.post(
            "/api/v1/orchestrator/escalate",
            json=payload,
            name="hitl_escalation",
        )
