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

CONSENSUS_DECISIONS_TOTAL = Counter(
    "synapse_consensus_decisions_total",
    "Total consensus decisions completed",
    ["tier", "outcome"],
)

CONSENSUS_DURATION = Histogram(
    "synapse_consensus_duration_seconds",
    "Consensus protocol duration",
    ["tier"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0, 60.0, 120.0],
)

CONSENSUS_DEBATE_ROUNDS = Histogram(
    "synapse_consensus_debate_rounds",
    "Debate rounds per consensus",
    ["tier"],
    buckets=[0, 1, 2, 3],
)

HITL_ESCALATIONS_TOTAL = Counter(
    "synapse_hitl_escalations_total",
    "Total HITL escalation events",
    ["reason"],
)

HITL_OVERRIDES_TOTAL = Counter(
    "synapse_hitl_overrides_total",
    "Total human override decisions",
    ["action"],
)

CONSENSUS_PROPOSALS_RECEIVED = Counter(
    "synapse_consensus_proposals_received",
    "Agent proposals received per consensus round",
    ["agent_name"],
)

# --- Sprint 7 distributed correctness (WS-1/WS-2) ----------------------------

BROWNOUT_DECISIONS_TOTAL = Counter(
    "synapse_brownout_decisions_total",
    "Decisions affected by brownout shedding, by level and city (ADR-028)",
    ["level", "city"],
)

OUTBOX_DISPATCH_TOTAL = Counter(
    "synapse_outbox_dispatch_total",
    "Outbox row dispatch outcomes by terminal status",
    ["status"],
)

OUTBOX_LAG_SECONDS = Gauge(
    "synapse_outbox_lag_seconds",
    "Age in seconds of the oldest PENDING audit_outbox row",
)

# Sprint 9 — Audit chain (ADR-033)
AUDIT_CHAIN_LENGTH = Gauge(
    "synapse_audit_chain_length",
    "Total rows in the chained audit table; monotonically increasing",
)

AUDIT_CHAIN_TAMPER_DETECTED = Counter(
    "synapse_audit_chain_tamper_detected_total",
    "Tamper events detected by synapse audit verify or the anchorer",
    ["source"],
)

# Sprint 9 — Data lifecycle & archival (WS-7)
ARCHIVE_ROWS_MOVED_TOTAL = Counter(
    "synapse_archive_rows_moved_total",
    "Audit rows successfully moved to the MinIO Parquet archive by the daily worker",
    ["table"],
)

# Sprint 8 — WS-3 Spec-as-Source-of-Truth (ADR-031)
REWARD_WEIGHT_DIVERGENCE_TOTAL = Counter(
    "synapse_reward_weight_divergence_total",
    "Reward-weight drift between spec.yaml-generated config and runtime kwargs "
    "(shadow mode, ADR-031)",
    ["agent", "key"],
)

# Sprint 8 — WS-8 Performance Hardening (ADR-032)
TIER_BUDGET_EXCEEDED_TOTAL = Counter(
    "synapse_tier_budget_exceeded_total",
    "Decisions whose handler latency exceeded its tier budget (ADR-032)",
    ["tier"],
)

# Sprint 11 / WS-12 — close the metric_truth gap (CURRENT.md C22).
# These three metrics existed only in alert rules under
# infrastructure/prometheus/rules/{demand_prophet,pricing_oracle}_invariants.yml
# — the alerts fired against them but no source module emitted them.
# scripts/observability/metric_truth.py flagged the drift; the agent
# pipelines (demand_prophet.inference.pipeline._build_forecasts,
# pricing_oracle.inference.pipeline._build_updates) now update them on
# every inference call.

# INV-DP-002: conformal 90% interval must achieve >=85% empirical coverage.
DEMAND_PROPHET_COVERAGE_P90 = Gauge(
    "synapse_demand_prophet_coverage_p90",
    "Empirical coverage of the 90% conformal interval (INV-DP-002, target >=0.85)",
    ["city"],
)

# INV-DP-006: no forecast horizon may be negative. The pipeline clamps
# negatives to 0.0 at build time AND increments this counter — the
# published payload is always safe; the counter records the pre-clamp
# incidence so the critical alert can fire even when output is safe.
DEMAND_PROPHET_NEGATIVE_HORIZON_TOTAL = Counter(
    "synapse_demand_prophet_negative_horizon_total",
    "Forecast horizon values that arrived negative from the model (INV-DP-006). "
    "Clamped to 0.0 at the output boundary; this counter records the pre-clamp "
    "incidence so the alert fires even though the published payload is safe.",
    ["sku_id", "horizon"],
)

# INV-PO-001: essential category items must never price above 1.3x base.
PRICING_ORACLE_ESSENTIAL_CAP_VIOLATION_TOTAL = Counter(
    "synapse_pricing_oracle_essential_cap_violation_total",
    "Essential-category items whose raw multiplier exceeded the 1.3x cap "
    "before clamping (INV-PO-001). Output is always safe (cap applied); "
    "this counter records the underlying pricing-model pressure.",
    ["sku_id"],
)
