# ADR-037: Dual Cloud Deployment — Cost Honesty for I-1

## Status
Accepted (Sprint 10, 2026-05-26)

## Context

CLAUDE.md invariant **I-1** states: *all components are open-source or
free-tier — $0 total cost*. Sprint 6 satisfied this with Oracle Cloud
Always-Free (4 ARM OCPU / 24 GB / 200 GB), which is *permanent* $0
(see [`infrastructure/oracle/`](../../infrastructure/oracle/)).

Sprint 10 promotes Google Cloud to the *primary* deployment target
(ADR-036). GCP has **no permanent always-free tier that fits the
SYNAPSE stack**. The available bargain is:

- A one-time **$300 free trial credit** valid for 90 days.
- A trickle of always-free tier (1 e2-micro VM, 5 GB GCS) that the
  full stack does not fit on.

Without an honest cost model, "GCP primary" silently breaks I-1 the
moment the trial credit drains. This ADR captures the mechanism that
makes I-1 *enforceable* in the GCP-primary world.

## Decision

### Layered cost guardrails (Tier-A hardening)

1. **Terraform-managed monthly budget cap**
   ([`infrastructure/gcp/terraform/budget.tf`](../../infrastructure/gcp/terraform/budget.tf))
   set to $300 USD (the trial-credit ceiling). Alerts fire at
   25 / 50 / 75 / 90 / 100 % of actual spend and at 100 % of
   forecasted spend, via email + the billing account's default
   monitoring channels.

2. **Nightly VM auto-stop schedule**
   ([`google_compute_resource_policy.auto_stop`](../../infrastructure/gcp/terraform/main.tf))
   stops the VM at 23:00 IST and restarts it at 09:00 IST every day.
   Concrete economics:

   | Schedule | On-demand $/mo | Spot $/mo | Free-trial duration |
   |----------|----------------|-----------|---------------------|
   | Always-on (no schedule) | $195 | $58 | ~6 weeks |
   | 14 h/day on (default) | ~$120 | ~$36 | ~10 weeks |
   | 8 h/day on (weekdays) | ~$65 | ~$19 | **~4.5 months** |
   | Stopped (disk + IP only) | $24 | $24 | n/a |

3. **Oracle Always-Free as a one-command fallback**. The
   `infrastructure/oracle/` + `docker/docker-compose.cloud.yml` +
   `.github/workflows/sprint6-e2e-oracle.yml` path is untouched.
   When trial credit expires (or budget alert fires hard), rotation is:

   ```
   gcloud compute instances stop synapse-demo   # halt GCP cost
   make deploy-oracle-terraform                 # provision Oracle (one-time)
   make deploy-oracle-setup deploy-oracle-push  # cut over
   ```

   The two clouds run the same agents, the same audit chain, the same
   8 spec.yaml files. Migration is operational, not architectural.

### Honest framing in user-facing docs

- [`README.md`](../../README.md) deployment section: GCP listed as
  **primary** with the $300/90-day trial caveat called out inline,
  Oracle as **"Permanent $0 fallback"** in a sibling subsection.
- [`docs/deploy/gcp-quickstart.md`](../deploy/gcp-quickstart.md):
  cost table reproduced verbatim, budget alert step is REQUIRED
  not optional.
- ADR-036 and this ADR cross-linked from both clouds' READMEs.

### What this ADR refuses

- We do **not** silently increase the budget cap above $300 in
  Terraform defaults. If a deploy needs more, the operator sets
  `var.budget_amount_usd` and explicitly acknowledges the cost.
- We do **not** auto-disable the budget when running short benchmarks
  ("just this once" is how credit is lost).
- We do **not** archive the Oracle path. Sprint 6 verification runs
  through it; it is the canonical free target for CI.

## Consequences

**Honest:**

- An outside reader can verify I-1 by reading two Terraform files and
  one ADR. No tribal "we shut it down at night" knowledge required.
- The deploy path produces a deterministic worst-case
  `terraform apply → $300 budget` bound; nothing in the configuration
  causes runaway cost.

**Operational:**

- The auto-stop schedule means a teammate hitting the demo URL at
  03:00 UTC sees `Connection refused`. The schedule cron is in
  `terraform.tfvars`; the operator owns the day/night cut.
- The Oracle fallback is real but cold — there is no live data
  replication between clouds. A cutover loses anything not in the
  daily GCS/Object-Storage backups.

**Strategic:**

- The next time a budget-relaxing event happens (paid demo, customer
  pilot, grant), ADR-036's "trigger to revisit" criteria become the
  guidance for promoting GKE / dropping Oracle / both.

## Verification

The plan's Phase 9 must verify:

- `terraform output budget_status` returns `ENABLED ($300 cap …)`
  when `billing_account_id` is set.
- `gcloud compute resource-policies describe <vm>-auto-stop --region=<region>`
  returns the cron schedule.
- Triggering the 25% threshold (manually adding a budget rule or
  observing a real bill) sends an email — captured in the deploy
  smoke test.

## References

- I-1 (cost invariant) in [CLAUDE.md](../../CLAUDE.md)
- [ADR-030: Dual deployment target (compose + Helm)](ADR-030-dual-deployment-target.md)
- [ADR-036: GCP single-VM, not GKE](ADR-036-gcp-single-vm-not-gke.md)
- [`infrastructure/gcp/`](../../infrastructure/gcp/) — primary
- [`infrastructure/oracle/`](../../infrastructure/oracle/) — fallback
- [GCP Free Trial terms](https://cloud.google.com/free/docs/free-cloud-features)
- [Oracle Always-Free terms](https://www.oracle.com/cloud/free/#always-free)
