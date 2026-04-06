"""
SYNAPSE — Neo4j Aura Free Migration.
Migrates schema from local Neo4j Community to Neo4j Aura Free.
Aura Free limits: 50,000 nodes, 175,000 relationships.
SYNAPSE at 25 dark stores: ~2,000 nodes, ~15,000 relationships — well within limits.

Run: python infrastructure/neo4j/migrate_to_aura.py
Requires: NEO4J_AURA_URI, NEO4J_AURA_USER, NEO4J_AURA_PASSWORD env vars
"""
from __future__ import annotations

import os
from typing import Any

import structlog
from neo4j import GraphDatabase, Session

logger = structlog.get_logger(__name__)


def get_aura_driver() -> Any:
    """Create Neo4j driver for Aura Free instance."""
    uri = os.environ["NEO4J_AURA_URI"]
    user = os.environ["NEO4J_AURA_USER"]
    password = os.environ["NEO4J_AURA_PASSWORD"]

    if not uri.startswith("neo4j+s://"):
        raise ValueError(f"Aura URI must use neo4j+s:// scheme, got: {uri}")

    return GraphDatabase.driver(uri, auth=(user, password))


def create_constraints(session: Session) -> None:
    """Create uniqueness constraints (Aura Free supports constraints)."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (ds:DarkStore) REQUIRE ds.store_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (w:Warehouse) REQUIRE w.warehouse_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplier) REQUIRE s.supplier_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (sk:SKU) REQUIRE sk.sku_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Rider) REQUIRE r.rider_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (z:Zone) REQUIRE z.zone_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Order) REQUIRE o.order_id IS UNIQUE",
    ]
    for cypher in constraints:
        session.run(cypher)
        logger.info("constraint_created", cypher=cypher[:60])


def create_indexes(session: Session) -> None:
    """Create indexes for common query patterns."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (sk:SKU) ON (sk.category, sk.subcategory)",
        "CREATE POINT INDEX IF NOT EXISTS FOR (ds:DarkStore) ON (ds.location)",
        "CREATE POINT INDEX IF NOT EXISTS FOR (w:Warehouse) ON (w.location)",
        "CREATE FULLTEXT INDEX sku_search IF NOT EXISTS FOR (sk:SKU) ON EACH [sk.name, sk.category]",
        "CREATE INDEX IF NOT EXISTS FOR (s:Supplier) ON (s.last_delivery_ts)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.event_date)",
    ]
    for cypher in indexes:
        try:
            session.run(cypher)
            logger.info("index_created", cypher=cypher[:60])
        except Exception as exc:
            logger.warning("index_skipped", cypher=cypher[:60], reason=str(exc))


