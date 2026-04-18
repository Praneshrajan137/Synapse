# Runbook: Model Rollback

**Severity**: P0/P1 — invoked when a promoted model causes incorrect decisions, drift, or invariant violations.

## When to invoke

This runbook supplements `mlflow_promotion.md` (which covers promotion). Invoke
rollback when ANY of the following are true:

- `synapse_drift_psi{agent,feature}` > 0.25 for 10 minutes
- `synapse_ollama_cache_hit_rate{tier="tier_2"}` < 0.70 for 15 minutes traced
  back to a new model's system prompt
- I-6 (price cap) or I-14 (context append) invariant violation in CI
- P0/P1 incident classification by on-call
- A/B test stop condition triggered (Cohen's d for harm > 0.3)

## Pre-rollback checklist

```bash
# Identify currently promoted version
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
for v in client.search_model_versions(\"name='<model_name>'\"):
    if v.current_stage == 'Production':
        print(f'Current Production: v{v.version}, run_id={v.run_id}')
"

# Identify the rollback target (prior Production)
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
for v in sorted(client.search_model_versions(\"name='<model_name>'\"),
                key=lambda x: -int(x.version)):
    if v.current_stage == 'Archived' and v.tags.get('was_production') == 'true':
        print(f'Rollback target: v{v.version}'); break
"
```

## Execute rollback

```bash
export MLFLOW_TRACKING_URI=https://mlflow.example.com
python -c "
import mlflow
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name='<model_name>',
    version='<prior_version>',
    stage='Production',
    archive_existing_versions=False,  # keep failing version for forensics
)
client.set_model_version_tag('<model_name>', '<prior_version>', 'rollback', 'true')
client.set_model_version_tag('<model_name>', '<prior_version>', 'incident_id', '<id>')
"
```

## Post-rollback verification

1. Wait 5 minutes for orchestrator to refresh its model registry cache.
2. Verify the rolled-back version is now serving:
   ```bash
   curl -s http://localhost:8085/agents/<agent>/model-version
   ```
3. Confirm the offending alert clears:
   - Drift PSI returns < 0.1
   - Cache hit rate climbs > 0.70
   - No new I-6/I-14 violations in `audit_decisions`
4. File an incident review and add an error pattern to `CLAUDE.md`.

## Audit trail (mandatory — I-4)

Every rollback writes to `audit_decisions.model_lifecycle`:

```sql
INSERT INTO audit_decisions.model_lifecycle (
    decision_id, agent, model_name, version,
    from_stage, to_stage, operator, evidence_links, reason
) VALUES (
    gen_random_uuid(), '<agent>', '<model_name>', '<prior_version>',
    'Archived', 'Production', current_user,
    jsonb_build_object('mlflow', '<run_url>',
                       'shadow', '<shadow_report>',
                       'incident', '<incident_url>'),
    'rollback: <reason>'
);
```

This row is immutable (Postgres role permissions), satisfying DPDPA-B as it
contains no personal data.

## Communication template

```
Subject: [P1] Model rollback — <model_name> v<failing> → v<rollback>

What: Rolled back <model_name> from version <failing> to <rollback>
Why: <PSI > 0.25 / cache collapse / I-6 violation / A/B harm>
Impact: ~<N> decisions affected between <promote_time> and <rollback_time>
Status: Resolved at <timestamp>; incident review tracked at <link>
Next: Postmortem in 48h; `tests/oracle/` regression test added before re-promotion
```

## Forensics

- Keep the failing version unarchived for at least 7 days for forensic analysis.
- Pull the LangSmith traces from the failure window into `artifacts/incident_<id>/`.
- Run `evidently_runner.py --window 24h --version <failing>` to characterize the drift.
- Update the agent's `tests/oracle/` suite with the failing-case scenario before re-promotion.

## See also

- `mlflow_promotion.md` — promotion gates and shadow/canary flow
- `kv_cache_collapse.md` — when cache collapse caused the problem
- `llm_hallucination.md` — when output correctness drove rollback
