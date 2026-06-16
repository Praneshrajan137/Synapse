# ADR-049: Two-Tier Cost Model — $0 Demonstration, Costed Production

## Status
Accepted (2026-06-16) — the two-tier *decision* is accepted (operator directive,
"production-intent"). The Tier-P cost figures below are **planning estimates** to
be validated before any spend is committed (a one-way door).

Supersedes [ADR-039](ADR-039-gcp-deploy-pull-from-artifact-registry.md) **Rule 2**
(per-merge auto-deploy → now a Demonstration-tier weekly measure). Refines
[ADR-037](ADR-037-dual-deployment-target-cost-honesty.md) (cost honesty for I-1). Relates to
[ADR-036](ADR-036-gcp-single-vm-not-gke.md) (single-VM GCE).

## Context

Invariant **I-1** states the project is **$0 total cost** — all components
open-source or free-tier. [ADR-037](ADR-037-dual-deployment-target-cost-honesty.md) made that
*honest for a demonstrator*: a budget cap, a nightly/weekly VM auto-stop, and the
permanent Oracle Always-Free fallback keep spend at $0.

On 2026-06-16 the operator set the project's purpose to **production-intent** —
SYNAPSE is meant to eventually run a real operation. This collides with I-1 as an
absolute:

> **You cannot run an always-on, low-latency, multi-agent control plane — with
> real data ingestion and real SLOs — for $0.** Free tiers have no always-on
> compute that fits the stack, no durable managed data plane, and no GPU.

Left unconfronted, I-1 *silently caps* everything downstream and there is no honest
way to call the result "production." It also has a documented side effect: because
there was no named distinction between "what the free demonstrator does" and "what
a production system would do", **demonstration-tier reality kept being written in
production-tier language** — the exact narrative drift Phase 0 found and fixed
(the deploy pipeline deploys *weekly* but docs/comments claimed per-merge "live";
the VM is off ~6.5 days/week but was described as continuously fresh). The missing
construct is two explicit tiers.

A second, separate point I-1 conflates: **infra cost** vs **paid API clients**.
I-1's CI import gate bans `openai`/`anthropic`/`cohere`/`replicate` — that is the
*open-source / local-LLM (Ollama) ethos*, not an infra-cost line. The two must not
be merged, or "production tier" could be misread as "now we may call paid LLMs."

## Decision

SYNAPSE has **two named, explicit cost tiers**. A deployment is always in exactly
one, and which one is a stated operator choice — never an implicit assumption.

### Clarification of I-1 (two independent rules)

- **I-1a (infra cost):** the **Demonstration tier is $0**. The **Production tier**
  has a documented, bounded cost envelope (this ADR). I-1's "$0 total" wording now
  reads *"the Demonstration tier is $0 — see ADR-049."*
- **I-1b (no paid API clients):** unchanged and **absolute in both tiers**. No
  `openai`/`anthropic`/`cohere`/`replicate` imports, ever. LLM inference is local
  (Ollama) in both tiers. This is the project's open-source identity, independent
  of infra spend. (Enforced by the widened paid-import gate in `ci.yml`.)

### Tier D — Demonstration ($0, the default; what CI/CD targets today)

The current posture, now *named*. ADR-037's mechanisms **are** this tier:

| Aspect | Tier D reality |
|---|---|
| Infra | Oracle Always-Free (permanent $0) or GCP $300 trial + Terraform budget cap |
| Deploy cadence | Weekly schedule + `v*` tag + manual dispatch; **push-to-main builds+signs only** (supersedes ADR-039 Rule 2 — this is a cost measure, not a bug) |
| Live window | VM **stopped** between weekly runs → normally stale vs `main` HEAD (acceptable for a demo; the live-truth watchdog must only assert freshness inside the real up-window) |
| Data | Synthetic / generated (Bengaluru/Mumbai generators, `synthetic-` traffic) |
| Models | CPU-only smoke training in CI; full checkpoints trained out-of-band (free GPU/Colab) and published to HF Hub free tier |
| SLA | None. Latency/availability are best-effort |

