"""Unit tests for Phase 1.5 firehose signal emission (orchestrator -> Kafka).

Guards the dead-channel fix: agents wrap their domain outputs in
``AgentProposal.payload`` (e.g. ``{"forecasts": [...]}``); the orchestrator must
event-source the INNER objects onto each channel topic, because the FE
per-channel schemas are ``.strict()`` and would reject the wrapper (the Sprint-15
dead-channel defect class). Verifies forwarding, topic mapping, the partition
key, best-effort error handling, and the anti-regression invariant that we emit
inner items, not the wrapper.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.provenance import ConfidenceBasis, Provenance

from orchestrator.consensus.firehose_signals import (
    METRICS_TOPIC,
    SIGNAL_CHANNELS,
    emit_agent_metrics,
    emit_agent_signals,
)


class _FakeProducer:
    def __init__(self, *, raise_on: str | None = None) -> None:
        self.calls: list[tuple[str, Any, str | None]] = []
        self._raise_on = raise_on

    def produce(
        self,
        topic: str,
        value: Any,
        key: str | None = None,
        headers: Any = None,
    ) -> None:
        if self._raise_on is not None and topic == self._raise_on:
            raise RuntimeError("kafka down")
        self.calls.append((topic, value, key))


def _proposal(agent_name: AgentName, payload: dict[str, Any]) -> AgentProposal:
    return AgentProposal(
        agent_name=agent_name,
        decision_id=uuid4(),
        utility_score=0.7,
        confidence=0.7,
        justification_trace=["t"],
        payload=payload,
        tier=DecisionTier.TIER_2,
    )


_FORECAST = {
    "sku_id": "SKU-1",
    "store_id": "STORE-1",
    "forecast_timestamp": "2026-06-16T00:00:00Z",
    "horizons": {"1h": 5.0},
    "lower_90": {"1h": 3.0},
    "upper_90": {"1h": 7.0},
    "confidence": 0.8,
    "drift_detected": False,
}


def test_none_producer_is_noop() -> None:
    assert (
        emit_agent_signals(None, [_proposal(AgentName.DEMAND_PROPHET, {"forecasts": [_FORECAST]})])
        == 0
    )


def test_demand_emits_inner_forecasts_not_wrapper() -> None:
    prod = _FakeProducer()
    payload = {"forecasts": [_FORECAST, _FORECAST], "store_id": "STORE-1", "num_skus": 2}
    n = emit_agent_signals(prod, [_proposal(AgentName.DEMAND_PROPHET, payload)])
    assert n == 2
    assert [c[0] for c in prod.calls] == ["synapse.demand.forecast"] * 2
    # Load-bearing invariant: emit the INNER forecast, never the wrapper.
    assert prod.calls[0][1] == _FORECAST
    assert "forecasts" not in prod.calls[0][1]


def test_pricing_and_freshness_topics() -> None:
    prod = _FakeProducer()
    emit_agent_signals(
        prod,
        [
            _proposal(AgentName.PRICING_ORACLE, {"updates": [{"pricing_id": "p"}]}),
            _proposal(
                AgentName.FRESHNESS_GUARDIAN, {"alerts": [{"alert_id": "a"}, {"alert_id": "b"}]}
            ),
        ],
    )
    assert [c[0] for c in prod.calls] == [
        "synapse.pricing.update",
        "synapse.freshness.alert",
        "synapse.freshness.alert",
    ]


def test_unmapped_agent_skipped() -> None:
    prod = _FakeProducer()
    assert emit_agent_signals(prod, [_proposal(AgentName.INVENTORY_SENTINEL, {"x": [1]})]) == 0
    assert prod.calls == []


def test_empty_or_missing_list_emits_nothing() -> None:
    prod = _FakeProducer()
    assert emit_agent_signals(prod, [_proposal(AgentName.DEMAND_PROPHET, {})]) == 0
    assert emit_agent_signals(prod, [_proposal(AgentName.PRICING_ORACLE, {"updates": []})]) == 0


def test_produce_error_is_swallowed() -> None:
    prod = _FakeProducer(raise_on="synapse.demand.forecast")
    # Best-effort (I-7): must not raise; reports 0 successful emits.
    assert (
        emit_agent_signals(prod, [_proposal(AgentName.DEMAND_PROPHET, {"forecasts": [_FORECAST]})])
        == 0
    )


def test_decision_id_is_partition_key() -> None:
    prod = _FakeProducer()
    prop = _proposal(AgentName.DEMAND_PROPHET, {"forecasts": [_FORECAST]})
    emit_agent_signals(prod, [prop])
    assert prod.calls[0][2] == str(prop.decision_id)


def test_registry_maps_only_verified_channels() -> None:
    # Every channel we emit to must be a real firehose topic (no typos / drift).
    assert {agent: topic for agent, (topic, _) in SIGNAL_CHANNELS.items()} == {
        AgentName.DEMAND_PROPHET: "synapse.demand.forecast",
        AgentName.PRICING_ORACLE: "synapse.pricing.update",
        AgentName.FRESHNESS_GUARDIAN: "synapse.freshness.alert",
    }


# ── ADR-053: live per-agent telemetry producer (the `metric` channel) ─────────


def test_metrics_none_producer_is_noop() -> None:
    assert emit_agent_metrics(None, [_proposal(AgentName.DEMAND_PROPHET, {})]) == 0


def test_metrics_emits_one_event_per_proposal_to_metrics_topic() -> None:
    prod = _FakeProducer()
    props = [
        _proposal(AgentName.DEMAND_PROPHET, {}),
        _proposal(AgentName.ROUTING_NAVIGATOR, {}),
    ]
    n = emit_agent_metrics(prod, props)
    assert n == 2
    assert [c[0] for c in prod.calls] == [METRICS_TOPIC, METRICS_TOPIC]
    payload = prod.calls[0][1]
    # Matches proto/domain/agent_metric.schema.json required fields.
    assert set(payload) >= {"agent_name", "decision_id", "tier", "confidence", "degraded", "ts"}
    assert payload["agent_name"] == "demand_prophet"
    assert payload["tier"] == "tier_2"
    assert prod.calls[0][2] == str(props[0].decision_id)


def test_metrics_degraded_reflects_provenance() -> None:
    prod = _FakeProducer()
    prop = AgentProposal(
        agent_name=AgentName.ROUTING_NAVIGATOR,
        decision_id=uuid4(),
        utility_score=0.4,
        confidence=0.5,
        justification_trace=["fallback"],
        payload={},
        tier=DecisionTier.TIER_1,
        provenance=Provenance.degraded_fallback(),
    )
    emit_agent_metrics(prod, [prop])
    payload = prod.calls[0][1]
    assert payload["degraded"] is True
    assert payload["confidence_basis"] == ConfidenceBasis.FALLBACK_FLOOR.value


def test_metrics_produce_error_is_swallowed() -> None:
    prod = _FakeProducer(raise_on=METRICS_TOPIC)
    # Best-effort (I-7): telemetry never blocks or fails a decision.
    assert emit_agent_metrics(prod, [_proposal(AgentName.DEMAND_PROPHET, {})]) == 0
