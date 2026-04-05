# SYNAPSE Domain Models Reference

## Pydantic Models (packages/synapse_common/models.py)
- SynapseBaseModel: frozen=True, extra=forbid, deterministic JSON (I-13)
- DecisionTier: TIER_1 (<100ms) | TIER_2 (<500ms) | TIER_3 (2-15s) | TIER_4 (15-120s)
- AgentName: 8 agents as enum
- ContextMessage: immutable, append-only (I-14)
- AgentProposal: A2A proposal with utility_score, confidence, justification_trace
- ConsensusDecision: full provenance with pareto_weights and audit_trace (I-4)
- DemandForecast: 5 horizons, conformal intervals, drift detection
- RoutePlan: stops, distance, time, freshness violations
- InventoryAction: reorder/transfer/markdown with safety stock
- PricingDecision: HARD 1.3x cap on essentials enforced via validator (I-6)

## Kafka Topics (16 — frozen after Sprint 1)
See infrastructure/kafka/topics.json for the complete registry.
Naming: synapse.<domain>.<event_type>
Always use synapse_common.kafka_client — direct kafka-python = PR rejection.

## Feast Feature Views
- sku_demand_signals: rolling stats, orders, trend (TTL: 1h)
- store_operational_state: occupancy, fill rate, pick time (TTL: 5min)
- weather_context: temp, humidity, precipitation (TTL: 30min)
- event_calendar: IPL, festivals, venue data (TTL: 24h)
- supplier_performance: lead time, fill rate, trust score (TTL: 6h)
- perishable_state: expiry, temp deviation, quality (TTL: 15min)
- routing_context: delivery time, riders, traffic (TTL: 5min)
- price_elasticity: own/cross elasticity, competitor delta (TTL: 6h)

## Neo4j Node Types
DarkStore, Warehouse, Supplier, SKU, Rider, Zone, Event, Category
All have uniqueness constraints. See infrastructure/neo4j/init.cypher.
