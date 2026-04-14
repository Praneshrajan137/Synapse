from __future__ import annotations

import json

import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


class OllamaResponseValidator:
    """Validates Ollama responses against expected JSON schema."""

    REQUIRED_FIELDS = {"agent_name", "utility_score", "confidence", "justification"}

    def validate(self, raw_response: str) -> tuple[bool, dict | None, str | None]:
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {e}"

        if not isinstance(parsed, dict):
            return False, None, "Response is not a JSON object"

        missing = self.REQUIRED_FIELDS - set(parsed.keys())
        if missing:
            return False, None, f"Missing required fields: {missing}"

        if not isinstance(parsed.get("utility_score"), (int, float)):
            return False, None, "utility_score must be numeric"

        if not (0.0 <= parsed.get("confidence", -1) <= 1.0):
            return False, None, "confidence must be in [0.0, 1.0]"

        return True, parsed, None


class TierRouter:
    """Routes to RL-only Tier 1 when LLM fails."""

    def __init__(self) -> None:
        self.validator = OllamaResponseValidator()
        self.fallback_count: int = 0

    def process_llm_response(self, raw_response: str) -> dict:
        valid, parsed, error = self.validator.validate(raw_response)

        if not valid:
            logger.warning(
                "llm_hallucination_detected",
                error=error,
                raw_response_preview=raw_response[:200],
                action="fallback_to_tier1_rl",
            )
            self.fallback_count += 1
            return self._tier1_rl_fallback()

        return parsed  # type: ignore[return-value]

    def _tier1_rl_fallback(self) -> dict:
        return {
            "agent_name": "orchestrator",
            "utility_score": 0.0,
            "confidence": 0.5,
            "justification": "Tier 1 RL-only fallback due to LLM response validation failure",
            "source": "tier1_rl_fallback",
            "tier": "TIER_1",
        }


class TestLLMHallucination:
    """Chaos logic validation: Ollama returns invalid JSON. System rejects via
    schema validation and falls back to Tier 1 RL-only within <100ms SLA."""

    def test_invalid_json_triggers_fallback(self, chaos_clock) -> None:
        """Completely invalid JSON is caught and triggers Tier 1 fallback."""
        router = TierRouter()

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = router.process_llm_response("This is not JSON at all {{{")

        assert result["source"] == "tier1_rl_fallback"
        chaos_clock.assert_within_sla(0.1, "Invalid JSON fallback")
        assert any(e.get("event") == "llm_hallucination_detected" for e in captured)

    def test_missing_required_fields_triggers_fallback(self, chaos_clock) -> None:
        """JSON missing required fields triggers fallback."""
        router = TierRouter()
        incomplete = json.dumps({"agent_name": "demand_prophet"})

        chaos_clock.start()
        result = router.process_llm_response(incomplete)

        assert result["source"] == "tier1_rl_fallback"
        chaos_clock.assert_within_sla(0.1, "LLM missing fields fallback")

    def test_invalid_confidence_range_triggers_fallback(self) -> None:
        """Confidence outside [0,1] range triggers fallback."""
        router = TierRouter()
        bad_confidence = json.dumps({
            "agent_name": "demand_prophet",
            "utility_score": 0.8,
            "confidence": 1.5,
            "justification": "test",
        })

        result = router.process_llm_response(bad_confidence)
        assert result["source"] == "tier1_rl_fallback"

    def test_non_numeric_utility_triggers_fallback(self) -> None:
        """String utility_score triggers fallback."""
        router = TierRouter()
        bad_utility = json.dumps({
            "agent_name": "demand_prophet",
            "utility_score": "high",
            "confidence": 0.9,
            "justification": "test",
        })

        result = router.process_llm_response(bad_utility)
        assert result["source"] == "tier1_rl_fallback"

    def test_valid_response_passes_through(self) -> None:
        """Valid LLM response passes validation without fallback."""
        router = TierRouter()
        valid = json.dumps({
            "agent_name": "demand_prophet",
            "utility_score": 0.85,
            "confidence": 0.92,
            "justification": "Demand forecast shows 15% increase due to IPL match",
        })

        result = router.process_llm_response(valid)
        assert result.get("source") != "tier1_rl_fallback"
        assert result["confidence"] == 0.92

    def test_fallback_counter_increments(self) -> None:
        """Each hallucination increments the fallback counter for monitoring."""
        router = TierRouter()

        router.process_llm_response("bad1")
        router.process_llm_response("bad2")
        router.process_llm_response("bad3")

        assert router.fallback_count == 3

    def test_empty_string_response(self, chaos_clock) -> None:
        """Empty string from Ollama (OOM, crash mid-generation) triggers fallback."""
        router = TierRouter()

        chaos_clock.start()
        result = router.process_llm_response("")

        assert result["source"] == "tier1_rl_fallback"
        chaos_clock.assert_within_sla(0.1, "Empty LLM response fallback")

    def test_partial_json_response(self, chaos_clock) -> None:
        """Truncated JSON (Ollama killed mid-stream) triggers fallback."""
        router = TierRouter()
        truncated = '{"agent_name": "demand_prophet", "utility_sc'

        chaos_clock.start()
        result = router.process_llm_response(truncated)

        assert result["source"] == "tier1_rl_fallback"
        chaos_clock.assert_within_sla(0.1, "Truncated LLM response fallback")

    def test_non_dict_json_triggers_fallback(self) -> None:
        """Valid JSON that is not a dict (e.g. array, number) triggers fallback."""
        router = TierRouter()

        for payload in ["42", '"hello"', "[1,2,3]", "true", "null"]:
            result = router.process_llm_response(payload)
            assert result["source"] == "tier1_rl_fallback", (
                f"Non-dict JSON '{payload}' was not rejected"
            )

    def test_negative_confidence_triggers_fallback(self) -> None:
        """Negative confidence triggers fallback."""
        router = TierRouter()
        bad = json.dumps({
            "agent_name": "test",
            "utility_score": 0.5,
            "confidence": -0.1,
            "justification": "test",
        })

        result = router.process_llm_response(bad)
        assert result["source"] == "tier1_rl_fallback"
