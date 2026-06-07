# data_fabric — OFFLINE data & ML-ops layer (not in the live request path)

This package is **offline/batch tooling**, not part of the running serving
stack. The live system (`docker/docker-compose.gcp.yml`) does **not** import
`data_fabric` from any agent/orchestrator/api process, and the APScheduler in
`scheduler/` is **intentionally not started** on the single decision VM (a
1000-scenario Monte-Carlo + nightly batch jobs would steal CPU from the
low-latency decision path). The module-liveness gate
(`scripts/audit/module_liveness.py`) classifies everything here as TOOLING,
reachable via `make` targets / CI, never DEAD.

## What's here and how to run it (on-demand, from an ops box or CI cron)

| Area | Purpose | Invoke |
| --- | --- | --- |
| `feast/` | Feast feature views (Bengaluru + Mumbai) + streaming materialization. The agents read these views at inference via `synapse_common.features`. | `make feast-build`, `make feast-up` |
| `etl/parquet_etl.py` | CSV → Parquet for the Feast offline store (I-3 determinism). | `scripts/convert_to_parquet.py` / `make convert-parquet-mumbai` |
| `etl/quality_gates.py` | Data-quality contract used by streaming materialization. | imported by `feast/stream_materialization.py` |
| `jobs/drift_psi.py` | PSI demand-drift detection (emits `synapse_drift_psi`). | `make jobs-drift` |
| `jobs/conformal_recal.py` | Recalibrate Mumbai conformal intervals post-transfer (E-S6-04). | `make jobs-recal` |
| `jobs/feast_compact.py` | Compact the Feast offline parquet store. | `make jobs-feast-compact` |
| `scheduler/scheduler.py` | APScheduler orchestrator for the above jobs. **Run on-demand**, not on the live VM. | `make jobs-scheduler` |

## Removed in the module-liveness sweep (2026-06)
The dead, self-referential ETL/CDC/backfill cluster (`etl/{backfill,cdc,kafka_to_parquet,lineage,schema_evolution}.py`) had zero importers anywhere and was deleted. If a backfill capability is needed later, rebuild it against the current `synapse_common.kafka_client` + Feast schema.
