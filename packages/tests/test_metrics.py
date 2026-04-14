"""Tests for Prometheus metric declarations (I-10, I-13)."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

from synapse_common.metrics import (
    AGENT_INFO,
    CONFIDENCE_DISTRIBUTION,
    CONSENSUS_DEBATE_ROUNDS,
    CONSENSUS_DECISIONS_TOTAL,
    CONSENSUS_DURATION,
    CONSENSUS_PROPOSALS_RECEIVED,
    DECISIONS_TOTAL,
    ESCALATION_RATE,
    FILL_RATE,
    HITL_ESCALATIONS_TOTAL,
    HITL_OVERRIDES_TOTAL,
    INFERENCE_LATENCY,
    KAFKA_CONSUME_LAG,
    KAFKA_PRODUCE_TOTAL,
    OLLAMA_CACHE_HIT_RATE,
    OLLAMA_PREFILL_TOKENS,
    WASTE_RATE,
)


class TestMetricTypes:

    def test_info_metrics(self) -> None:
        assert isinstance(AGENT_INFO, Info)

    def test_histogram_metrics(self) -> None:
        for metric in (
            INFERENCE_LATENCY,
            CONFIDENCE_DISTRIBUTION,
            OLLAMA_PREFILL_TOKENS,
            CONSENSUS_DURATION,
            CONSENSUS_DEBATE_ROUNDS,
        ):
            assert isinstance(metric, Histogram)

    def test_counter_metrics(self) -> None:
        for metric in (
            DECISIONS_TOTAL,
            KAFKA_PRODUCE_TOTAL,
            CONSENSUS_DECISIONS_TOTAL,
            HITL_ESCALATIONS_TOTAL,
            HITL_OVERRIDES_TOTAL,
            CONSENSUS_PROPOSALS_RECEIVED,
        ):
            assert isinstance(metric, Counter)

    def test_gauge_metrics(self) -> None:
        for metric in (
            OLLAMA_CACHE_HIT_RATE,
            KAFKA_CONSUME_LAG,
            FILL_RATE,
            WASTE_RATE,
            ESCALATION_RATE,
        ):
            assert isinstance(metric, Gauge)


class TestMetricNames:

    def test_agent_info_name(self) -> None:
        assert AGENT_INFO._name == "synapse_agent"

    def test_inference_latency_name(self) -> None:
        assert INFERENCE_LATENCY._name == "synapse_inference_latency_seconds"

    def test_fill_rate_name(self) -> None:
        assert FILL_RATE._name == "synapse_fill_rate"
