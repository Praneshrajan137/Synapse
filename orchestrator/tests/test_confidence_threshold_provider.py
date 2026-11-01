"""Unit tests for the reloadable I-5 escalation boundary (R5.4, ADR-054 D4).

Feature: purpose-achievement-audit, task 8.1. The universal statement over threshold
sequences is Property 24 (task 8.2); these are the example-class facts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.guardrails.rules import GuardrailEngine
from orchestrator.guardrails.thresholds import (
    ConfidenceThresholdProvider,
    ConfigConfidenceThresholdProvider,
    StaticConfidenceThresholdProvider,
    resolve_threshold_provider,
)


def _decision(confidence: float) -> ConsensusDecision:
    return ConsensusDecision(
        tier=DecisionTier.TIER_1,
        proposals=[],
        selected_action={},
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        audit_trace=["test"],
    )


class TestStaticProvider:
    def test_reports_its_pinned_value(self) -> None:
        provider = StaticConfidenceThresholdProvider(0.55)
        assert provider.current() == pytest.approx(0.55)

    def test_reload_is_a_documented_no_op(self) -> None:
        provider = StaticConfidenceThresholdProvider(0.55)
        provider.reload()
        assert provider.current() == pytest.approx(0.55)

    def test_satisfies_the_protocol(self) -> None:
        assert isinstance(StaticConfidenceThresholdProvider(0.7), ConfidenceThresholdProvider)


class TestConfigProvider:
    def test_reads_the_configured_threshold(self) -> None:
        settings = OrchestratorConfig(confidence_threshold=0.42)
        assert ConfigConfidenceThresholdProvider(settings).current() == pytest.approx(0.42)

    def test_reload_rebinds_and_mutates_no_settings_instance(self) -> None:
        """I-13/Pydantic discipline: reload builds a new instance, never writes to one."""
        first = OrchestratorConfig(confidence_threshold=0.60)
        second = OrchestratorConfig(confidence_threshold=0.90)
        provider = ConfigConfidenceThresholdProvider(first, settings_factory=lambda: second)

        provider.reload()

        assert provider.current() == pytest.approx(0.90)
        # The instance previously bound is untouched.
        assert first.confidence_threshold == pytest.approx(0.60)

    def test_failed_reload_leaves_the_previous_value_in_force(self) -> None:
        """I-7: a provider never substitutes a default, which would lower the gate."""

        def _broken() -> OrchestratorConfig:
            return OrchestratorConfig(confidence_threshold="not-a-float")  # type: ignore[arg-type]

        provider = ConfigConfidenceThresholdProvider(
            OrchestratorConfig(confidence_threshold=0.80),
            settings_factory=_broken,
        )

        with pytest.raises(ValidationError):
            provider.reload()

        assert provider.current() == pytest.approx(0.80)

    def test_satisfies_the_protocol(self) -> None:
        provider = ConfigConfidenceThresholdProvider(OrchestratorConfig())
        assert isinstance(provider, ConfidenceThresholdProvider)


class TestEngineReadsPerValidation:
    def test_a_float_is_still_accepted_and_coerced(self) -> None:
        engine = GuardrailEngine(confidence_threshold=0.7)
        assert isinstance(engine.threshold_provider, StaticConfidenceThresholdProvider)
        assert engine.confidence_threshold == pytest.approx(0.7)

    def test_resolve_passes_a_provider_through_unchanged(self) -> None:
        provider = StaticConfidenceThresholdProvider(0.7)
        assert resolve_threshold_provider(provider) is provider

    def test_escalation_boundary_follows_a_reload_with_no_reconstruction(self) -> None:
        """R5.4: the boundary moves with configuration, not with the process lifetime."""
        low = OrchestratorConfig(confidence_threshold=0.50)
        high = OrchestratorConfig(confidence_threshold=0.95)
        provider = ConfigConfidenceThresholdProvider(low, settings_factory=lambda: high)
        engine = GuardrailEngine(confidence_threshold=provider)

        passed_before, _ = engine.validate_decision(_decision(0.80))
        provider.reload()
        passed_after, violations = engine.validate_decision(_decision(0.80))

        assert passed_before is True
        assert passed_after is False
        assert any("0.95" in v for v in violations)
