# ADR-004: Feast for Feature Store

## Status
Accepted

## Context
Agents need point-in-time correct feature retrieval with no data leakage.

## Decision
Use Feast with local provider, Redis online store, file-based offline store. 8 feature views covering demand, store state, weather, events, supplier, perishables, routing, and pricing.

## Consequences
- Zero-cost feature serving (local provider)
- Redis already in stack for caching
- Must run `feast apply` after feature definition changes

## Alternatives Rejected
- Custom feature pipeline: more work, less standardized
- Tecton/Hopsworks: paid services, violates I-1
