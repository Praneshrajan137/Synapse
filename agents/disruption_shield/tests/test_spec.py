"""Auto-generated spec tests for disruption_shield from spec.yaml.

Regenerate with::

    python scripts/generate_tests_from_spec.py agents/disruption_shield/spec.yaml

Add the marker token  S P E C _ T E S T S _ H A N D _ W R I T T E N
(without spaces, prefixed with #) to opt out of regeneration once you
have curated real assertions on top of the generated stubs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse_common.fsm import AgentState

from agents.disruption_shield.state_machine import DisruptionShieldStateMachine

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "proto" / "domain" / "disruption_alert.schema.json"


@pytest.mark.integration
class TestInvDs001:
    """Invariant INV-DS-001: Anomaly score above threshold implies alert_level > 0

    Assertion: if ensemble_score > threshold then output.alert_level > 0
    """

    def test_inv_ds_001(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestInvDs002:
    """Invariant INV-DS-002: Pinecone playbook retrieval latency < 200ms

    Assertion: playbook_retrieval_latency_ms < 200
    """

    def test_inv_ds_002(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestInvDs003:
    """Invariant INV-DS-003: Every disruption alert includes a non-empty reasoning chain

    Assertion: len(output.reasoning_chain) > 0
    """

    def test_inv_ds_003(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestInvDs004:
    """Invariant INV-DS-004: Reward function is entirely self-contained â€” no cross-agent imports

    Assertion: ast_check: no import from agents.* except agents.disruption_shield
    """

    def test_inv_ds_004(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestInvDs005:
    """Invariant INV-DS-005: Output validates against disruption_alert.schema.json

    Assertion: jsonschema.validate(output, disruption_alert_schema) passes
    """

    def test_inv_ds_005(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestInvDs006:
    """Invariant INV-DS-006: Graceful degradation: if Pinecone unavailable, return cached playbooks

    Assertion: pinecone_down implies fallback_to_cache and output.confidence < 0.7
    """

    def test_inv_ds_006(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestInvDs007:
    """Invariant INV-DS-007: Ensemble score is a weighted combination in [0, 1]

    Assertion: 0.0 <= output.ensemble_score <= 1.0
    """

    def test_inv_ds_007(self) -> None:
        pytest.skip("INTEGRATION: assertion in spec.yaml -- wired in tests/integration/ or tests/oracle/")


@pytest.mark.integration
class TestPreDs001:
    """Precondition PRE-DS-001: Supply chain graph node IDs are non-empty

    Check: len(node_ids) > 0
    """

    def test_pre_ds_001_valid(self) -> None:
        pytest.skip("INTEGRATION: precondition exercised in tests/integration/")

    def test_pre_ds_001_invalid(self) -> None:
        pytest.skip("INTEGRATION: violation path exercised in tests/integration/")


@pytest.mark.integration
class TestPreDs002:
    """Precondition PRE-DS-002: Time-series feature matrix has at least one row

    Check: feature_matrix.shape[0] > 0
    """

    def test_pre_ds_002_valid(self) -> None:
        pytest.skip("INTEGRATION: precondition exercised in tests/integration/")

    def test_pre_ds_002_invalid(self) -> None:
        pytest.skip("INTEGRATION: violation path exercised in tests/integration/")


@pytest.mark.integration
class TestPreDs003:
    """Precondition PRE-DS-003: Anomaly threshold is in (0, 1)

    Check: 0.0 < anomaly_threshold < 1.0
    """

    def test_pre_ds_003_valid(self) -> None:
        pytest.skip("INTEGRATION: precondition exercised in tests/integration/")

    def test_pre_ds_003_invalid(self) -> None:
        pytest.skip("INTEGRATION: violation path exercised in tests/integration/")


@pytest.mark.integration
class TestPostDs001:
    """Postcondition POST-DS-001: All output fields are non-null

    Check: all(v is not None for v in output.__dict__.values())
    """

    def test_post_ds_001(self) -> None:
        pytest.skip("INTEGRATION: postcondition exercised in tests/integration/")


@pytest.mark.integration
class TestPostDs002:
    """Postcondition POST-DS-002: Timestamp is valid ISO-8601

    Check: datetime.fromisoformat(output.timestamp) is not None
    """

    def test_post_ds_002(self) -> None:
        pytest.skip("INTEGRATION: postcondition exercised in tests/integration/")


@pytest.mark.integration
class TestPostDs003:
    """Postcondition POST-DS-003: Confidence in [0, 1]

    Check: 0.0 <= output.confidence <= 1.0
    """

    def test_post_ds_003(self) -> None:
        pytest.skip("INTEGRATION: postcondition exercised in tests/integration/")


@pytest.mark.integration
class TestPostDs004:
    """Postcondition POST-DS-004: Kafka message published to synapse.disruption.alert

    Check: kafka_publish_success == True
    """

    def test_post_ds_004(self) -> None:
        pytest.skip("INTEGRATION: postcondition exercised in tests/integration/")


class TestStateMachine:
    """State machine for disruption_shield (real, not skipped)."""

    def test_initial_state(self) -> None:
        sm = DisruptionShieldStateMachine()
        assert sm.state == AgentState.IDLE

    def test_transition_idle_to_proposing(self) -> None:
        sm = DisruptionShieldStateMachine()
        assert sm.state == AgentState.IDLE
        ok = sm.transition("disruption_signal_received")
        assert ok is True
        assert sm.state == AgentState.PROPOSING

    def test_transition_proposing_to_debating(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        assert sm.state == AgentState.PROPOSING
        ok = sm.transition("proposal_submitted")
        assert ok is True
        assert sm.state == AgentState.DEBATING

    def test_transition_debating_to_executing(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        sm.transition("proposal_submitted")
        assert sm.state == AgentState.DEBATING
        ok = sm.transition("consensus_reached")
        assert ok is True
        assert sm.state == AgentState.EXECUTING

    def test_transition_executing_to_learning(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        sm.transition("proposal_submitted")
        sm.transition("consensus_reached")
        assert sm.state == AgentState.EXECUTING
        ok = sm.transition("execution_confirmed")
        assert ok is True
        assert sm.state == AgentState.LEARNING

    def test_transition_learning_to_idle(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        sm.transition("proposal_submitted")
        sm.transition("consensus_reached")
        sm.transition("execution_confirmed")
        assert sm.state == AgentState.LEARNING
        ok = sm.transition("policy_updated")
        assert ok is True
        assert sm.state == AgentState.IDLE

    def test_transition_proposing_to_error(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        assert sm.state == AgentState.PROPOSING
        ok = sm.transition("exception_raised")
        assert ok is True
        assert sm.state == AgentState.ERROR

    def test_transition_executing_to_error(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        sm.transition("proposal_submitted")
        sm.transition("consensus_reached")
        assert sm.state == AgentState.EXECUTING
        ok = sm.transition("exception_raised")
        assert ok is True
        assert sm.state == AgentState.ERROR

    def test_transition_error_to_idle(self) -> None:
        sm = DisruptionShieldStateMachine()
        sm.transition("disruption_signal_received")
        sm.transition("exception_raised")
        assert sm.state == AgentState.ERROR
        ok = sm.transition("error_handled")
        assert ok is True
        assert sm.state == AgentState.IDLE

    def test_invalid_trigger_returns_false(self) -> None:
        sm = DisruptionShieldStateMachine()
        assert sm.transition("__nonsense__") is False
        assert sm.state == AgentState.IDLE


class TestSchemaArtefact:
    """The disruption_shield output schema must remain a valid JSON Schema."""

    def test_schema_loads(self) -> None:
        data = json.loads(SCHEMA_PATH.read_text())
        assert data.get("$schema", "").startswith("http")
        assert "properties" in data


@pytest.mark.metamorphic
class TestMrDs001:
    """Metamorphic MR-DS-001: Increasing anomaly magnitude implies higher or equal alert_level

    Transform: scale anomaly features by factor 2x
    Expected:  output.alert_level(2x) >= output.alert_level(1x)
    """

    def test_mr_ds_001(self) -> None:
        pytest.skip("Asserted in test_metamorphic.py against the trained model")


@pytest.mark.metamorphic
class TestMrDs002:
    """Metamorphic MR-DS-002: Adding affected nodes increases ensemble score

    Transform: add 3 anomalous nodes to supply chain graph
    Expected:  ensemble_score increases or stays equal
    """

    def test_mr_ds_002(self) -> None:
        pytest.skip("Asserted in test_metamorphic.py against the trained model")


@pytest.mark.metamorphic
class TestMrDs003:
    """Metamorphic MR-DS-003: Removing all anomalies results in alert_level = 0

    Transform: set all feature values to nominal range
    Expected:  output.alert_level == 0
    """

    def test_mr_ds_003(self) -> None:
        pytest.skip("Asserted in test_metamorphic.py against the trained model")

