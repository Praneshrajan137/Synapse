# ml_pipelines — OFFLINE training & evaluation pipelines (not in the live request path)

This package is **offline training/eval tooling**, run via `make` / CI / a GPU
notebook — never imported by the running serving stack. The module-liveness
gate (`scripts/audit/module_liveness.py`) classifies it as TOOLING.

| Area | Purpose | Invoke |
| --- | --- | --- |
| `transfer/transfer.py` | Transfer learning (Bengaluru → Mumbai fine-tuning). | `make transfer-train` |
| `transfer/cold_start_baseline.py` | Cold-start control models for A/B testing (E-S6-14). | `make cold-start-baseline` |
| `ab_test/` | A/B framework (Welch t-test + Bonferroni) + runner. Also CI-gated. | `make ab-test` |
| `drift/evidently_runner.py` | PSI + Wasserstein drift (the `_compute_psi` fallback used by `data_fabric/jobs/drift_psi.py`). | via `make jobs-drift` |

For end-to-end agent training (real checkpoints), see
`notebooks/train_synapse_agents.ipynb` (Colab/Kaggle GPU).

## Removed in the module-liveness sweep (2026-06)
`transfer/cold_start_tracker.py` had zero importers/references and was deleted.