def seed_bengaluru_topology(session: Session) -> None:
    """Seed the 25 dark store Bengaluru topology."""
    zones = [
        {"zone_id": f"BLR-Z{i:02d}", "name": f"Bengaluru Zone {i}",
         "lat": 12.9 + (i * 0.02), "lon": 77.5 + (i * 0.03)}
        for i in range(1, 6)
    ]
    for z in zones:
        session.run(
            "MERGE (z:Zone {zone_id: $zone_id}) "
            "SET z.name = $name, z.location = point({latitude: $lat, longitude: $lon})",
            z,
        )

    for i in range(1, 26):
        zone_idx = ((i - 1) % 5) + 1
        session.run(
            "MERGE (ds:DarkStore {store_id: $sid}) "
            "SET ds.name = $name, ds.zone_id = $zid, "
            "    ds.location = point({latitude: $lat, longitude: $lon}), "
            "    ds.capacity_sqft = $cap "
            "WITH ds "
            "MATCH (z:Zone {zone_id: $zid}) "
            "MERGE (ds)-[:IN_ZONE]->(z)",
            {
                "sid": f"BLR-DS-{i:03d}",
                "name": f"Bengaluru Dark Store {i}",
                "zid": f"BLR-Z{zone_idx:02d}",
                "lat": 12.9 + (i * 0.008),
                "lon": 77.5 + (i * 0.012),
                "cap": 1500 + (i * 100),
            },
        )

    for i in range(1, 3):
        session.run(
            "MERGE (w:Warehouse {warehouse_id: $wid}) "
            "SET w.name = $name, w.location = point({latitude: $lat, longitude: $lon})",
            {
                "wid": f"BLR-WH-{i:03d}",
                "name": f"Bengaluru Warehouse {i}",
                "lat": 12.95 + (i * 0.05),
                "lon": 77.55 + (i * 0.05),
            },
        )

    for i in range(1, 11):
        session.run(
            "MERGE (s:Supplier {supplier_id: $sid}) "
            "SET s.name = $name, s.trust_score = $trust, "
            "    s.avg_lead_time_days = $lead",
            {
                "sid": f"SUP-{i:03d}",
                "name": f"Supplier {i}",
                "trust": 0.5 + (i * 0.04),
                "lead": 1.0 + (i * 0.3),
            },
        )

    categories = ["essentials", "snacks", "beverages", "dairy", "produce"]
    for i in range(1, 101):
        cat = categories[(i - 1) % 5]
        session.run(
            "MERGE (sk:SKU {sku_id: $skid}) "
            "SET sk.name = $name, sk.category = $cat, "
            "    sk.base_price = $price, sk.shelf_life_days = $shelf, "
            "    sk.is_essential = $essential",
            {
                "skid": f"SKU-{i:04d}",
                "name": f"Product {i} ({cat})",
                "cat": cat,
                "price": 20.0 + (i * 2.5),
                "shelf": 3 if cat in ("dairy", "produce") else 30,
                "essential": cat == "essentials",
            },
        )

    session.run(
        "MATCH (ds:DarkStore), (sk:SKU) "
        "WHERE toInteger(right(ds.store_id, 3)) % 5 = toInteger(right(sk.sku_id, 4)) % 5 "
        "   OR rand() < 0.3 "
        "MERGE (ds)-[:STORES {current_stock: toInteger(rand() * 100), "
        "  max_capacity: 150, days_to_expiry: toInteger(rand() * sk.shelf_life_days)}]->(sk)"
    )

    session.run(
        "MATCH (sk:SKU), (s:Supplier) "
        "WHERE toInteger(right(sk.sku_id, 4)) % 10 = toInteger(right(s.supplier_id, 3)) - 1 "
        "   OR rand() < 0.15 "
        "MERGE (sk)-[:SUPPLIED_BY {unit_cost: sk.base_price * 0.6, "
        "  moq: toInteger(rand() * 50 + 10)}]->(s)"
    )

    logger.info("topology_seeded", stores=25, warehouses=2, suppliers=10, skus=100)


def verify_counts(session: Session) -> dict[str, int]:
    """Verify node and relationship counts against Aura Free limits."""
    node_result = session.run("MATCH (n) RETURN count(n) AS cnt").single()
    rel_result = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()

    nodes = node_result["cnt"] if node_result else 0
    rels = rel_result["cnt"] if rel_result else 0

    logger.info(
        "aura_usage",
        nodes=nodes,
        relationships=rels,
        node_limit=50000,
        rel_limit=175000,
        node_pct=f"{nodes / 500:.1f}%",
        rel_pct=f"{rels / 1750:.1f}%",
    )

    if nodes >= 50000:
        raise RuntimeError(f"Node count {nodes} exceeds Aura Free limit of 50,000")
    if rels >= 175000:
        raise RuntimeError(f"Relationship count {rels} exceeds Aura Free limit of 175,000")

    return {"nodes": nodes, "relationships": rels}


def main() -> None:
    """Run full Aura migration."""
    driver = get_aura_driver()

    try:
        with driver.session() as session:
            logger.info("connected_to_aura")
            create_constraints(session)
            create_indexes(session)
            seed_bengaluru_topology(session)
            counts = verify_counts(session)
            logger.info("migration_complete", **counts)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
