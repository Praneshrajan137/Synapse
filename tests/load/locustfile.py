from __future__ import annotations

"""Locust load test for SYNAPSE API Gateway — 6 named scenarios.

Scenarios (select via env var SYNAPSE_LOAD_SCENARIO):
    sustained          — baseline traffic, p99 < 2s, I-10 SLA validation
    ipl_burst          — 5x demand spike during IPL match window
    multi_disruption   — concurrent disruption + reroute + repricing pressure
    hitl_flood         — saturate HITL escalation queue
    kafka_backpressure — high-volume bulk-order ingest, validate consumer lag bounds
    neo4j_concurrent   — concurrent shortest-path queries against Neo4j

Invocation (see tests/load/README.md for full matrix):
    SYNAPSE_LOAD_SCENARIO=sustained \
        locust -f tests/load/locustfile.py --users 100 --spawn-rate 10 --run-time 10m --headless
"""

import os
import random
import uuid
from datetime import UTC, datetime

from locust import HttpUser, between, events, tag, task

VALID_SCENARIOS = {
    "sustained",
    "ipl_burst",
    "multi_disruption",
    "hitl_flood",
    "kafka_backpressure",
    "neo4j_concurrent",
}


def _scenario() -> str:
    s = os.environ.get("SYNAPSE_LOAD_SCENARIO", "sustained").strip().lower()
    if s not in VALID_SCENARIOS:
        raise ValueError(
            f"Invalid SYNAPSE_LOAD_SCENARIO={s!r}; valid: {sorted(VALID_SCENARIOS)}"
        )
    return s


STORE_IDS = [f"STORE-BLR-{i:02d}" for i in range(1, 26)]
MUMBAI_STORE_IDS = [f"MUM-{i:03d}" for i in range(1, 26)]
SKU_IDS = [f"SKU-{i:04d}" for i in range(1, 101)]
HORIZONS = ["15min", "1h", "6h", "24h", "7d"]
DISRUPTION_TYPES = ["heat_wave", "monsoon_flood", "festival_surge", "blackout", "strike"]


