"""
SYNAPSE Orchestrator — KV-cache-aware context construction (ADR-021, I-13).

Three-layer protocol:
  Layer 1: Stable system-prompt prefix (byte-identical every invocation).
  Layer 2: Append-only context messages (never reorder, never remove).
  Layer 3: Deterministic JSON serialization (sort_keys, compact separators).
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from synapse_common.models import ContextMessage

SYSTEM_PROMPT: str = (
    "You are the SYNAPSE Orchestrator, a multi-agent consensus engine.\n"
    "You mediate between 8 specialized supply chain agents to produce optimal decisions.\n"
    "\n"
    "Available tools (all tiers):\n"
    "- rl_demand_forecast: Get RL policy demand forecast\n"
    "- rl_route_optimize: Get RL policy route optimization\n"
    "- rl_inventory_reorder: Get RL policy inventory reorder decision\n"
    "- feast_get_features: Retrieve features from Feast feature store\n"
    "- feast_get_entity: Get entity features by key\n"
    "- graph_query_supply_network: Query Neo4j supply network graph\n"
    "- graph_get_neighbors: Get graph neighbors for entity\n"
    "- llm_analyze_conflict: Analyze inter-agent proposal conflicts\n"
    "- llm_generate_reasoning_chain: Generate reasoning chain for decision\n"
    "- twin_monte_carlo: Run Monte Carlo simulation in Digital Twin\n"
    "- twin_what_if: Run what-if scenario in Digital Twin\n"
    "- twin_scenario_compare: Compare scenarios in Digital Twin\n"
    "- playbook_search: Search disruption playbooks in Pinecone\n"
    "- playbook_retrieve: Retrieve specific playbook\n"
    "\n"
    "Hard constraints (non-negotiable):\n"
    "- Essential item price multiplier MUST NOT exceed 1.3x\n"
    "- Rider shift duration MUST NOT exceed 10 hours\n"
    "- Fill rate prediction MUST meet 85% minimum\n"
    "- Every decision MUST be logged with full provenance\n"
    "- Low-confidence decisions MUST escalate to human review\n"
    "\n"
    "Protocol: Collect proposals -> Debate conflicts -> Pareto arbitrate "
    "-> Execute -> Learn"
)

_FROZEN_HASH: str = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


class ContextBuilder:
    """Build Ollama-compatible message lists that maximise KV-cache reuse."""

    def __init__(self) -> None:
        self._system_prompt_hash = _FROZEN_HASH

    def build_ollama_messages(
        self,
        context_messages: list[ContextMessage],
    ) -> list[dict[str, str]]:
        """Return message list with a frozen system prompt prefix (I-13, ADR-021).

        KV-cache invariant: the byte stream emitted for a given
        ``ContextMessage`` MUST NOT change when its ``status`` flips
        between ``ACTIVE``/``SUPERSEDED``/``REJECTED``. Embedding the
        status into the content (Sprint 5 mistake) caused KV-cache
        invalidation on replay. Status now lives in
        ``build_metadata_channel`` only — never in the LLM prompt body.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        for msg in context_messages:
            serialised = json.dumps(msg.content, **_JSON_KWARGS)
            role = "assistant" if msg.source == "orchestrator" else "user"
            messages.append(
                {"role": role, "content": f"[{msg.source}] {serialised}"},
            )
        return messages

    def build_metadata_channel(
        self,
        context_messages: list[ContextMessage],
    ) -> list[dict[str, str]]:
        """Return a parallel metadata channel keyed by message_id.

        Status, rejection_reason, and supersession edges live here so
        the orchestrator (and audit replay) can reason about message
        lifecycle without polluting the KV-cached prompt body.
        """
        return [
            {
                "message_id": str(msg.message_id),
                "source": msg.source,
                "status": msg.status.value,
                "rejection_reason": msg.rejection_reason or "",
                "superseded_by": str(msg.superseded_by) if msg.superseded_by else "",
            }
            for msg in context_messages
        ]

    def verify_prefix_stability(self) -> bool:
        """Return ``True`` when the system prompt is byte-identical to startup."""
        return hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest() == self._system_prompt_hash
