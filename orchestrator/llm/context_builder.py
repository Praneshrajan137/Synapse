"""
SYNAPSE Orchestrator — KV-cache-aware context construction (ADR-021, I-13).

Three-layer protocol:
  Layer 1: Stable system-prompt prefix (byte-identical every invocation).
  Layer 2: Append-only context messages (never reorder, never remove).
  Layer 3: Deterministic JSON serialization (sort_keys, compact separators).

WS-2 hardening (Sprint 7):
    Earlier versions embedded the dynamic ``msg.status`` (ACTIVE / SUPERSEDED /
    REJECTED / ERROR) into the LLM message body via the prefix
    ``f"[{msg.source}|{msg.status}] ..."``. This was a partial I-13 violation:
    the same logical context message produced *different* prompt bytes at
    different points in its lifecycle, which silently invalidates the
    Ollama KV-cache for that position and every subsequent position.

    Sprint 7 fix:
      * The LLM message body is now solely the deterministic JSON of
        ``msg.content``. Source attribution moves into the OpenAI-style
        ``role`` field (``user`` / ``assistant``).
      * Filtering by status is the consensus-protocol's responsibility —
        ``build_ollama_messages`` accepts an ``include_statuses`` set
        (default = ACTIVE only) and drops the rest *before* serialization.
        Once a status changes, the consensus layer simply re-builds the
        prompt with a different filter; the message bodies that *do* end
        up in the prompt are byte-identical to any other call with the
        same set of ACTIVE messages.

    Net effect: the KV-cache prefix length is now ``len(SYSTEM_PROMPT) +
    sum(len(canonical(msg.content)) for active msg)`` and is stable across
    status transitions, replays, and reruns.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from synapse_common.models import MessageStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

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

_DEFAULT_INCLUDE: frozenset[MessageStatus] = frozenset({MessageStatus.ACTIVE})


class ContextBuilder:
    """Build Ollama-compatible message lists that maximise KV-cache reuse."""

    def __init__(self) -> None:
        self._system_prompt_hash = _FROZEN_HASH

    def build_ollama_messages(
        self,
        context_messages: Iterable[ContextMessage],
        *,
        include_statuses: Iterable[MessageStatus] | None = None,
    ) -> list[dict[str, str]]:
        """Return a message list with a frozen system prompt prefix.

        Args:
            context_messages: Append-only context. ``msg.status`` does NOT
                appear in the LLM body; instead, messages whose status is
                NOT in ``include_statuses`` are dropped entirely.
            include_statuses: Status values to include. Default is just
                ``ACTIVE``. Pass an empty iterable to include every status
                (rare; mostly for full-trace debugging).
        """
        statuses = (
            _DEFAULT_INCLUDE if include_statuses is None else frozenset(include_statuses)
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        for msg in context_messages:
            if statuses and msg.status not in statuses:
                continue
            serialised = json.dumps(msg.content, **_JSON_KWARGS)
            role = "assistant" if msg.source == "orchestrator" else "user"
            messages.append({"role": role, "content": serialised})
        return messages

    def kv_cache_prefix_hash(
        self,
        context_messages: Iterable[ContextMessage],
        *,
        include_statuses: Iterable[MessageStatus] | None = None,
    ) -> str:
        """Return a SHA-256 over the full prompt bytes.

        Used by the eval harness (WS-5) to assert two prompt invocations
        produce identical bytes, i.e. would share the Ollama KV-cache.
        """
        h = hashlib.sha256()
        for msg in self.build_ollama_messages(
            context_messages, include_statuses=include_statuses
        ):
            h.update(msg["role"].encode("utf-8"))
            h.update(b"\x00")
            h.update(msg["content"].encode("utf-8"))
            h.update(b"\x01")
        return h.hexdigest()

    def verify_prefix_stability(self) -> bool:
        """Return ``True`` when the system prompt is byte-identical to startup."""
        return hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest() == self._system_prompt_hash
