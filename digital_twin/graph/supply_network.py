"""
SYNAPSE Digital Twin — Neo4j supply-network graph (Aura Free tier).

Provides topology queries, node updates, and neighbor lookups for the
digital twin's graph representation of the supply chain.
"""

from __future__ import annotations

from typing import Any

import structlog
from neo4j import Driver, GraphDatabase, Session

from digital_twin.config import TwinConfig

logger = structlog.get_logger(__name__)


class SupplyNetworkGraph:
    """Manages the Neo4j graph backing the digital twin."""

    def __init__(self, config: TwinConfig | None = None) -> None:
        self._config = config or TwinConfig()
        self._driver: Driver = GraphDatabase.driver(
            self._config.neo4j_uri,
            auth=(self._config.neo4j_user, self._config.neo4j_password),
        )
        logger.info(
            "neo4j_connected",
            uri=self._config.neo4j_uri,
            user=self._config.neo4j_user,
        )

    def _session(self) -> Session:
        return self._driver.session()

    def get_topology(self) -> list[dict[str, Any]]:
        """Return the full supply-network topology as a list of node/edge dicts."""
        query = (
            "MATCH (n)-[r]->(m) "
            "RETURN n.id AS source, type(r) AS rel, m.id AS target, "
            "properties(n) AS source_props, properties(m) AS target_props"
        )
        with self._session() as session:
            result = session.run(query)
            topology: list[dict[str, Any]] = [dict(record) for record in result]
        logger.info("get_topology", edge_count=len(topology))
        return topology

    def update_node(self, node_id: str, properties: dict[str, Any]) -> None:
        """Upsert a node's properties in the supply network."""
        query = "MERGE (n:SupplyNode {id: $node_id}) SET n += $properties"
        with self._session() as session:
            session.run(query, node_id=node_id, properties=properties)
        logger.info("update_node", node_id=node_id, props_count=len(properties))

    def get_neighbors(self, node_id: str, direction: str = "both") -> list[dict[str, Any]]:
        """Return neighbors of a node, optionally filtering by direction."""
        if direction == "outgoing":
            query = (
                "MATCH (n:SupplyNode {id: $node_id})-[r]->(m) "
                "RETURN m.id AS neighbor_id, type(r) AS rel, properties(m) AS props"
            )
        elif direction == "incoming":
            query = (
                "MATCH (n:SupplyNode {id: $node_id})<-[r]-(m) "
                "RETURN m.id AS neighbor_id, type(r) AS rel, properties(m) AS props"
            )
        else:
            query = (
                "MATCH (n:SupplyNode {id: $node_id})-[r]-(m) "
                "RETURN m.id AS neighbor_id, type(r) AS rel, properties(m) AS props"
            )
        with self._session() as session:
            result = session.run(query, node_id=node_id)
            neighbors: list[dict[str, Any]] = [dict(record) for record in result]
        logger.info(
            "get_neighbors",
            node_id=node_id,
            direction=direction,
            count=len(neighbors),
        )
        return neighbors

    def close(self) -> None:
        self._driver.close()
        logger.info("neo4j_closed")
