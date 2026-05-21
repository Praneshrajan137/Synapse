"""Supply network topology endpoint (P3.B20).

Surfaces the Neo4j-backed supply graph at HTTP so the FE Twin Lab can
render it. City-scoped via the `city` node property (E-S6-05). If Neo4j
is unreachable, returns a deterministic synthesized topology so the FE
shows *something* in dev/smoke environments.

Read-only by design — Twin Lab cannot mutate the graph; that's an
agent-only operation behind A2A.
"""

from __future__ import annotations

import os
import random
from typing import Any

import structlog
from fastapi import APIRouter, Query

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/topology")
async def topology(city: str = Query(default="bengaluru")) -> dict[str, Any]:
    if city not in {"bengaluru", "mumbai"}:
        return {"city": city, "nodes": [], "edges": [], "generated_at": _now()}
    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]

        uri = os.environ.get("SYNAPSE_NEO4J_URI", "bolt://neo4j:7687")
        user = os.environ.get("SYNAPSE_NEO4J_USER", "neo4j")
        pwd = os.environ.get("SYNAPSE_NEO4J_PASSWORD", "synapse_graph_2026")
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        with driver.session() as session:
            nodes = session.run(
                "MATCH (n) WHERE n.city = $city OR NOT EXISTS(n.city) "
                "RETURN coalesce(n.id, toString(id(n))) AS id, "
                "       labels(n)[0] AS type, "
                "       n.lat AS lat, n.lon AS lon",
                city=city,
            ).data()
            edges = session.run(
                "MATCH (a)-[r]->(b) "
                "WHERE (a.city = $city OR NOT EXISTS(a.city)) "
                "  AND (b.city = $city OR NOT EXISTS(b.city)) "
                "RETURN coalesce(a.id, toString(id(a))) AS src, "
                "       coalesce(b.id, toString(id(b))) AS dst, "
                "       type(r) AS type, "
                "       coalesce(r.weight, 1.0) AS weight",
                city=city,
            ).data()
        driver.close()
        return {"city": city, "nodes": nodes, "edges": edges, "generated_at": _now()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("topology_fallback_synthesized", city=city, error=str(exc))
        return _synthesize(city)


def _synthesize(city: str) -> dict[str, Any]:
    """Deterministic fallback (seed=city) so the FE renders even without Neo4j."""
    rng = random.Random(hash(city))
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for i in range(3):
        nodes.append({"id": f"warehouse-{city}-{i}", "type": "Warehouse", "lat": None, "lon": None})
    for i in range(25):
        nodes.append({"id": f"store-{city}-{i:03d}", "type": "DarkStore", "lat": None, "lon": None})
    for i in range(8):
        nodes.append({"id": f"supplier-{city}-{i}", "type": "Supplier", "lat": None, "lon": None})
    for w in range(3):
        for s in range(25):
            if rng.random() < 0.4:
                edges.append(
                    {
                        "src": f"warehouse-{city}-{w}",
                        "dst": f"store-{city}-{s:03d}",
                        "type": "SERVES",
                        "weight": round(rng.uniform(0.1, 1.0), 2),
                    }
                )
    for sp in range(8):
        for w in range(3):
            if rng.random() < 0.5:
                edges.append(
                    {
                        "src": f"supplier-{city}-{sp}",
                        "dst": f"warehouse-{city}-{w}",
                        "type": "SUPPLIES",
                        "weight": round(rng.uniform(0.1, 1.0), 2),
                    }
                )
    return {"city": city, "nodes": nodes, "edges": edges, "generated_at": _now()}


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
