// ============================================================================
// SYNAPSE Neo4j Schema — Structural Backbone
// Knowledge graph for Digital Twin + Agent reasoning
// Execute via: cat init.cypher | docker exec -i synapse-neo4j cypher-shell -u neo4j -p synapse_graph_2026
// ============================================================================

// ── Node Uniqueness Constraints (8 total) ──
CREATE CONSTRAINT dark_store_id IF NOT EXISTS
  FOR (ds:DarkStore) REQUIRE ds.store_id IS UNIQUE;

CREATE CONSTRAINT warehouse_id IF NOT EXISTS
  FOR (w:Warehouse) REQUIRE w.warehouse_id IS UNIQUE;

CREATE CONSTRAINT supplier_id IF NOT EXISTS
  FOR (s:Supplier) REQUIRE s.supplier_id IS UNIQUE;

CREATE CONSTRAINT sku_id IF NOT EXISTS
  FOR (sk:SKU) REQUIRE sk.sku_id IS UNIQUE;

CREATE CONSTRAINT rider_id IF NOT EXISTS
  FOR (r:Rider) REQUIRE r.rider_id IS UNIQUE;

CREATE CONSTRAINT zone_id IF NOT EXISTS
  FOR (z:Zone) REQUIRE z.zone_id IS UNIQUE;

CREATE CONSTRAINT event_id IF NOT EXISTS
  FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

CREATE CONSTRAINT category_id IF NOT EXISTS
  FOR (c:Category) REQUIRE c.category_id IS UNIQUE;

// ── Composite Indexes (2 total) ──
CREATE INDEX inventory_lookup IF NOT EXISTS
  FOR (inv:Inventory) ON (inv.store_id, inv.sku_id);

CREATE INDEX demand_lookup IF NOT EXISTS
  FOR (d:DemandSignal) ON (d.sku_id, d.store_id, d.timestamp);

// ── Geospatial Point Indexes (4 total) ──
CREATE POINT INDEX store_location IF NOT EXISTS
  FOR (ds:DarkStore) ON (ds.location);

CREATE POINT INDEX warehouse_location IF NOT EXISTS
  FOR (w:Warehouse) ON (w.location);

CREATE POINT INDEX rider_location IF NOT EXISTS
  FOR (r:Rider) ON (r.current_location);

CREATE POINT INDEX event_location IF NOT EXISTS
  FOR (e:Event) ON (e.location);

// ── Full-Text Index for SKU Search ──
CREATE FULLTEXT INDEX sku_search IF NOT EXISTS
  FOR (sk:SKU) ON EACH [sk.name, sk.brand, sk.description];
