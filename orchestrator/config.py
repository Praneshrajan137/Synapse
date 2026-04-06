"""SYNAPSE Orchestrator — Pydantic BaseSettings configuration."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorConfig(BaseSettings):
    """All orchestrator knobs. Env vars prefixed with ``SYNAPSE_ORCHESTRATOR_``."""

    model_config = SettingsConfigDict(
        env_prefix="SYNAPSE_ORCHESTRATOR_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8085

    kafka_bootstrap_servers: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "synapse_graph_2026"

    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: int = 120

    postgresql_url: str = (
        "postgresql+asyncpg://synapse_app:synapse_app_2026@localhost:5432/synapse_audit"
    )

    pinecone_api_key: str | None = None
    pinecone_decision_cache_index: str = "synapse-decision-cache"
    pinecone_playbook_index: str = "synapse-playbooks"

    confidence_threshold: float = 0.7
    proposal_timeout_seconds: float = 2.0
    debate_timeout_seconds: float = 30.0
    debate_max_rounds: int = 3
    arbitration_timeout_seconds: float = 5.0
    execution_timeout_seconds: float = 10.0
    hitl_timeout_seconds: float = 300.0
    hitl_timeout_action: str = "defer"

    meta_rl_learning_rate: float = 0.001
    meta_rl_history_size: int = 100

    kv_cache_alert_threshold: float = 0.7
    recitation_interval: int = 10

    tier2_escalation_prob_threshold: float = 0.3
    semantic_cache_similarity_threshold: float = 0.92
    semantic_cache_ttl_hours: int = 24
