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

# WS-1 Resilience Mesh
BREAKER_STATE = Gauge(
    "synapse_breaker_state",
    "Circuit breaker state per named dependency (0=closed, 1=half_open, 2=open)",
    ["name"],
)

BROWNOUT_DECISIONS_TOTAL = Counter(
    "synapse_brownout_decisions_total",
    "Decisions shed or downgraded by the brownout policy",
    ["level", "city"],
)

# WS-2 Distributed Correctness
OUTBOX_LAG_SECONDS = Gauge(
    "synapse_outbox_lag_seconds",
    "Age in seconds of the oldest PENDING audit_outbox row",
)

OUTBOX_DISPATCH_TOTAL = Counter(
    "synapse_outbox_dispatch_total",
    "Outbox rows dispatched to Kafka by status",
    ["status"],
)

IDEMPOTENT_HIT_TOTAL = Counter(
    "synapse_idempotent_hit_total",
    "Idempotency-Key replay outcomes",
    ["outcome"],
)

# WS-4 Observability cost-telemetry shell
LLM_TOKENS = Histogram(
    "synapse_llm_tokens",
    "Ollama tokens per LLM call by tier/model/direction",
    ["tier", "model", "direction"],
    buckets=[50, 100, 250, 500, 1000, 2000, 5000, 10000, 20000, 50000],
)

# Sprint 8 — WS-3 Spec-as-Source-of-Truth
REWARD_WEIGHT_DIVERGENCE_TOTAL = Counter(
    "synapse_reward_weight_divergence_total",
    "Reward-weight drift between spec.yaml-generated config and runtime kwargs "
    "(shadow mode, ADR-031)",
    ["agent", "key"],
)

SPEC_VALIDATION_FAILED_TOTAL = Counter(
    "synapse_spec_validation_failed_total",
    "Spec validation failures emitted by scripts/spec_cli.py validate",
    ["agent", "severity"],
)

# Sprint 8 — WS-8 Performance Hardening
TIER_BUDGET_EXCEEDED_TOTAL = Counter(
    "synapse_tier_budget_exceeded_total",
    "Decisions whose handler latency exceeded its tier budget (ADR-032)",
    ["tier"],
)

# Sprint 8 — WS-5 AI Eval harness
EVAL_TRACE_LATENCY = Histogram(
    "synapse_eval_trace_latency_seconds",
    "Wall-clock latency per golden-trace replay",
    ["tier", "city"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 60.0, 120.0],
)

EVAL_TRACE_OUTCOME_TOTAL = Counter(
    "synapse_eval_trace_outcome_total",
    "Golden-trace replay outcomes",
    ["tier", "city", "outcome"],
)

# Sprint 9 — WS-6 Supply Chain Security
AUDIT_CHAIN_LENGTH = Gauge(
    "synapse_audit_chain_length",
    "Total rows in the chained audit table; monotonically increasing",
)

AUDIT_CHAIN_TAMPER_DETECTED = Counter(
    "synapse_audit_chain_tamper_detected_total",
    "Tamper events detected by synapse audit verify or the anchorer",
    ["source"],
)

# Sprint 9 — WS-7 Data Lifecycle & Compliance
ARCHIVE_ROWS_MOVED_TOTAL = Counter(
    "synapse_archive_rows_moved_total",
    "Audit rows successfully moved to the MinIO Parquet archive by the daily worker",
    ["table"],
)

PII_REDACTION_TOTAL = Counter(
    "synapse_pii_redaction_total",
    "Structlog log records where the redact_pii processor scrubbed at least one field",
    ["field"],
)

# Sprint 9 — WS-5 carryover: live LLM-as-judge
LLM_JUDGE_LATENCY_SECONDS = Histogram(
    "synapse_llm_judge_latency_seconds",
    "Wall-clock latency per LLM-as-judge scoring call (live mode only)",
    ["model"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# Sprint 9 — WS-5 carryover: drift scheduler
DRIFT_PSI_VALUE = Gauge(
    "synapse_drift_psi_value",
    "Most-recent Population Stability Index per Feast feature view, keyed by city",
    ["feature", "city"],
)
