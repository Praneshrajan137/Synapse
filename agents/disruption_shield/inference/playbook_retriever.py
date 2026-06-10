"""
SYNAPSE Disruption Shield — Playbook Retriever via Pinecone (I-1: zero cost).

Embeds disruption context using sentence-transformers all-mpnet-base-v2,
queries Pinecone for top-k historical playbooks, enforces 200ms SLA (INV-DS-002).
Falls back to cached playbooks if Pinecone is unavailable (I-7).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

try:
    from pinecone import Pinecone

    _HAS_PINECONE = True
except ImportError:
    _HAS_PINECONE = False
    logger.warning("pinecone_unavailable", fallback="cached_playbooks_only")

try:
    from sentence_transformers import SentenceTransformer

    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False
    logger.warning("sentence_transformers_unavailable", fallback="zero_vector_embedding")


@dataclass(frozen=True)
class PlaybookMatch:
    """Single matched playbook from vector store."""

    id: str
    title: str
    relevance_score: float
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


_FALLBACK_PLAYBOOKS: list[PlaybookMatch] = [
    PlaybookMatch(
        id="PB-FALLBACK-001",
        title="Generic Supplier Disruption Recovery",
        relevance_score=0.5,
        content="Activate backup suppliers. Review safety stock. Notify downstream agents.",
        metadata={"type": "supplier_disruption", "cached": True},
    ),
    PlaybookMatch(
        id="PB-FALLBACK-002",
        title="Logistics Network Rerouting",
        relevance_score=0.4,
        content="Identify alternative routes. Redistribute load across hubs. Monitor SLAs.",
        metadata={"type": "logistics_disruption", "cached": True},
    ),
    PlaybookMatch(
        id="PB-FALLBACK-003",
        title="Demand Surge Mitigation",
        relevance_score=0.3,
        content="Cap order quantities. Activate regional inventory buffers. Alert pricing agent.",
        metadata={"type": "demand_surge", "cached": True},
    ),
]


class PlaybookRetriever:
    """Retrieves historical playbooks from Pinecone with 200ms SLA (INV-DS-002)."""

    def __init__(
        self,
        index_name: str = "synapse-playbooks",
        embedding_model: str = "all-mpnet-base-v2",
        top_k: int = 3,
        sla_ms: float = 200.0,
    ) -> None:
        self._index_name = index_name
        self._top_k = top_k
        self._sla_ms = sla_ms
        self._index: Any | None = None
        self._embedder: Any | None = None

        # Pinecone FIRST: retrieve() needs BOTH the index and the embedder
        # (it falls back to cached playbooks if either is missing), so when
        # Pinecone is unconfigured the embedder would never be used — yet
        # SentenceTransformer(all-mpnet-base-v2) downloads ~420MB from HF
        # Hub on every force-recreated boot, blocking the server lifespan
        # (and /health) for ~11 minutes. That blackout failed the C47
        # deploy gate twice. Load the embedder only when an index exists.
        if _HAS_PINECONE:
            try:
                pc = Pinecone()
                self._index = pc.Index(index_name)
                logger.info("pinecone_connected", index=index_name)
            except Exception as exc:
                logger.warning("pinecone_init_failed", error=str(exc))
                self._index = None

        if self._index is not None and _HAS_SENTENCE_TRANSFORMERS:
            self._embedder = SentenceTransformer(embedding_model)
        elif self._index is None:
            logger.info(
                "playbook_embedder_skipped",
                reason="pinecone_unconfigured_fallback_playbooks_active",
            )

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[PlaybookMatch]:
        """Retrieve top-k playbooks matching the disruption query.

        Enforces INV-DS-002: total retrieval latency < 200ms.
        Falls back to cached playbooks if Pinecone or embedder unavailable (I-7).
        """
        k = top_k or self._top_k
        start = time.monotonic()

        if self._index is None or self._embedder is None:
            logger.info("playbook_retriever_fallback", reason="pinecone_or_embedder_unavailable")
            return _FALLBACK_PLAYBOOKS[:k]

        try:
            embedding = self._embedder.encode(query).tolist()
            results = self._index.query(vector=embedding, top_k=k, include_metadata=True)
            elapsed_ms = (time.monotonic() - start) * 1000

            if elapsed_ms > self._sla_ms:
                logger.warning(
                    "pinecone_sla_breach",
                    elapsed_ms=round(elapsed_ms, 1),
                    sla_ms=self._sla_ms,
                )

            matches: list[PlaybookMatch] = []
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})
                matches.append(
                    PlaybookMatch(
                        id=match["id"],
                        title=metadata.get("title", "Untitled Playbook"),
                        relevance_score=float(match.get("score", 0.0)),
                        content=metadata.get("content", ""),
                        metadata=metadata,
                    )
                )

            logger.info(
                "playbooks_retrieved",
                count=len(matches),
                elapsed_ms=round(elapsed_ms, 1),
            )
            return matches

        except Exception as exc:
            logger.warning(
                "playbook_retrieval_failed",
                error=str(exc),
                fallback="cached_playbooks",
            )
            return _FALLBACK_PLAYBOOKS[:k]
