# ADR-019: DragonflyDB Evaluation in Sprint 5

## Status
Accepted

## Context
Redis 7 is the default cache and Feast online store. DragonflyDB (BSL 1.1, free for non-competing use) claims 25× throughput on multi-core servers via its shared-nothing thread architecture. SYNAPSE's hot path includes Feast online lookups, semantic decision cache, and Kafka offset management — any of which could become the bottleneck at 500 orders/min sustained load. Adopting a new cache mid-sprint without measurement is reckless; not evaluating it forfeits a potential 25× speedup.

## Decision
**Evaluate** DragonflyDB during Sprint 5 load testing as a side-by-side comparison with Redis 7. Run the standard locust load suite against both backends. Adoption criteria — adopt if **all** of the following hold:
1. Tier 2 p99 latency drops ≥ 30% vs Redis 7.
2. No correctness regressions in Feast online lookups or audit trail.
3. License (BSL 1.1) verified compatible with Apache 2.0 distribution (non-competing use clause).
4. ARM64 image available for Oracle Cloud deployment.

If any criterion fails, retain Redis 7. The evaluation harness is `tests/load/locustfile.py --backend {redis|dragonfly}`; results recorded in `docs/sprint5/dragonflydb_evaluation.md`.

## Consequences
- Time-boxed evaluation prevents indefinite "shall we migrate?" debates.
- DragonflyDB uses port 6380 externally to avoid Redis port collision (E-S5-05).
- Decision is reversible via single env var change in compose files.

## Alternatives Rejected
- **Migrate without evaluation**: rejected — premature optimization.
- **Stay on Redis without evaluation**: rejected — leaves measurable performance gain on the table.
- **KeyDB / Valkey**: rejected for evaluation — DragonflyDB has the larger reported delta; if it fails, Redis remains.
