// ============================================================================
// SYNAPSE Neo4j Seed Data — Bengaluru 25 Dark Stores
// Run after init.cypher to populate baseline graph.
// Uses MERGE for idempotency (safe to re-run).
// ============================================================================

// ── Categories (with price caps from I-6) ──
MERGE (c1:Category {category_id: 'cat_essentials'})
  SET c1.name = 'Essentials', c1.price_cap = 1.3, c1.is_essential = true
MERGE (c2:Category {category_id: 'cat_snacks'})
  SET c2.name = 'Snacks & Beverages', c2.price_cap = 2.0, c2.is_essential = false
MERGE (c3:Category {category_id: 'cat_fresh'})
  SET c3.name = 'Fresh Produce', c3.price_cap = 1.5, c3.is_essential = true
MERGE (c4:Category {category_id: 'cat_dairy'})
  SET c4.name = 'Dairy & Bakery', c4.price_cap = 1.5, c4.is_essential = true
MERGE (c5:Category {category_id: 'cat_household'})
  SET c5.name = 'Household', c5.price_cap = 2.0, c5.is_essential = false
MERGE (c6:Category {category_id: 'cat_personal'})
  SET c6.name = 'Personal Care', c6.price_cap = 2.0, c6.is_essential = false;

// ── Zones (Bengaluru — 5 zones) ──
MERGE (z1:Zone {zone_id: 'zone_koramangala'})
  SET z1.name = 'Koramangala', z1.location = point({latitude: 12.9352, longitude: 77.6245}), z1.avg_delivery_time_min = 12
MERGE (z2:Zone {zone_id: 'zone_indiranagar'})
  SET z2.name = 'Indiranagar', z2.location = point({latitude: 12.9716, longitude: 77.6412}), z2.avg_delivery_time_min = 14
MERGE (z3:Zone {zone_id: 'zone_hsr'})
  SET z3.name = 'HSR Layout', z3.location = point({latitude: 12.9116, longitude: 77.6474}), z3.avg_delivery_time_min = 13
MERGE (z4:Zone {zone_id: 'zone_whitefield'})
  SET z4.name = 'Whitefield', z4.location = point({latitude: 12.9698, longitude: 77.7500}), z4.avg_delivery_time_min = 18
MERGE (z5:Zone {zone_id: 'zone_electronic_city'})
  SET z5.name = 'Electronic City', z5.location = point({latitude: 12.8452, longitude: 77.6602}), z5.avg_delivery_time_min = 16;

// ── Dark Stores (5 of 25 — template for the rest) ──
MERGE (ds1:DarkStore {store_id: 'ds_kor_01'})
  SET ds1.name = 'Koramangala Store 1', ds1.location = point({latitude: 12.9352, longitude: 77.6245}), ds1.capacity_sqft = 3000, ds1.max_skus = 2500, ds1.active = true, ds1.city = 'bengaluru'
MERGE (ds2:DarkStore {store_id: 'ds_kor_02'})
  SET ds2.name = 'Koramangala Store 2', ds2.location = point({latitude: 12.9280, longitude: 77.6190}), ds2.capacity_sqft = 2500, ds2.max_skus = 2000, ds2.active = true, ds2.city = 'bengaluru'
MERGE (ds3:DarkStore {store_id: 'ds_ind_01'})
  SET ds3.name = 'Indiranagar Store 1', ds3.location = point({latitude: 12.9716, longitude: 77.6412}), ds3.capacity_sqft = 3500, ds3.max_skus = 3000, ds3.active = true, ds3.city = 'bengaluru'
MERGE (ds4:DarkStore {store_id: 'ds_hsr_01'})
  SET ds4.name = 'HSR Store 1', ds4.location = point({latitude: 12.9116, longitude: 77.6474}), ds4.capacity_sqft = 2800, ds4.max_skus = 2200, ds4.active = true, ds4.city = 'bengaluru'
MERGE (ds5:DarkStore {store_id: 'ds_wf_01'})
  SET ds5.name = 'Whitefield Store 1', ds5.location = point({latitude: 12.9698, longitude: 77.7500}), ds5.capacity_sqft = 4000, ds5.max_skus = 3500, ds5.active = true, ds5.city = 'bengaluru';

// ── Store-Zone Relationships ──
MATCH (ds1:DarkStore {store_id: 'ds_kor_01'}), (z1:Zone {zone_id: 'zone_koramangala'})
MERGE (ds1)-[:IN_ZONE {primary: true}]->(z1);
MATCH (ds2:DarkStore {store_id: 'ds_kor_02'}), (z1:Zone {zone_id: 'zone_koramangala'})
MERGE (ds2)-[:IN_ZONE {primary: true}]->(z1);
MATCH (ds3:DarkStore {store_id: 'ds_ind_01'}), (z2:Zone {zone_id: 'zone_indiranagar'})
MERGE (ds3)-[:IN_ZONE {primary: true}]->(z2);
MATCH (ds4:DarkStore {store_id: 'ds_hsr_01'}), (z3:Zone {zone_id: 'zone_hsr'})
MERGE (ds4)-[:IN_ZONE {primary: true}]->(z3);
MATCH (ds5:DarkStore {store_id: 'ds_wf_01'}), (z4:Zone {zone_id: 'zone_whitefield'})
MERGE (ds5)-[:IN_ZONE {primary: true}]->(z4);

// ── Zone Connectivity ──
MATCH (z1:Zone {zone_id: 'zone_koramangala'}), (z2:Zone {zone_id: 'zone_indiranagar'})
MERGE (z1)-[:CONNECTED_TO {distance_km: 5.2, avg_travel_min: 15}]->(z2);
MATCH (z1:Zone {zone_id: 'zone_koramangala'}), (z3:Zone {zone_id: 'zone_hsr'})
MERGE (z1)-[:CONNECTED_TO {distance_km: 3.8, avg_travel_min: 10}]->(z3);
MATCH (z3:Zone {zone_id: 'zone_hsr'}), (z5:Zone {zone_id: 'zone_electronic_city'})
MERGE (z3)-[:CONNECTED_TO {distance_km: 8.1, avg_travel_min: 22}]->(z5);
MATCH (z2:Zone {zone_id: 'zone_indiranagar'}), (z4:Zone {zone_id: 'zone_whitefield'})
MERGE (z2)-[:CONNECTED_TO {distance_km: 12.5, avg_travel_min: 35}]->(z4);
