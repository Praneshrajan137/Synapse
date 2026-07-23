"""Fan agent domain outputs onto the firehose topics (Phase 1.5).

Agents return their domain output *inside* the ``AgentProposal.payload`` wrapper
to the orchestrator over A2A; nothing ever published those signals to Kafka, so
6 of the 9 firehose channels were dead (the FE ``Live Markets`` and
``Demand Prophet`` surfaces rendered nothing live). This module event-sources
each agent's domain output onto its channel topic as the orchestrator collects
proposals — ADR-038-clean (Kafka for event-sourcing/telemetry, NOT inter-agent
RPC, which stays on A2A).

Schema contract (the load-bearing detail): the FE validates each channel against
the ``proto/domain`` schema it mirrors, and those Zod schemas are ``.strict()``.
The agent payloads are *wrappers* around a list of domain objects, e.g.
``{"forecasts": [DemandForecast, ...], ...}`` — so we emit the INNER domain
objects, one event each, never the wrapper. Emitting the wrong shape is silently
rejected by the FE (the Sprint-15 dead-channel defect class), so a channel is
only added to ``SIGNAL_CHANNELS`` once its agent's wrapper shape is verified
against the FE ``@domain`` schema.

Best-effort (I-7): a missing producer or a produce error never breaks consensus.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

import structlog
from synapse_common.models import AgentName, AgentProposal

logger = structlog.get_logger(__name__)

# The live per-agent telemetry topic (topic 17). Registered in
# infrastructure/kafka/topics.json with api_firehose as a consumer, but had NO
# producer until ADR-053 — the FE `metric` channel was open-shape and dead.
METRICS_TOPIC = "synapse.metrics.agent"

# Extract the inner domain dicts the FE expects from an agent's proposal payload.
Extractor = Callable[[dict[str, Any]], Iterable[dict[str, Any]]]


def _items(key: str) -> Extractor:
    """Build an extractor that yields ``payload[key]`` (a list), defaulting to []."""

    def extract(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        value = payload.get(key, [])
        return list(value) if isinstance(value, list) else []

    return extract


# agent -> (firehose topic, extractor). Each emitted item is a single, already
# I-3-validated domain object matching the FE's .strict() per-channel schema.
#
# Verified wrapper shapes (agent a2a/handler.py -> FE frontend/src/domain/*.ts):
#   demand_prophet     payload={"forecasts": [...]}  -> demand-forecast.ts
#   pricing_oracle     payload={"updates":   [...]}  -> pricing-update.ts
#   freshness_guardian payload={"alerts":    [...]}  -> freshness-alert.ts
SIGNAL_CHANNELS: dict[AgentName, tuple[str, Extractor]] = {
    AgentName.DEMAND_PROPHET: ("synapse.demand.forecast", _items("forecasts")),
    AgentName.PRICING_ORACLE: ("synapse.pricing.update", _items("updates")),
    AgentName.FRESHNESS_GUARDIAN: ("synapse.freshness.alert", _items("alerts")),
    # Pending follow-ups (verify the handler wrapper shape against the FE schema
    # before enabling — emitting an unverified shape silently fails FE validation):
    #   routing_navigator -> synapse.routing.plan     (route-plan.ts)
    #   disruption_shield -> synapse.disruption.alert (disruption-alert.ts)
}


def emit_agent_signals(producer: Any, proposals: Iterable[AgentProposal]) -> int:
    """Publish each agent's domain output onto its firehose topic.

    Returns the number of events produced. No-op (returns 0) when ``producer`` is
    None — the orchestrator wires a real ``SynapseProducer`` in production
    (``orchestrator/inference/serve.py``), but tests and degraded boots may not.
    """
    if producer is None:
        return 0
    produced = 0
    for proposal in proposals:
        mapping = SIGNAL_CHANNELS.get(proposal.agent_name)
        if mapping is None:
            continue
        topic, extract = mapping
        try:
            for item in extract(proposal.payload):
                producer.produce(topic, item, key=str(proposal.decision_id))
                produced += 1
        except Exception as exc:  # noqa: BLE001 — telemetry is best-effort (I-7)
            logger.warning(
                "agent_signal_emit_failed",
                agent=str(proposal.agent_name),
                topic=topic,
                error=str(exc),
            )
    return produced


def emit_agent_metrics(producer: Any, proposals: Iterable[AgentProposal]) -> int:
    """Event-source one live telemetry event per proposal onto ``synapse.metrics.agent``.

    ADR-053: this closes the dead ``metric`` firehose channel by giving it a real
    producer. Each event is genuine measured data captured as consensus collects
    the proposal — agent, decision, tier, confidence, and whether that proposal's
    provenance ran an I-7 fallback. The payload matches
    ``proto/domain/agent_metric.schema.json`` (the FE validates it .strict()).

    Best-effort (I-7): a None/missing/broken producer never blocks or fails the
    decision. Returns the number of events produced.
    """
    if producer is None:
        return 0
    produced = 0
    for proposal in proposals:
        prov = proposal.provenance
        metric: dict[str, Any] = {
            "agent_name": str(proposal.agent_name),
            "decision_id": str(proposal.decision_id),
            "tier": str(proposal.tier.value),
            "confidence": proposal.confidence,
            "degraded": bool(prov is not None and prov.degraded),
            "ts": datetime.now(UTC).isoformat(),
        }
        if prov is not None:
            metric["confidence_basis"] = str(prov.confidence_basis.value)
        try:
            producer.produce(METRICS_TOPIC, metric, key=str(proposal.decision_id))
            produced += 1
        except Exception as exc:  # noqa: BLE001 — telemetry is best-effort (I-7)
            logger.warning(
                "agent_metric_emit_failed",
                agent=str(proposal.agent_name),
                error=str(exc),
            )
    return produced
