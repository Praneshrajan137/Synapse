"""
scripts/seed_mumbai_graph.py

Seeds Neo4j with Mumbai-specific nodes and relationships.
MUST maintain IDENTICAL schema to Bengaluru — same node labels, relationship types, property keys.
The ONLY differences are:
  - city property = 'mumbai' on all nodes
  - store_ids use MUM-xxx prefix
  - Mumbai-specific relationships: FLOOD_RISK, BRIDGE_DEPENDENCY
  - Mumbai-specific zone properties: monsoon_vulnerability, coastal_proximity

INVARIANT I-3: All node/relationship types validate against proto/domain/graph.schema.json
INVARIANT I-12: Divergence monitor will track these nodes immediately upon seeding.

Property key mapping (MUST match init.cypher uniqueness constraints):
  DarkStore  -> store_id      (NOT 'id')
  Warehouse  -> warehouse_id  (NOT 'id')
  Supplier   -> supplier_id   (NOT 'id')
  Zone       -> zone_id       (NOT 'id')
  Rider      -> rider_id      (NOT 'id')
  SKU        -> sku_id        (NOT 'id')
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import structlog
from neo4j import GraphDatabase

log = structlog.get_logger()

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "synapse_graph_2026")


def seed_mumbai(driver) -> None:  # noqa: C901 — seeding is inherently sequential
    """
    Creates:
    - 25 DarkStore nodes with Mumbai coordinates and city='mumbai'
    - 3 Warehouse nodes (Bhiwandi, Navi Mumbai, Thane) with city='mumbai'
    - 40 Supplier nodes with Mumbai lead-time distributions and city='mumbai'
    - 500 SKU nodes (SHARED with Bengaluru — same sku_ids, NO city property on SKUs)
    - 8 Zone nodes matching Mumbai ward boundaries with city='mumbai'
    - 200 Rider nodes with zone assignments and city='mumbai'
    - All relationships: STORES, IN_ZONE, SUPPLIED_BY, SUPPLIES, CONNECTED_TO
    - Mumbai-specific: FLOOD_RISK relationship on affected zones (5 zones)
    - Mumbai-specific: BRIDGE_DEPENDENCY relationship on cross-water routes
    """

    stores = json.loads(Path("data/mumbai/stores.json").read_text())
    warehouses = json.loads(Path("data/mumbai/warehouses.json").read_text())
    suppliers = json.loads(Path("data/mumbai/suppliers.json").read_text())
    zones = json.loads(Path("data/mumbai/zones.json").read_text())
    riders = json.loads(Path("data/mumbai/riders.json").read_text())

    with driver.session() as session:
        # ── DarkStore Nodes (key: store_id per init.cypher constraint) ────
        for store in stores:
            session.run(
                """
                MERGE (s:DarkStore {store_id: $store_id})
                SET s.name = $name, s.location = point({latitude: $lat, longitude: $lon}),
                    s.zone = $zone, s.city = 'mumbai',
                    s.capacity_sqft = $capacity, s.cold_chain = $cold_chain,
                    s.active = true
                """,
                store_id=store["id"],
                name=store["name"],
                lat=store["lat"],
                lon=store["lon"],
                zone=store["zone"],
                capacity=store.get("capacity_sqft", 1500),
                cold_chain=store.get("cold_chain", True),
            )
        log.info("seeded_darkstores", city="mumbai", count=len(stores))

        # ── Warehouse Nodes (key: warehouse_id per init.cypher constraint) ─
        for wh in warehouses:
            session.run(
                """
                MERGE (w:Warehouse {warehouse_id: $warehouse_id})
                SET w.name = $name,
                    w.location = point({latitude: $lat, longitude: $lon}),
                    w.type = $type, w.capacity_pallets = $capacity,
                    w.city = 'mumbai'
                """,
                warehouse_id=wh["id"],
                name=wh["name"],
                lat=wh["lat"],
                lon=wh["lon"],
                type=wh["type"],
                capacity=wh["capacity_pallets"],
            )
        log.info("seeded_warehouses", city="mumbai", count=len(warehouses))

        # ── Zone Nodes (key: zone_id per init.cypher constraint) ──────────
        for zone in zones:
            session.run(
                """
                MERGE (z:Zone {zone_id: $zone_id})
                SET z.name = $name, z.city = 'mumbai',
                    z.population_density = $density,
                    z.avg_income = $income,
                    z.flood_risk = $flood_risk
                """,
                zone_id=zone["id"],
                name=zone["name"],
                density=zone["population_density"],
                income=zone["avg_income"],
                flood_risk=zone["flood_risk"],
            )
        log.info("seeded_zones", city="mumbai", count=len(zones))

        # ── Supplier Nodes (key: supplier_id per init.cypher constraint) ──
        for supplier in suppliers:
            session.run(
                """
                MERGE (sup:Supplier {supplier_id: $supplier_id})
                SET sup.name = $name, sup.city = 'mumbai',
                    sup.lead_time_mean = $lt_mean, sup.lead_time_std = $lt_std,
                    sup.reliability_score = $reliability,
                    sup.monsoon_lead_time_multiplier = $monsoon_mult
                """,
                supplier_id=supplier["id"],
                name=supplier["name"],
                lt_mean=supplier["lead_time_mean"],
                lt_std=supplier["lead_time_std"],
                reliability=supplier.get("reliability_score", 0.85),
                monsoon_mult=supplier.get("monsoon_lead_time_multiplier", 1.5),
            )
        log.info("seeded_suppliers", city="mumbai", count=len(suppliers))

        # ── SKU Nodes (SHARED — key: sku_id, NO city property) ───────────
        skus = json.loads(Path("data/mumbai/skus.json").read_text())
        for sku in skus:
            session.run(
                """
                MERGE (k:SKU {sku_id: $sku_id})
                SET k.name = $name, k.category = $category,
                    k.subcategory = $subcategory,
                    k.is_essential = $essential, k.is_perishable = $perishable,
                    k.shelf_life_days = $shelf_life
                """,
                sku_id=sku["sku_id"],
                name=sku["name"],
                category=sku["category"],
                subcategory=sku["subcategory"],
                essential=sku.get("is_essential", False),
                perishable=sku.get("is_perishable", False),
                shelf_life=sku.get("shelf_life_days", 365),
            )
        log.info("merged_skus", count=len(skus))

        # ── Rider Nodes (key: rider_id per init.cypher constraint) ────────
        for rider in riders:
            session.run(
                """
                MERGE (r:Rider {rider_id: $rider_id})
                SET r.name = $name, r.city = 'mumbai',
                    r.zone = $zone, r.vehicle_type = $vehicle,
                    r.shift = $shift, r.rating = $rating
                """,
                rider_id=rider["id"],
                name=rider["name"],
                zone=rider["zone"],
                vehicle=rider.get("vehicle_type", "bike"),
                shift=rider.get("shift", "morning"),
                rating=rider.get("rating", 4.2),
            )
        log.info("seeded_riders", city="mumbai", count=len(riders))

        # ── Relationships ─────────────────────────────────────────────────

        # DarkStore -> IN_ZONE -> Zone (match on store_id and zone_id)
        for store in stores:
            session.run(
                """
                MATCH (s:DarkStore {store_id: $store_id})
                MATCH (z:Zone {city: 'mumbai', name: $zone})
                MERGE (s)-[:IN_ZONE {primary: true}]->(z)
                """,
                store_id=store["id"],
                zone=store["zone"],
            )

        # DarkStore -> STORES -> SKU (all stores carry all SKUs initially)
        session.run(
            """
            MATCH (s:DarkStore {city: 'mumbai'}), (k:SKU)
            MERGE (s)-[:STORES {current_stock: 50, reorder_point: 15, max_stock: 100}]->(k)
            """
        )

        # Warehouse -> SUPPLIES -> DarkStore (nearest warehouse per store)
        session.run(
            """
            MATCH (w:Warehouse {city: 'mumbai'}), (s:DarkStore {city: 'mumbai'})
            WITH w, s, point.distance(w.location, s.location) AS dist
            ORDER BY dist
            WITH s, collect(w)[0] AS nearest_wh, collect(dist)[0] AS min_dist
            MERGE (nearest_wh)-[:SUPPLIES {distance_km: min_dist / 1000.0}]->(s)
            """
        )

        # Supplier -> SUPPLIED_BY -> Warehouse
        session.run(
            """
            MATCH (sup:Supplier {city: 'mumbai'}), (w:Warehouse {city: 'mumbai'})
            WITH sup, w, rand() AS r
            WHERE r < 0.5
            MERGE (w)-[:SUPPLIED_BY]->(sup)
            """
        )

        # DarkStore -> CONNECTED_TO -> DarkStore (routing graph, <10km links)
        session.run(
            """
            MATCH (s1:DarkStore {city: 'mumbai'}), (s2:DarkStore {city: 'mumbai'})
            WHERE s1.store_id < s2.store_id
            WITH s1, s2, point.distance(s1.location, s2.location) AS dist
            WHERE dist < 10000
            MERGE (s1)-[:CONNECTED_TO {distance_m: dist}]->(s2)
            MERGE (s2)-[:CONNECTED_TO {distance_m: dist}]->(s1)
            """
        )

        # ── Mumbai-Specific Relationships ─────────────────────────────────

        flood_zones: dict[str, tuple[str, float]] = {
            "central": ("severe", 0.7),
            "harbour": ("severe", 0.8),
            "central_suburbs": ("moderate", 0.5),
            "western_suburbs": ("moderate", 0.4),
            "extended_western": ("moderate", 0.4),
        }
        for zone_name, (level, prob) in flood_zones.items():
            session.run(
                """
                MATCH (z:Zone {city: 'mumbai', name: $zone})
                SET z.flood_risk_level = $level
                WITH z
                MATCH (s:DarkStore {city: 'mumbai'})-[:IN_ZONE]->(z)
                MERGE (z)-[:FLOOD_RISK {probability: $prob}]->(s)
                """,
                zone=zone_name,
                level=level,
                prob=prob,
            )

        bridge_deps = [
            ("MUM-004", "MUM-003", "Bandra-Worli Sea Link"),
            ("MUM-020", "MUM-019", "Vashi Bridge"),
            ("MUM-018", "MUM-017", "Thane Creek Bridge"),
        ]
        for s1_id, s2_id, bridge_name in bridge_deps:
            session.run(
                """
                MATCH (s1:DarkStore {store_id: $s1}), (s2:DarkStore {store_id: $s2})
                MERGE (s1)-[:BRIDGE_DEPENDENCY {bridge: $bridge,
                    closure_risk: 0.3, monsoon_closure_risk: 0.6}]->(s2)
                """,
                s1=s1_id,
                s2=s2_id,
                bridge=bridge_name,
            )

        log.info("seeded_mumbai_relationships_complete")


def verify_seeding(driver) -> None:
    """Post-seeding verification — all assertions must pass."""
    with driver.session() as session:
        r = session.run(
            "MATCH (s:DarkStore {city:'mumbai'}) RETURN count(s) AS c"
        ).single()
        assert r["c"] == 25, f"Expected 25 DarkStores, got {r['c']}"

        r = session.run(
            "MATCH (w:Warehouse {city:'mumbai'}) RETURN count(w) AS c"
        ).single()
        assert r["c"] == 3, f"Expected 3 Warehouses, got {r['c']}"

        r = session.run(
            "MATCH (z:Zone {city:'mumbai'}) RETURN count(z) AS c"
        ).single()
        assert r["c"] == 8, f"Expected 8 Zones, got {r['c']}"

        r = session.run(
            "MATCH (:Zone {city:'mumbai'})-[r:FLOOD_RISK]->() RETURN count(r) AS c"
        ).single()
        assert r["c"] >= 5, f"Expected >=5 FLOOD_RISK relationships, got {r['c']}"

        r = session.run(
            "MATCH ()-[r:BRIDGE_DEPENDENCY]->() RETURN count(r) AS c"
        ).single()
        assert r["c"] >= 3, f"Expected >=3 BRIDGE_DEPENDENCY relationships, got {r['c']}"

        r = session.run(
            "MATCH (s:DarkStore {city:'bengaluru'}) RETURN count(s) AS c"
        ).single()
        assert r["c"] == 25, f"Bengaluru DarkStores corrupted: expected 25, got {r['c']}"

        r = session.run("MATCH (k:SKU) RETURN count(k) AS c").single()
        assert r["c"] == 500, f"Expected 500 shared SKUs, got {r['c']}"

        log.info("mumbai_seeding_verification_passed")


if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        seed_mumbai(driver)
        verify_seeding(driver)
    finally:
        driver.close()
