"""
SYNAPSE Metrics — Prometheus metrics exposed by every agent.
Includes KV-cache metrics (I-13) and tier latency metrics (I-10).
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

AGENT_INFO = Info("synapse_agent", "Agent metadata")

INFERENCE_LATENCY = Histogram(
    "synapse_inference_latency_seconds",
    "Inference latency per agent",
    ["agent_name", "tier"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0, 60.0, 120.0],
)

DECISIONS_TOTAL = Counter(
    "synapse_decisions_total",
    "Total decisions made",
    ["agent_name", "tier", "outcome"],
)

CONFIDENCE_DISTRIBUTION = Histogram(
    "synapse_confidence",
    "Decision confidence distribution",
    ["agent_name"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

OLLAMA_CACHE_HIT_RATE = Gauge(
    "synapse_ollama_cache_hit_rate",
    "Ollama KV-cache hit rate",
    ["model", "tier"],
)

OLLAMA_PREFILL_TOKENS = Histogram(
    "synapse_ollama_prefill_tokens",
    "Ollama prefill tokens per request",
    ["model", "tier"],
    buckets=[100, 500, 1000, 2000, 5000, 10000, 20000, 50000],
)

KAFKA_PRODUCE_TOTAL = Counter(
    "synapse_kafka_produce_total",
    "Total Kafka messages produced",
    ["topic"],
)

KAFKA_CONSUME_LAG = Gauge(
    "synapse_kafka_consume_lag",
    "Kafka consumer lag",
    ["topic", "consumer_group"],
)

FILL_RATE = Gauge("synapse_fill_rate", "Current fill rate", ["store_id"])
WASTE_RATE = Gauge("synapse_waste_rate", "Current waste rate", ["store_id"])
ESCALATION_RATE = Gauge("synapse_escalation_rate", "HITL escalation rate")