### Tier P — Production (costed; activated only by explicit operator spend)

What "production-intent" actually requires. **No part of this is built until the
operator commits the spend** (one-way door).

| Aspect | Tier P requirement |
|---|---|
| Serving | Always-on, `min-instances >= 1`; no stop-window; real per-tier latency SLOs measured under real models |
| Data | Real ingestion adapters (orders/inventory/GPS); synthetic origin, if retained, is an explicit flag — never a hidden default |
| Data plane | Durable, backed-up Postgres + Redis + Kafka + Neo4j (managed or HA self-hosted) |
| Models | Periodic GPU retraining (batch, not always-on); published, calibrated, C46-green checkpoints |
| Reliability | Real multi-window burn-rate SLOs against real traffic; on-call/alerting |
| Governance | DPDPA cascade active on the real data path; threat model + secrets rotation (Phase 2) |

### Tier-P cost envelope (ESTIMATES — GCP asia-south1, USD/month, validate before spend)

Two shapes, both *minimal* production:

**P-min (self-hosted infra on one always-on VM)** — pragmatic first step:

| Line item | Est. /mo |
|---|---|
| 1× e2-standard-8 always-on (sustained-use) | ~$145 |
| 100 GB SSD persistent disk | ~$17 |
| Static IP + egress | ~$15–30 |
| Artifact Registry + Cloud Logging/Monitoring | ~$15 |
| GPU retraining (Vertex/Colab spot, weekly, amortized) | ~$10–20 |
| GCS backups | ~$5 |
| **P-min subtotal** | **~$220–300** |

**P-managed (durable managed data plane)** — production-grade:

| Line item | Est. /mo |
|---|---|
| Compute (GKE Autopilot or larger VM, min-instances≥1) | ~$200–400 |
| Cloud SQL Postgres (HA) | ~$130 |
| Memorystore Redis (1–5 GB) | ~$50–150 |
| Managed Kafka (Confluent/Redpanda basic) | ~$100–250 |
| Neo4j AuraDB Professional | ~$65–200 |
| Networking / egress / observability | ~$50–100 |
| GPU retraining (amortized) | ~$20 |
| **P-managed subtotal** | **~$700–1,200** |

> These are order-of-magnitude planning numbers, not quotes. They exist to make the
> ceiling *visible and decidable*, replacing the invisible $0 cap. Refine against a
> real GCP pricing-calculator run before committing.

## Consequences

- **I-1 reworded** in CLAUDE.md per I-1a/I-1b above (separate PR; the `doc_truth`
  gate can later pin the "Demonstration tier = $0" claim to this ADR).
- **The deploy cadence has a home.** The weekly/stopped-VM cadence is now a recorded
  Tier-D cost decision, closing the ADR-039 Rule 2 drift permanently.
- **The production path is a named, costed target**, not an implicit assumption.
  Phase 2 work (real ingestion, always-on serving, real SLOs, security hardening)
  maps explicitly to Tier P and is gated on the spend decision.
- **CI/CD is unchanged** — it continues to target Tier D. Nothing here authorizes
  spend; it authorizes a *decision frame*.
- **Phase 1 is tier-agnostic.** Closing the substance loop (real models train →
  publish → serve, C46 green) is required by *both* tiers and proceeds now at $0
  (free GPU/Colab + HF free tier).

## Alternatives considered

- **Keep I-1 absolute ($0 only).** Rejected for production-intent: it permanently
  caps the system at a demonstrator (no always-on serving, synthetic data only) and
  makes "production-intent" dishonest. (Valid if the purpose were "demo" — it is not.)
- **Drop I-1 entirely / go full managed now.** Rejected: destroys the $0
  demonstrator's distinctiveness and the open-source ethos, and commits spend before
  the substance loop (Phase 1) even proves the models are real. Premature one-way door.
- **One tier, "cheapest viable production."** Rejected: erases the genuinely-valuable
  $0 demonstrator that lets anyone run the full loop for free — the project's
  strongest reviewer-facing asset.
