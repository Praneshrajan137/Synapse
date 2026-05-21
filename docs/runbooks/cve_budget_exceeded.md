# Runbook: CVE Budget Exceeded

**Alert source:** `scripts/check_cve_budget.py` exits 1 in the
`sprint9-supply` CI job (WS-6 §M-sec-6).

## Symptoms
- CI build fails with `CVE budget breaches: ... age=Xd sla=Yd`.
- The breach lists per-CVE: severity, package, age in days, SLA in days.

## Likely Causes
1. A `CRITICAL` CVE published more than 7 days ago for a dependency
   we still pin.
2. A `HIGH` CVE >30 days old.
3. The `infrastructure/security/cve-budget.json` `first_seen`
   registry is stale.

## Verification
```bash
pip-audit -r packages/requirements.txt --format json | jq
pip-audit -r orchestrator/requirements.txt --format json | jq

cat infrastructure/security/cve-budget.json | jq '.first_seen'
```

## Mitigation
1. **Patch path:** bump the offending dependency in the requirements
   file + regenerate `uv.lock`. Run `python scripts/check_cve_budget.py`
   locally to confirm green.
2. **No upstream patch yet:** add the CVE id to
   `infrastructure/security/cve-budget.json` `exempt[]` with a
   commit-message explanation + a tracking GitHub issue. Set an
   expiry comment so the exemption is re-evaluated quarterly.
3. **Registry refresh:** if the CVE shows up as `NEW CVE` for the
   first time, run
   ```bash
   python scripts/check_cve_budget.py --update-registry
   ```
   and commit the updated `first_seen` timestamps.

## Postmortem Anchor
For any exempted CVE, link the upstream issue + the date we expect a
patch + the next quarterly review.
