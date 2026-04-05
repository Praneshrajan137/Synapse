# ADR-005: Neo4j for Knowledge Graph

## Status
Accepted

## Context
The Digital Twin and agent reasoning require a structural backbone representing dark stores, zones, SKUs, suppliers, and their relationships.

## Decision
Use Neo4j 5 Community Edition with APOC plugin. 8 node types with uniqueness constraints, composite indexes, geospatial indexes, and full-text search. Graph serves as the ontology backbone (I-3) and twin structural model (I-12).

## Consequences
- Rich graph queries for routing, inventory, and supplier analysis
- Geospatial indexes enable distance-based store/zone queries
- MERGE-based seeding enables idempotent initialization

## Alternatives Rejected
- PostgreSQL with recursive CTEs: limited graph traversal performance
- ArangoDB: smaller community, fewer enterprise patterns
