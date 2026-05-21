"""Neo4j graph client — read-mostly facade with templated cyphers (WS-8.4).

Activates ADR-005 (knowledge graph) in agent decision paths. Read-only by
default; writes require an explicit `write=True` so a stray cypher in an
inference path can never mutate the supply graph.

Hot-query results are cached in Redis with a 30 s TTL — Neo4j stays out of
the Tier-1 latency budget. Cache failures degrade open (I-7).

Predefined cyphers live in `_CYPHERS` so both call sites and audit can grep
for the exact query string. New cyphers MUST be added there, never inline,
to keep the surface auditable.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


_CYPHERS: dict[str, str] = {
    # Supplier trust: PageRank over failure edges. Higher score = more trusted.
    "supplier_trust_score": (
        "MATCH (s:Supplier {supplier_id: $supplier_id, city: $city}) "
        "OPTIONAL MATCH (s)-[r:FAILED_ON]->(:Order) "
        "WITH s, count(r) AS failures "
        "RETURN s.supplier_id AS supplier_id, "
        "       1.0 / (1.0 + failures) AS trust_score, "
        "       failures"
    ),
    # Disruption shield: blast-radius given a node and hop count.
    "disruption_blast_radius": (
        "MATCH (n {id: $node_id, city: $city}) "
        "OPTIONAL MATCH path = (n)-[*1..$hops]-(impacted) "
        "WITH DISTINCT impacted "
        "RETURN labels(impacted) AS kind, "
        "       coalesce(impacted.id, impacted.store_id, impacted.sku_id) AS id"
    ),
    # Sustainability: per-SKU lifecycle CO2 lookup.
    "sku_lifecycle_co2": (
        "MATCH (sku:SKU {sku_id: $sku_id})-[:SOURCED_FROM]->(supplier:Supplier {city: $city}) "
        "RETURN sku.sku_id AS sku_id, "
        "       coalesce(sku.lifecycle_co2_kg, 1.0) AS co2_per_unit, "
        "       coalesce(supplier.transport_multiplier, 1.0) AS transport_multiplier"
    ),
}


class GraphClient:
    """Read-mostly Neo4j wrapper. Lazy connection; degrades open on failure."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        redis_url: str | None = None,
        cache_ttl: int = 30,
    ) -> None:
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get(
            "NEO4J_PASSWORD", "synapse_graph_2026"
        )
        self._redis_url = redis_url or os.environ.get(
            "SYNAPSE_REDIS_URL", "redis://redis:6379/2"
        )
        self._cache_ttl = cache_ttl
        self._driver: Any = None
        self._redis: Any = None

    # -- Connections --------------------------------------------------------

    def _get_driver(self) -> Any:
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
            return self._driver
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_driver_unavailable", error=str(exc))
            return None

    def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis  # type: ignore[import-untyped]

            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            return self._redis
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_cache_unavailable", error=str(exc))
            return None

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                pass

    # -- Public surface -----------------------------------------------------

    def query(
        self,
        cypher_name: str,
        params: dict[str, Any] | None = None,
        *,
        write: bool = False,
        cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Run a templated cypher. Write=True allows mutation; default is read-only."""
        if cypher_name not in _CYPHERS:
            raise KeyError(f"unknown cypher: {cypher_name!r}")
        cypher = _CYPHERS[cypher_name]
        params = params or {}
        cache_key = self._cache_key(cypher_name, params) if cache and not write else None

        if cache_key is not None:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        rows = self._execute(cypher, params, write=write)
        if cache_key is not None:
            self._cache_put(cache_key, rows)
        return rows

    # -- Internal helpers ---------------------------------------------------

    def _execute(
        self, cypher: str, params: dict[str, Any], *, write: bool
    ) -> list[dict[str, Any]]:
        driver = self._get_driver()
        if driver is None:
            return []
        try:
            with driver.session() as session:
                method = session.execute_write if write else session.execute_read
                rows: Iterable[dict[str, Any]] = method(
                    lambda tx: [r.data() for r in tx.run(cypher, **params)]
                )
                return list(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_query_failed", error=str(exc))
            return []

    def _cache_key(self, name: str, params: dict[str, Any]) -> str:
        blob = json.dumps({"n": name, "p": params}, sort_keys=True, separators=(",", ":"))
        return f"graph:{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:24]}"

    def _cache_get(self, key: str) -> list[dict[str, Any]] | None:
        client = self._get_redis()
        if client is None:
            return None
        try:
            raw = client.get(key)
            if raw is None:
                return None
            return list(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            logger.debug("graph_cache_get_skip", error=str(exc))
            return None

    def _cache_put(self, key: str, rows: list[dict[str, Any]]) -> None:
        client = self._get_redis()
        if client is None:
            return
        try:
            client.setex(key, self._cache_ttl, json.dumps(rows, default=str))
        except Exception as exc:  # noqa: BLE001
            logger.debug("graph_cache_put_skip", error=str(exc))


__all__ = ["GraphClient"]
