# ADR-006: Kafka for Event Streaming

## Status
Accepted

## Context
Agents need asynchronous, durable, ordered event communication with replay capability.

## Decision
Use Kafka (bitnami) with ZooKeeper. 16 topics frozen after Sprint 1. Auto-create disabled. All agents use synapse_common.kafka_client with deterministic serialization (I-13). Redis streams as fallback (I-7).

## Consequences
- Durable event log with configurable retention (24h to infinite)
- Replay capability for debugging and re-processing
- Topic registry is frozen: new topics require an ADR

## Alternatives Rejected
- RabbitMQ: no replay, no ordered partitioning
- Redis Streams only: less durable, no partition-level ordering at scale
