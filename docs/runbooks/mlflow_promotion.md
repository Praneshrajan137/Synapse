# Runbook: MLflow Model Promotion

## Context
SYNAPSE uses MLflow Model Registry stages: `None → Staging → Production → Archived`.
Promotions are gated by training-time metrics *and* shadow/canary traffic
checks. The promotion flow is automated in `.github/workflows/cd.yml` on
tagged releases but can be invoked manually from this runbook.

## Promotion criteria

| Stage transition | Required evidence |
|------------------|-------------------|
| None → Staging | `pytest agents/<agent>/tests -v` green; MLflow run logs `convergence_speedup > 2.5` and `calibration_coverage_90 >= 0.85` |
| Staging → Production | 4-hour shadow evaluation: online metrics within 2% of Staging offline metrics; drift PSI < 0.1 across all features; no Prometheus alert |
| Production → Archived | Successor tagged in Production for ≥24h with no incident; audit entry captures archive reason |

## Manual promotion (emergency)

```bash
export MLFLOW_TRACKING_URI=https://mlflow.example.com
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name='demand_prophet_hgt_tft',
    version='42',
    stage='Production',
    archive_existing_versions=True,
)"
```

## Rollback triggers

Immediate rollback from Production to Archived when any of:

- `synapse_drift_psi{agent,feature}` > 0.25 for 10 minutes.
- `synapse_ollama_cache_hit_rate{tier="tier_2"}` < 0.70 for 15 minutes
  traced back to the new model's system prompt.
- Any I-6 (price cap) or I-14 (context append) invariant violation in CI.
- Incident report classified `P0` or `P1` by on-call.

Rollback command:

```bash
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name='demand_prophet_hgt_tft',
    version='41',       # prior Production version
    stage='Production',
    archive_existing_versions=False,
)"
```

Always file an incident review and add an error pattern to `CLAUDE.md`.

## Shadow evaluation

```bash
make shadow-evaluate AGENT=demand_prophet VERSION_CANDIDATE=42 VERSION_CURRENT=41 DURATION_H=4
```

Outputs `artifacts/shadow/<agent>-<timestamp>.html` with:
- per-feature drift (PSI, Wasserstein)
- prediction divergence distribution
- conformal coverage recalibration diff
- decision-latency delta

## Canary rollout

After shadow passes, route 5% of traffic via the orchestrator tier router:

```bash
make canary-deploy AGENT=demand_prophet VERSION=42 TRAFFIC_PCT=5
```

Hold for 1 hour with Prometheus alerts muted at P2; escalate to 25%, 50%,
100% over 4 hours with checkpoint verification at each step.

## Audit obligations (I-4)

Every stage transition writes to `audit_decisions.model_lifecycle` with:
- decision_id
- agent
- model_name
- version
- from_stage / to_stage
- operator (Vault app token identity)
- evidence_links (MLflow run URL, shadow report, canary dashboard)

These rows are immutable (Postgres role permissions). Right-to-erasure
requests do **not** scrub these rows because they contain no personal
data — only model metadata.
