"""
SYNAPSE Sprint 3 — Cross-Agent Integration Tests.
Tests all Sprint 3 agents individually and their cross-agent interactions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ── Section 1: Agent Health Endpoints ──


class TestFreshnessGuardianHealth:
    """Freshness Guardian basic operational tests."""

    def test_pipeline_produces_valid_output(self) -> None:
        from agents.freshness_guardian.inference.pipeline import (
            FreshnessGuardianPipeline,
            FreshnessRequest,
        )

        pipeline = FreshnessGuardianPipeline()
        result = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001", sku_id="SKU-0001",
            days_since_receipt=3.0, initial_shelf_life_days=7,
        ))
        assert 0 <= result.quality_score <= 1
        assert 0 <= result.markdown_pct <= 100
        assert isinstance(result.fssai_compliant, bool)
        assert result.confidence > 0

    def test_schema_compliance(self) -> None:
        import jsonschema

        from agents.freshness_guardian.inference.pipeline import (
            FreshnessGuardianPipeline,
            FreshnessRequest,
        )

        schema = json.loads(
            (PROJECT_ROOT / "proto" / "domain" / "freshness_alert.schema.json").read_text()
        )
        pipeline = FreshnessGuardianPipeline()
        result = pipeline.assess(FreshnessRequest(
            store_id="BLR-DS-001", sku_id="SKU-0001",
            days_since_receipt=2.0, initial_shelf_life_days=7,
        ))
        jsonschema.validate(result.model_dump(mode="json"), schema)


class TestPricingOracleHealth:
    """Pricing Oracle basic operational tests."""

    def test_pipeline_produces_valid_output(self) -> None:
        from agents.pricing_oracle.inference.pipeline import (
            PricingOraclePipeline,
        )

        pipeline = PricingOraclePipeline()
        results = pipeline.price(
            sku_ids=["SKU-0001", "SKU-0002"],
            store_id="BLR-DS-001",
            categories=["essential", "snack"],
            base_prices=[100.0, 50.0],
        )
        assert len(results) >= 1
        for r in results:
            # PricingUpdate Pydantic model — access via attributes.
            assert r.confidence >= 0
            assert r.final_price > 0

    def test_essential_cap_enforced(self) -> None:
        """INV-PO-001: Essential multiplier NEVER exceeds 1.3x."""
        from agents.pricing_oracle.inference.pipeline import (
            PricingOraclePipeline,
        )

        pipeline = PricingOraclePipeline()
        results = pipeline.price(
            sku_ids=["SKU-0001"],
            store_id="BLR-DS-001",
            categories=["essential"],
            base_prices=[100.0],
        )
        for r in results:
            if getattr(r, "is_essential", False):
                assert r.multiplier <= 1.3


class TestDisruptionShieldHealth:
    """Disruption Shield basic operational tests."""

    def test_anomaly_ensemble_produces_scores(self) -> None:
        import numpy as np

        from agents.disruption_shield.models.anomaly_ensemble import (
            AnomalyEnsemble,
            EnsembleResult,
        )

        ensemble = AnomalyEnsemble()
        # Fit the isolation forest so decision_function is defined.
        training = np.random.randn(32, 10).astype(np.float32)
        ensemble.isolation_forest.fit(training)

        features = np.random.randn(5, 10).astype(np.float32)
        result = ensemble.score(features)
        assert isinstance(result, EnsembleResult)
        assert 0 <= result.ensemble_score <= 1


class TestSupplierTrustHealth:
    """Supplier Trust basic operational tests."""

    def test_pipeline_trust_floor(self) -> None:
        """INV-ST-001: New vendor trust floor = 0.3."""
        from agents.supplier_trust.inference.pipeline import (
            SupplierTrustPipeline,
        )

        pipeline = SupplierTrustPipeline()
        # is_new_vendor=True takes the _score_new_vendor path; empty history
        # would otherwise raise PRE-ST-002 for an existing supplier.
        result = pipeline.score(
            supplier_id="NEW-SUP-999",
            delivery_history=[],
            is_new_vendor=True,
        )
        assert result.trust_score >= 0.3


class TestSustainabilityAgentHealth:
    """Sustainability Agent basic operational tests."""

    def test_carbon_tracking(self) -> None:
        from agents.sustainability_agent.models.carbon import CarbonTracker

        tracker = CarbonTracker()
        co2 = tracker.track_route(fuel_liters=5.0, distance_km=20.0)
        assert co2 >= 0


# ── Section 2: Cross-Agent A2A Communication ──


class TestCrossAgentA2A:
    """Test A2A JSON-RPC communication between Sprint 3 agents."""

    def test_freshness_guardian_a2a_proposal(self) -> None:
        from agents.freshness_guardian.a2a.handler import FreshnessGuardianA2AHandler

        handler = FreshnessGuardianA2AHandler()
        response = handler.handle_request({
            "jsonrpc": "2.0",
            "method": "proposal",
            "params": {"store_id": "BLR-DS-001", "sku_ids": ["SKU-0001"]},
            "id": "test-1",
        })
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert response["id"] == "test-1"

    def test_a2a_unknown_method_returns_error(self) -> None:
        from agents.freshness_guardian.a2a.handler import FreshnessGuardianA2AHandler

        handler = FreshnessGuardianA2AHandler()
        response = handler.handle_request({
            "jsonrpc": "2.0",
            "method": "unknown_method",
            "params": {},
            "id": "test-err",
        })
        assert "error" in response
        assert response["error"]["code"] == -32601


# ── Section 3: Schema Compliance ──


class TestSchemaCompliance:
    """Verify all Sprint 3 agent outputs match their proto schemas (I-3)."""

    @pytest.mark.parametrize("schema_name", [
        "freshness_alert",
        "pricing_update",
        "disruption_alert",
        "supplier_score",
        "carbon_report",
        "twin_state",
    ])
    def test_schema_is_valid_json_schema(self, schema_name: str) -> None:
        import jsonschema

        path = PROJECT_ROOT / "proto" / "domain" / f"{schema_name}.schema.json"
        assert path.exists(), f"Missing schema: {path}"
        schema = json.loads(path.read_text())
        assert "required" in schema
        assert "properties" in schema
        jsonschema.Draft7Validator.check_schema(schema)


# ── Section 4: Agent Card Validation ──


class TestAgentCards:
    """Verify all Sprint 3 agent cards are A2A compliant."""

    @pytest.mark.parametrize("agent_name", [
        "freshness_guardian",
        "pricing_oracle",
        "disruption_shield",
        "supplier_trust",
        "sustainability_agent",
    ])
    def test_agent_card_valid(self, agent_name: str) -> None:
        card_path = PROJECT_ROOT / "agents" / agent_name / "agent_card.json"
        assert card_path.exists(), f"Missing agent card: {card_path}"
        card = json.loads(card_path.read_text())
        assert card.get("protocol") in ("a2a", "a2a-v1"), f"{agent_name}: wrong protocol"
        assert card.get("agent_name") == agent_name, f"{agent_name}: wrong agent_name"
        assert "methods" in card or "skills" in card, f"{agent_name}: no methods/skills"


# ── Section 5: Reward Isolation (I-2) ──


class TestRewardIsolation:
    """Verify all agents have isolated reward functions (I-2)."""

    @pytest.mark.parametrize("agent_name", [
        "demand_prophet",
        "routing_navigator",
        "inventory_sentinel",
        "freshness_guardian",
        "pricing_oracle",
        "disruption_shield",
        "supplier_trust",
        "sustainability_agent",
    ])
    def test_no_cross_agent_imports_in_rewards(self, agent_name: str) -> None:
        import ast

        rewards_path = PROJECT_ROOT / "agents" / agent_name / "training" / "rewards.py"
        if not rewards_path.exists():
            pytest.skip(f"No rewards.py for {agent_name}")

        tree = ast.parse(rewards_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "agents." in node.module:
                assert agent_name in node.module, (
                    f"{agent_name}: cross-agent import '{node.module}' violates I-2"
                )


# ── Section 6: Spec Validation ──


class TestSpecValidation:
    """Verify all Sprint 3 spec.yaml files validate against the schema."""

    @pytest.mark.parametrize("agent_name", [
        "freshness_guardian",
        "pricing_oracle",
        "disruption_shield",
        "supplier_trust",
        "sustainability_agent",
    ])
    def test_spec_yaml_exists_and_has_required_fields(self, agent_name: str) -> None:
        import yaml

        spec_path = PROJECT_ROOT / "agents" / agent_name / "spec.yaml"
        assert spec_path.exists(), f"Missing spec: {spec_path}"
        spec = yaml.safe_load(spec_path.read_text())
        assert spec["agent_name"] == agent_name
        assert "invariants" in spec
        assert len(spec["invariants"]) >= 1


# ── Section 7: Dockerfile Existence ──


class TestDockerfiles:
    """Verify all Sprint 3 Dockerfiles exist."""

    @pytest.mark.parametrize("component", [
        "agents/freshness_guardian",
        "agents/pricing_oracle",
        "agents/disruption_shield",
        "agents/supplier_trust",
        "agents/sustainability_agent",
        "digital_twin",
    ])
    def test_dockerfile_exists(self, component: str) -> None:
        path = PROJECT_ROOT / component / "Dockerfile"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "HEALTHCHECK" in content, f"{component}: missing HEALTHCHECK"
        assert "synapse" in content.lower(), f"{component}: missing synapse user"