# ──────────────────────────────────────────────────────────────────────────
# Scenario 1 — Sustained baseline (existing behavior; unchanged)
# ──────────────────────────────────────────────────────────────────────────
class SynapseAPIUser(HttpUser):
    """Sustained baseline traffic — validates I-10 (p99 < 2s)."""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.order_count = 0

    @tag("sustained")
    @task(10)
    def demand_forecast(self) -> None:
        payload = {
            "sku_ids": random.sample(SKU_IDS, k=min(5, len(SKU_IDS))),
            "store_id": random.choice(STORE_IDS),
            "horizons": random.sample(HORIZONS, k=random.randint(1, 3)),
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
                "pickup_store": random.choice(STORE_IDS),
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
            f"/api/v1/agents/inventory_sentinel/state/{random.choice(STORE_IDS)}",
            name="inventory_state",
        )

    @tag("sustained")
    @task(3)
    def orchestrator_decision(self) -> None:
        payload = {
            "decision_type": random.choice([
                "restock", "reroute", "reprice", "rebalance",
            ]),
            "store_id": random.choice(STORE_IDS),
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


# ──────────────────────────────────────────────────────────────────────────
# Scenario 2 — IPL burst (5x spike on demand_prophet, IPL stadium proximity)
# ──────────────────────────────────────────────────────────────────────────
class IPLBurstUser(HttpUser):
    """5x demand spike during IPL match window; tests Tier-2 burst absorption."""

    wait_time = between(0.05, 0.15)

    @tag("ipl_burst")
    @task
    def ipl_burst_demand(self) -> None:
        for _ in range(5):
            payload = {
                "sku_ids": random.sample(SKU_IDS[:20], k=10),
                "store_id": random.choice(STORE_IDS[:10]),
                "horizons": ["15min", "1h"],
                "include_uncertainty": True,
                "event_context": {
                    "type": "ipl_match",
                    "team": random.choice(["RCB", "MI", "CSK", "KKR"]),
                    "venue_proximity_km": round(random.uniform(0.5, 5.0), 2),
                },
            }
            self.client.post(
                "/api/v1/agents/demand_prophet/predict",
                json=payload,
                name="ipl_burst_demand",
            )


# ──────────────────────────────────────────────────────────────────────────
# Scenario 3 — Multi-disruption (concurrent disruption + reroute + repricing)
# ──────────────────────────────────────────────────────────────────────────
class MultiDisruptionUser(HttpUser):
    """Triggers concurrent agent activation across disruption_shield, routing, pricing."""

    wait_time = between(0.5, 1.5)

    @tag("multi_disruption")
    @task(5)
    def trigger_disruption(self) -> None:
        payload = {
            "disruption_id": str(uuid.uuid4()),
            "type": random.choice(DISRUPTION_TYPES),
            "severity": round(random.uniform(0.4, 1.0), 2),
            "affected_zones": random.sample(STORE_IDS, k=random.randint(3, 8)),
            "started_at": datetime.now(UTC).isoformat(),
        }
        self.client.post(
            "/api/v1/agents/disruption_shield/scenario",
            json=payload,
            name="disruption_scenario",
        )

    @tag("multi_disruption")
    @task(5)
    def emergency_reroute(self) -> None:
        orders = [
            {
                "order_id": str(uuid.uuid4()),
                "pickup_store": random.choice(STORE_IDS),
                "delivery_lat": 12.9716 + random.uniform(-0.1, 0.1),
                "delivery_lon": 77.5946 + random.uniform(-0.1, 0.1),
                "weight_kg": round(random.uniform(0.5, 15.0), 2),
                "temp_class": "ambient",
                "deadline_minutes": random.randint(10, 30),
                "priority": "critical",
            }
            for _ in range(random.randint(5, 15))
        ]
        self.client.post(
            "/api/v1/agents/routing_navigator/optimize",
            json={"orders": orders, "mode": "emergency"},
            name="emergency_reroute",
        )

    @tag("multi_disruption")
    @task(3)
    def surge_pricing(self) -> None:
        payload = {
            "sku_ids": random.sample(SKU_IDS, k=10),
            "store_id": random.choice(STORE_IDS),
            "context": {"disruption_active": True, "surge_factor": 1.3},
        }
        self.client.post(
            "/api/v1/agents/pricing_oracle/recommend",
            json=payload,
            name="surge_pricing",
        )


# ──────────────────────────────────────────────────────────────────────────
# Scenario 4 — HITL flood (escalation queue saturation)
# ──────────────────────────────────────────────────────────────────────────
class HITLFloodUser(HttpUser):
    """Forces low-confidence decisions to flood the HITL escalation queue (I-5)."""

    wait_time = between(0.5, 1.5)

    @tag("hitl_flood")
    @task
    def escalation_request(self) -> None:
        payload = {
            "decision_id": str(uuid.uuid4()),
            "confidence": round(random.uniform(0.30, 0.55), 3),
            "agent_proposals": [
                {"agent": "demand_prophet", "utility": round(random.uniform(0.4, 0.7), 2)},
                {"agent": "pricing_oracle", "utility": round(random.uniform(0.4, 0.7), 2)},
                {"agent": "routing_navigator", "utility": round(random.uniform(0.4, 0.7), 2)},
            ],
            "context": {
                "reason": "low_confidence_consensus",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }
        self.client.post(
            "/api/v1/orchestrator/escalate",
            json=payload,
            name="hitl_escalation",
        )


# ──────────────────────────────────────────────────────────────────────────
# Scenario 5 — Kafka backpressure (high-volume bulk ingest)
# ──────────────────────────────────────────────────────────────────────────
class KafkaBackpressureUser(HttpUser):
    """Bulk-order ingest to stress Kafka producers and consumer-group lag."""

    wait_time = between(0.2, 0.6)

    @tag("kafka_backpressure")
    @task(10)
    def bulk_orders(self) -> None:
        orders = [
            {
                "order_id": str(uuid.uuid4()),
                "store_id": random.choice(STORE_IDS),
                "sku_id": random.choice(SKU_IDS),
                "quantity": random.randint(1, 5),
                "placed_at": datetime.now(UTC).isoformat(),
            }
            for _ in range(1000)
        ]
        self.client.post(
            "/api/v1/orders/bulk",
            json={"orders": orders},
            name="bulk_orders_1000",
        )

    @tag("kafka_backpressure")
    @task(1)
    def lag_check(self) -> None:
        # Pulls Prometheus-style metrics; SLO: synapse_kafka_consumer_lag < 10000.
        with self.client.get("/metrics", name="metrics_lag_check", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"metrics endpoint returned {r.status_code}")
                return
            for line in r.text.splitlines():
                if line.startswith("synapse_kafka_consumer_lag"):
                    try:
                        value = float(line.rsplit(" ", 1)[-1])
                    except ValueError:
                        continue
                    if value > 10000:
                        r.failure(f"consumer lag {value} > 10000 SLO")
                        return
            r.success()


# ──────────────────────────────────────────────────────────────────────────
# Scenario 6 — Neo4j concurrent shortest-path queries
# ──────────────────────────────────────────────────────────────────────────
class Neo4jConcurrentUser(HttpUser):
    """Maximizes pickup-store cardinality to force concurrent Neo4j path queries."""

    wait_time = between(0.05, 0.2)

    @tag("neo4j_concurrent")
    @task
    def graph_intensive_route(self) -> None:
        # Use ALL stores in a single request to maximize graph fan-out.
        orders = [
            {
                "order_id": str(uuid.uuid4()),
                "pickup_store": store,
                "delivery_lat": 12.9716 + random.uniform(-0.1, 0.1),
                "delivery_lon": 77.5946 + random.uniform(-0.1, 0.1),
                "weight_kg": round(random.uniform(0.5, 5.0), 2),
                "temp_class": "ambient",
                "deadline_minutes": random.randint(15, 45),
            }
            for store in random.sample(STORE_IDS, k=min(20, len(STORE_IDS)))
        ]
        self.client.post(
            "/api/v1/agents/routing_navigator/optimize",
            json={"orders": orders, "graph_mode": "exhaustive"},
            name="graph_intensive_route",
        )


# ──────────────────────────────────────────────────────────────────────────
# Scenario dispatch — env-driven user-class selection
# ──────────────────────────────────────────────────────────────────────────
_SCENARIO_TO_CLASS = {
    "sustained": SynapseAPIUser,
    "ipl_burst": IPLBurstUser,
    "multi_disruption": MultiDisruptionUser,
    "hitl_flood": HITLFloodUser,
    "kafka_backpressure": KafkaBackpressureUser,
    "neo4j_concurrent": Neo4jConcurrentUser,
}


@events.test_start.add_listener
def _announce_scenario(environment, **_kwargs) -> None:  # type: ignore[no-untyped-def]
    """Print the selected scenario and disable non-selected user classes."""
    scenario = _scenario()
    selected_cls = _SCENARIO_TO_CLASS[scenario]
    print(f"[SYNAPSE-LOAD] scenario={scenario} user_class={selected_cls.__name__}")
    # Filter user_classes to only the selected scenario.
    if hasattr(environment, "user_classes") and environment.user_classes:
        environment.user_classes = [
            cls for cls in environment.user_classes if cls is selected_cls
        ] or [selected_cls]


__all__ = [
    "SynapseAPIUser",
    "IPLBurstUser",
    "MultiDisruptionUser",
    "HITLFloodUser",
    "KafkaBackpressureUser",
    "Neo4jConcurrentUser",
]
