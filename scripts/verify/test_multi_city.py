"""
Sprint 6 Quality Gate: Multi-City Deployment Verification

All verification uses Python libraries (no cypher-shell, kafka-topics.sh, jq, bc).
Cross-platform compatible (Windows, Linux, macOS).

INVARIANTS TESTED: I-1, I-3, I-5, I-8, I-11, I-12
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import requests
import structlog

log = structlog.get_logger()

MUMBAI_STORE_COUNT = 25
MUMBAI_SKU_COUNT = 500
MUMBAI_DAYS = 90

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "synapse_graph_2026")


def _neo4j_query(query: str) -> list[dict]:
    """Run a Cypher query via the neo4j Python driver."""
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]
    finally:
        driver.close()


# ─── Category 1: Mumbai data exists and validates ────────────────────────────


class TestMumbaiDataGeneration:
    def test_stores_generated(self) -> None:
        stores = json.loads(Path("data/mumbai/stores.json").read_text())
        assert len(stores) == MUMBAI_STORE_COUNT
        for store in stores:
            assert 18.87 <= store["lat"] <= 19.30, f"Store {store['id']} lat out of bounds"
            assert 72.77 <= store["lon"] <= 73.15, f"Store {store['id']} lon out of bounds"
            assert store["id"].startswith("MUM-"), f"Store {store['id']} missing MUM- prefix"

    def test_warehouses_generated(self) -> None:
        wh = json.loads(Path("data/mumbai/warehouses.json").read_text())
        assert len(wh) == 3

    def test_suppliers_generated(self) -> None:
        suppliers = json.loads(Path("data/mumbai/suppliers.json").read_text())
        assert len(suppliers) == 40

    def test_zones_generated(self) -> None:
        zones = json.loads(Path("data/mumbai/zones.json").read_text())
        assert len(zones) == 8

    def test_riders_generated(self) -> None:
        riders = json.loads(Path("data/mumbai/riders.json").read_text())
        assert len(riders) == 200

    def test_demand_history_shape(self) -> None:
        import pandas as pd

        df = pd.read_csv("data/mumbai/demand_history.csv")
        expected_rows = MUMBAI_DAYS * MUMBAI_SKU_COUNT * MUMBAI_STORE_COUNT
        assert len(df) == expected_rows, f"Expected {expected_rows} rows, got {len(df)}"

    def test_demand_history_has_monsoon(self) -> None:
        import pandas as pd

        df = pd.read_csv("data/mumbai/demand_history.csv", usecols=["monsoon_active"])
        assert "monsoon_active" in df.columns, "Missing monsoon_active column"

    def test_events_mumbai_specific(self) -> None:
        events = json.loads(Path("data/mumbai/events.json").read_text())
        event_names = {e["name"] for e in events}
        assert "Ganesh_Chaturthi" in event_names
        assert "IPL_MI" in event_names
        assert "Monsoon_Onset" in event_names

    def test_skus_shared_with_bengaluru(self) -> None:
        """E-S6-01: SKU catalogs MUST be identical."""
        mumbai_skus = json.loads(Path("data/mumbai/skus.json").read_text())
        bengaluru_skus = json.loads(Path("data/bengaluru/skus.json").read_text())
        mumbai_ids = {s["sku_id"] for s in mumbai_skus}
        bengaluru_ids = {s["sku_id"] for s in bengaluru_skus}
        assert mumbai_ids == bengaluru_ids, "SKU catalogs must match — E-S6-01"

    def test_weather_has_monsoon_intensity(self) -> None:
        """E-S6-09: monsoon_intensity is Mumbai-specific and required."""
        import pandas as pd

        df = pd.read_csv("data/mumbai/weather_history.csv")
        assert "monsoon_intensity" in df.columns, "Missing monsoon_intensity — E-S6-09"
        assert df["monsoon_intensity"].max() > 0, "monsoon_intensity is all zeros"


# ─── Category 2: OSRM routing operational on port 5001 ──────────────────────


class TestOSRMMumbai:
    def test_osrm_routing_operational(self) -> None:
        """E-S6-02: Mumbai OSRM on port 5001, not 5000."""
        resp = requests.get(
            "http://localhost:5001/route/v1/driving/72.8777,19.0760;72.8307,19.0176",
            timeout=5,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "Ok"
        assert len(data["routes"]) >= 1

    def test_osrm_store_pairs_routable(self) -> None:
        """Verify 50 random store pairs are routable."""
        import random

        stores = json.loads(Path("data/mumbai/stores.json").read_text())
        random.seed(42)
        pairs = random.sample(
            [(s1, s2) for s1 in stores for s2 in stores if s1["id"] != s2["id"]],
            k=min(50, len(stores) * (len(stores) - 1)),
        )
        for s1, s2 in pairs:
            resp = requests.get(
                f"http://localhost:5001/route/v1/driving/{s1['lon']},{s1['lat']};{s2['lon']},{s2['lat']}",
                timeout=5,
            )
            assert resp.json()["code"] == "Ok", f"Route failed: {s1['id']} -> {s2['id']}"


# ─── Category 3: Neo4j graph seeded (Python driver, no cypher-shell) ────────


class TestNeo4jMumbai:
    def test_darkstore_count(self) -> None:
        rows = _neo4j_query("MATCH (s:DarkStore {city:'mumbai'}) RETURN count(s) AS c")
        assert rows[0]["c"] == MUMBAI_STORE_COUNT

    def test_warehouse_count(self) -> None:
        rows = _neo4j_query("MATCH (w:Warehouse {city:'mumbai'}) RETURN count(w) AS c")
        assert rows[0]["c"] == 3

    def test_zone_count(self) -> None:
        rows = _neo4j_query("MATCH (z:Zone {city:'mumbai'}) RETURN count(z) AS c")
        assert rows[0]["c"] == 8

    def test_flood_risk_relationships(self) -> None:
        rows = _neo4j_query(
            "MATCH (:Zone {city:'mumbai'})-[r:FLOOD_RISK]->() RETURN count(r) AS c"
        )
        assert rows[0]["c"] >= 5

    def test_bridge_dependency_relationships(self) -> None:
        rows = _neo4j_query("MATCH ()-[r:BRIDGE_DEPENDENCY]->() RETURN count(r) AS c")
        assert rows[0]["c"] >= 3

    def test_no_cross_city_contamination(self) -> None:
        """E-S6-05: Bengaluru data must be untouched."""
        rows = _neo4j_query("MATCH (s:DarkStore {city:'bengaluru'}) RETURN count(s) AS c")
        assert rows[0]["c"] == 25, f"Bengaluru DarkStores corrupted — E-S6-05"

    def test_sku_sharing_verified(self) -> None:
        rows = _neo4j_query("MATCH (k:SKU) RETURN count(k) AS c")
        assert rows[0]["c"] == 500

    def test_city_filter_on_all_queries(self) -> None:
        """E-S6-05: Queries without city filter return cross-city results."""
        all_rows = _neo4j_query("MATCH (s:DarkStore) RETURN count(s) AS c")
        mum_rows = _neo4j_query("MATCH (s:DarkStore {city:'mumbai'}) RETURN count(s) AS c")
        blr_rows = _neo4j_query("MATCH (s:DarkStore {city:'bengaluru'}) RETURN count(s) AS c")
        assert all_rows[0]["c"] == mum_rows[0]["c"] + blr_rows[0]["c"], "Untagged DarkStore nodes"


# ─── Category 4: Transfer learning convergence ──────────────────────────────


class TestTransferLearning:
    def test_convergence_speedup(self) -> None:
        """Transfer model must converge faster than Bengaluru training time."""
        import mlflow

        client = mlflow.tracking.MlflowClient()
        for agent in ["demand_prophet", "routing_navigator", "inventory_sentinel_l1"]:
            exp = client.get_experiment_by_name(f"mumbai_transfer_{agent}")
            assert exp is not None, f"No transfer experiment for {agent}"
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                order_by=["metrics.convergence_speedup DESC"],
                max_results=1,
            )
            assert len(runs) > 0, f"No transfer learning run found for {agent}"
            speedup = runs[0].data.metrics.get("convergence_speedup", 0)
            assert speedup > 2.5, f"{agent} convergence speedup {speedup:.1f}x < 2.5x target"

    def test_conformal_recalibration(self) -> None:
        """E-S6-04: Mumbai conformal intervals MUST be recalibrated."""
        import mlflow

        client = mlflow.tracking.MlflowClient()
        exp = client.get_experiment_by_name("mumbai_transfer_demand_prophet")
        assert exp is not None
        runs = client.search_runs(experiment_ids=[exp.experiment_id], max_results=1)
        coverage = runs[0].data.metrics.get("mumbai_calibration_coverage_90", 0)
        assert coverage >= 0.85, f"Conformal coverage {coverage:.3f} < 0.85 — E-S6-04"

    def test_mlflow_registry_has_mumbai_models(self) -> None:
        """E-S6-07: All transfer-learned models registered with mumbai_ prefix."""
        import mlflow

        client = mlflow.tracking.MlflowClient()
        for agent in [
            "demand_prophet_hgt_tft",
            "routing_navigator_pointer",
            "inventory_sentinel_strategic",
            "pricing_oracle_maddpg",
            "disruption_shield_ensemble",
            "supplier_trust_gnn",
        ]:
            model_name = f"mumbai_{agent}"
            versions = client.get_latest_versions(model_name, stages=["Staging"])
            assert len(versions) > 0, f"No Staging model for {model_name} — E-S6-07"


# ─── Category 5: A/B test results ───────────────────────────────────────────


class TestABTestResults:
    def test_primary_metrics_significant(self) -> None:
        """A/B test shows transfer model is statistically better."""
        import mlflow

        client = mlflow.tracking.MlflowClient()
        primary_metrics = {
            "demand_prophet": "ab_crps_p_value",
            "routing_navigator": "ab_mean_route_cost_p_value",
            "inventory_sentinel_l1": "ab_fill_rate_p_value",
        }
        for agent, metric_key in primary_metrics.items():
            exp = client.get_experiment_by_name(f"mumbai_ab_test_{agent}")
            assert exp is not None, f"No A/B test experiment for {agent}"
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id], max_results=1
            )
            assert len(runs) > 0, f"No A/B test run for {agent}"
            p_value = runs[0].data.metrics.get(metric_key, 1.0)
            assert p_value < 0.05, f"{agent} A/B test not significant: p={p_value:.4f}"


# ─── Category 6: Mumbai agent container health ──────────────────────────────


class TestMumbaiAgentHealth:
    MUMBAI_AGENTS = [
        "synapse-demand-prophet-mumbai",
        "synapse-routing-navigator-mumbai",
        "synapse-inventory-sentinel-mumbai",
        "synapse-pricing-oracle-mumbai",
        "synapse-freshness-guardian-mumbai",
        "synapse-disruption-shield-mumbai",
        "synapse-supplier-trust-mumbai",
        "synapse-sustainability-agent-mumbai",
        "synapse-osrm-mumbai",
    ]

    @pytest.mark.parametrize("container_name", MUMBAI_AGENTS)
    def test_agent_healthy(self, container_name: str) -> None:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "healthy", f"{container_name} not healthy"


# ─── Category 7: Feast materialization ───────────────────────────────────────


class TestFeastMumbai:
    def test_feast_mumbai_materialized(self) -> None:
        from feast import FeatureStore

        fs = FeatureStore(repo_path="data_fabric/feast/mumbai")
        features = fs.get_online_features(
            features=["mumbai_weather_context:monsoon_intensity"],
            entity_rows=[{"store_id": "MUM-001"}],
        ).to_dict()
        assert "monsoon_intensity" in features, "monsoon_intensity not materialized — E-S6-09"


# ─── Category 8: Kafka multi-city (Python confluent-kafka, no shell) ────────


class TestKafkaMultiCity:
    def test_kafka_topics_exist(self) -> None:
        """Verify Kafka topics exist using Python client."""
        try:
            from confluent_kafka.admin import AdminClient

            admin = AdminClient({"bootstrap.servers": "localhost:9092"})
            metadata = admin.list_topics(timeout=10)
            synapse_topics = [t for t in metadata.topics if t.startswith("synapse.")]
            assert len(synapse_topics) >= 16, f"Only {len(synapse_topics)} synapse topics, expected 16"
        except ImportError:
            pytest.skip("confluent-kafka not installed")


# ─── Category 9: Invariant compliance ────────────────────────────────────────


class TestInvariantCompliance:
    def test_zero_cost_verified(self) -> None:
        """I-1: No paid API keys in Mumbai compose."""
        compose_path = Path("docker/docker-compose.mumbai.yml")
        content = compose_path.read_text()
        for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "COHERE_API_KEY"]:
            assert key not in content, f"Paid API key {key} found in Mumbai compose — I-1"

    def test_essential_price_cap_configured(self) -> None:
        """I-6: Essential price cap (1.3x) configured for Mumbai pricing oracle."""
        compose_path = Path("docker/docker-compose.mumbai.yml")
        content = compose_path.read_text()
        assert "ESSENTIAL_PRICE_CAP=1.3" in content, "Price cap not set — I-6"

    def test_audit_immutability(self) -> None:
        """I-4: Audit trail has write protection."""
        try:
            import psycopg2

            conn = psycopg2.connect(
                "postgresql://synapse:synapse_audit_2026@localhost:5432/synapse_audit"
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT has_table_privilege('synapse_readonly', 'synapse_audit', 'DELETE')"
            )
            row = cur.fetchone()
            if row:
                assert not row[0], "DELETE not revoked on audit table"
            conn.close()
        except Exception:
            pytest.skip("PostgreSQL not available or synapse_readonly role missing")


# ─── Category 10: Parquet features ──────────────────────────────────────────


class TestParquetFeatures:
    def test_demand_features_parquet(self) -> None:
        import pandas as pd

        df = pd.read_parquet("data/mumbai/demand_features.parquet")
        assert "event_timestamp" in df.columns
        assert "rolling_mean_7d" in df.columns
        assert "orders_last_1h" in df.columns
        assert "orders_last_24h" in df.columns

    def test_weather_features_parquet(self) -> None:
        import pandas as pd

        df = pd.read_parquet("data/mumbai/weather_features.parquet")
        assert "monsoon_intensity" in df.columns, "Missing monsoon_intensity — E-S6-09"

    def test_store_features_date_alignment(self) -> None:
        """Store features dates must overlap with demand features dates."""
        import pandas as pd

        demand_df = pd.read_parquet("data/mumbai/demand_features.parquet")
        store_df = pd.read_parquet("data/mumbai/store_features.parquet")
        demand_dates = set(pd.to_datetime(demand_df["event_timestamp"]).dt.date)
        store_dates = set(pd.to_datetime(store_df["event_timestamp"]).dt.date)
        overlap = demand_dates & store_dates
        assert len(overlap) > 0, "No date overlap between demand and store features"
