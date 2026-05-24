# Runbook: Reward-Weight Divergence

**Alert source:** `rate(synapse_reward_weight_divergence_total[5m]) > 0`
(WS-3 §M3, ADR-031).

## Symptoms
- `synapse_reward_weight_divergence_total{agent="<agent>",key="<key>"}`
  counter incrementing.
- An agent's reward function is being called with a kwarg whose value
  diverges from `agents/<agent>/training/reward_config.WEIGHTS`.
- No production impact in Sprint 8 (shadow mode — runtime kwargs still
  win). In Sprint 9 this becomes an Alertmanager warning.

## Likely Causes
1. A researcher locally overrode a kwarg during experimentation and
   forgot to update spec.yaml.
2. A training pipeline regression — Flower federated learning client
   is passing stale weights from a prior epoch.
3. spec.yaml was edited but `scripts/spec_cli.py generate-reward-config`
   was not re-run; `reward_config.py` is stale.

## Verification
```bash
# 1. Inspect the agent's spec block.
yq '.reward.weights' agents/<agent>/spec.yaml

# 2. Compare against the runtime config.
cat agents/<agent>/training/reward_config.py

# 3. Regenerate + diff.
python scripts/spec_cli.py generate-reward-config --check
```

## Mitigation
- **Stale config:** `python scripts/spec_cli.py generate-reward-config`
  then commit the regenerated `reward_config.py`.
- **Researcher override:** confirm with the researcher and, if intentional,
  update spec.yaml + regenerate.
- **Training regression:** revert the training pipeline change; the
  shadow counter caught it before the cutover.

## Sprint-9 cutover note
Sprint 9 promotes spec.yaml to source-of-truth; the divergence counter
graduates to an Alertmanager-routed warning, and a divergence ≥1 per
hour blocks merges via a CI gate that calls
`synapse_reward_weight_divergence_total` over the last build window.

## Postmortem Anchor
Always link the spec.yaml commit and the runtime call site.
