"""
SYNAPSE Orchestrator — Pinecone semantic decision cache (ADR-018).

Caches Tier 3-4 decisions so repeated scenarios can be resolved at Tier 1 speed.
Uses cosine similarity >= 0.92 and a 24-hour TTL.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


class SemanticDecisionCache:
    """Pinecone-backed semantic cache for consensus decisions."""

    SIMILARITY_THRESHOLD: float = 0.92
    TTL_HOURS: int = 24

    def __init__(
        self,
        api_key: str | None,
        index_name: str = "synapse-decision-cache",
    ) -> None:
        self._index: Any = None
        if api_key:
            try:
                from pinecone import Pinecone

                pc = Pinecone(api_key=api_key)
                self._index = pc.Index(index_name)
                logger.info("semantic_cache_connected", index=index_name)
            except Exception as exc:
                logger.warning("semantic_cache_init_failed", error=str(exc))

    @property
    def available(self) -> bool:
        return self._index is not None

    async def check_cache(
        self,
        query_embedding: list[float],
        context_hash: str,
    ) -> dict[str, Any] | None:
        """Return cached decision if a close match exists, else ``None``."""
        if not self.available:
            return None
        try:
            results = await asyncio.to_thread(
                self._index.query,
                vector=query_embedding,
                top_k=1,
                include_metadata=True,
                filter={"context_hash": context_hash},
            )
            if results.matches:
                match = results.matches[0]
                if match.score >= self.SIMILARITY_THRESHOLD:
                    cached_time = datetime.fromisoformat(match.metadata["timestamp"])
                    if datetime.now(UTC) - cached_time < timedelta(hours=self.TTL_HOURS):
                        loaded: dict[str, Any] = json.loads(match.metadata["decision_json"])
                        return loaded
        except Exception as exc:
            logger.warning("semantic_cache_check_failed", error=str(exc))
        return None

    async def retrieve_batch(
        self,
        queries: list[tuple[list[float], str]],
    ) -> dict[str, dict[str, Any] | None]:
        """Batched cache lookup (Sprint 8 WS-8 §M14).

        ``queries`` is a list of ``(embedding, context_hash)`` tuples. Returns
        a dict keyed by ``context_hash`` mapping to the cached decision (or
        ``None`` on miss). One Pinecone call per query — but issued in
        parallel via ``asyncio.gather`` so total wall-clock is bounded by the
        slowest single query rather than the sum.

        Sprint 9 cuts over call sites to use this method; Sprint 8 ships the
        API + a unit test only.
        """
        if not self.available:
            return {context_hash: None for _, context_hash in queries}
        if not queries:
            return {}

        async def _one(
            embedding: list[float], context_hash: str
        ) -> tuple[str, dict[str, Any] | None]:
            cached = await self.check_cache(embedding, context_hash)
            return context_hash, cached

        results = await asyncio.gather(
            *(_one(embedding, context_hash) for embedding, context_hash in queries)
        )
        return dict(results)

    async def store_decision(
        self,
        query_embedding: list[float],
        decision: dict[str, Any],
        context_hash: str,
    ) -> None:
        """Store a decision in the semantic cache."""
        if not self.available:
            return
        try:
            decision_json = json.dumps(decision, **_JSON_KWARGS)
            decision_id = hashlib.sha256(decision_json.encode()).hexdigest()[:16]
            await asyncio.to_thread(
                self._index.upsert,
                vectors=[
                    {
                        "id": f"cache_{decision_id}",
                        "values": query_embedding,
                        "metadata": {
                            "decision_json": decision_json,
                            "context_hash": context_hash,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                ],
            )
        except Exception as exc:
            logger.warning("semantic_cache_store_failed", error=str(exc))
