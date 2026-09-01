"""SYNAPSE Orchestrator — Pydantic BaseSettings configuration."""

from __future__ import annotations

from pydantic import Field
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

    #: The I-5 escalation boundary (R5.4, ADR-054 D4). Reloadable, and read per
    #: validation through
    #: :class:`~orchestrator.guardrails.thresholds.ConfigConfidenceThresholdProvider`.
    #:
    #: ``ge=0.0`` is load-bearing, not decoration. Until task 12.1a,
    #: ``execute_consensus``'s ``@deal.pre`` hardcoded ``0.7``, which was an accidental
    #: backstop: a negative configured threshold crashed the choke point rather than
    #: dispatching. Now that the precondition is judged against the boundary in force, a
    #: negative threshold would make *every* decision satisfy the floor - fail-open, the
    #: one direction a guardrail must never fail (I-6). A malformed value is refused at
    #: construction, which is also what makes ``thresholds.py``'s documented I-7 claim
    #: ("a malformed environment makes ``OrchestratorConfig()`` raise", so a failed
    #: reload leaves the previous known-good boundary in force) true for ``-1.0`` and not
    #: only for ``"not-a-float"``.
    #:
    #: There is deliberately **no** ``le=1.0``. A boundary above ``1.0`` is a legitimate
    #: fail-closed knob - ``ConsensusDecision`` pins ``confidence <= 1``, so ``1.1``
    #: escalates everything - and removing it would take away an operator's kill switch
    #: to guard against nothing.
    #:
    #: ``default=`` IS THE KEYWORD FORM ON PURPOSE, AND IT IS LOAD-BEARING FOR THE TYPE
    #: CHECKER, NOT FOR PYDANTIC. This project configures no ``pydantic.mypy`` plugin
    #: (``pyproject.toml``'s ``[tool.mypy]`` has no ``plugins`` entry), so mypy synthesises
    #: ``__init__`` from pydantic v2's PEP-681 ``dataclass_transform`` instead, and that path
    #: recognises a field-specifier default only when it arrives as ``default=``. Written
    #: positionally as ``Field(0.7, ge=0.0)`` this field was synthesised as a REQUIRED
    #: keyword argument and ``mypy --strict orchestrator/`` reported
    #: ``Missing named argument "confidence_threshold"`` at 21 call sites - three of them
    #: production (``inference/serve.py`` x2, ``audit/cli.py``). Runtime behaviour is
    #: identical either way: ``default`` is ``Field``'s first positional parameter.
    #:
    #: **Never clear those errors by passing a value at a call site.**
    #: ``GuardrailEngine(confidence_threshold=config.confidence_threshold)`` consumes this,
    #: and ``thresholds.py`` records that the boundary is injected a single time at
    #: ``inference/serve.py``, so a call-site literal substitutes an unreviewed number for a
    #: committed one on the I-5 confidence gate. The reviewed default already exists; it was
    #: only ever invisible to the type checker.
    confidence_threshold: float = Field(default=0.7, ge=0.0)
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
