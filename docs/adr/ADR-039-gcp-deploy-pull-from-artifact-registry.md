# ADR-039: GCP Deploy — Pull-from-Artifact-Registry is the Contract

## Status
Accepted (Sprint 12, 2026-05-28)

## Context

Between 2026-05-24 and 2026-05-27, four PRs landed on `main`:

| PR | Merge SHA | Shipped |
|---|---|---|
| #7 | `c16bd9f` | Backend Phases 1–8 (audit chain, A2A v2, distributed-system primitives) |
| #6 | `9685463` | Atlas Console v1.1 + ProposalConstellation + chromatic OKLCH palette |
| #9 | `f919caa` | Sprint 10 — `cd-gcp.yml`, Terraform, `docker-compose.gcp.yml`, IAP / WIF |
| #10 | `0967d5e` | Sprint 11 — verify-claims registry, Helm 11/11, contract hardening |

The GCE VM kept serving the **pre-merge** UI (purple/violet pre-chromatic build) the entire time. Investigation found two compounding defects:

1. **Trigger gap.** `.github/workflows/cd-gcp.yml` fired only on `push: tags: v*`. No `v*` tag had been pushed since the prior release. The CD workflow never ran for any of the 4 merges, so the VM's checkout was frozen at the last tagged SHA and Artifact Registry received no new images.

2. **`build:` defeats the supply chain.** `docker/docker-compose.gcp.yml` defined all 12 SYNAPSE-owned services with `build:` directives. `docker compose pull` is a no-op for `build:` services, and `docker compose up -d` reuses the cached local image unless `--build --force-recreate` is passed. Even when the workflow did run (under a manual `workflow_dispatch`), the freshly pushed, cosign-signed images in Artifact Registry were never pulled — they existed only as ceremony. The VM rebuilt from its own (stale) git checkout.

A secondary defect — `infrastructure/gcp/verify_images.sh` listed 11 of 12 signed images, omitting `frontend` — meant the Cosign-verify gate on the VM reported "all verified" while never checking the very service the user could see.

Together these mean: the supply-chain layer (Cosign + SBOM + provenance) and the deploy layer (compose + VM) were not connected. The signed images and the running images were unrelated artifacts.

## Decision

**The GCP deploy is a pull-from-Artifact-Registry contract.** Three load-bearing rules, each backed by a mechanical CI check:

### Rule 1 — `docker-compose.gcp.yml` uses `image:` only

Every SYNAPSE-owned service references the AR URL:

```yaml
image: ${SYNAPSE_AR_REPO_URL}/<service>:${SYNAPSE_VERSION:-latest}
pull_policy: always
```

No `build:` directive on any of the 12 services. Upstream images (kafka, redis, neo4j, postgres, mlflow, prometheus, grafana, nginx) keep their pinned upstream tags — they are not ours to sign.

Enforced by `verify_claims.py` check **C26** (`gcp_compose_pulls_images`): parses the compose file, fails CI if any of the 12 SYNAPSE services carries a `build:` key or its `image:` does not match the AR URL pattern.

### Rule 2 — CD fires on merge to `main`

`cd-gcp.yml` triggers on:
- `push: branches: [main]` — auto-deploy, version `main-<sha7>`, image tags `:main-<sha7>` + `:main` + `:latest`
- `push: tags: [v*]` — explicit release, version `<tag>`, image tags `:<tag>` + `:latest`
- `workflow_dispatch` — manual re-deploy, version `dryrun-<sha7>`, image tag `:latest` (with `dryrun: true` to skip the VM step)

The compose file's default `${SYNAPSE_VERSION:-latest}` keeps working for manual `docker compose up` sessions on the VM; the workflow writes `.env.gcp.version` on the VM with the exact pushed version so the deploy uses it verbatim. The deploy step is `docker compose pull && docker compose up -d --pull always --force-recreate --remove-orphans`.

### Rule 3 — `verify_images.sh` covers every signed image

The Cosign-verify gate's `IMAGES=(...)` list must be a superset of the `cd-gcp.yml` build matrix. `frontend` is in the list. Any future image added to the matrix must be added to the list in the same PR.

Enforced by `verify_claims.py` check **C27** (`verify_images_covers_matrix`).

### Visible deployed version (corollary)

Build-args carry `SYNAPSE_BUILD_SHA` + `SYNAPSE_BUILD_TIME` into every image. The API gateway exposes `GET /version` returning `{git_sha, build_time, service, version}`. The frontend Shell shows a `BuildSHAChip` in the app header — a click copies the SHA. "The UI looks stale" is a falsifiable claim, not a vibe.

## Consequences

### Positive

- Merges to `main` land on the VM within ~15 minutes (CD build time), never sitting until someone remembers to tag.
- Cosign signatures become load-bearing instead of decorative — the running container's digest is the signed digest, verified at boot.
- The VM no longer needs the build toolchain (node, pnpm, Python build deps). It only needs Docker, `gcloud`, and `cosign`.
- The first three checks of "why is the UI stale" become one-line answers:
  1. Frontend chip / `curl /version` shows the SHA — match to `git rev-parse main`.
  2. `gh run list --workflow=cd-gcp.yml` — green for HEAD?
  3. `gcloud artifacts docker images list .../synapse/frontend` — tagged at HEAD?

  If all three are green and the UI is still wrong, the cause is *only* a browser cache (Ctrl+Shift+R) — by construction, nowhere else for the failure to hide.

### Negative

- Compose-level "edit one file, run `up`" iteration on the VM no longer works for SYNAPSE services — they come from AR. This is the right trade: ad-hoc VM edits were never auditable anyway. Local dev still uses `docker-compose.yml` (the non-GCP file), which keeps `build:` for fast iteration.
- `workflow_dispatch` dryruns push `:latest` to AR, so a dryrun *does* update what a fresh VM would pull on `:latest`. This is intentional — the dryrun path is for testing the build + sign chain, not for sandbox tagging.

### Neutral

- Compose service `api` keeps its name (so `depends_on` chains stay readable) but pulls the AR image `api-gateway` (matching the CD matrix). A comment in the compose file flags the alias.

## Related ADRs

- **ADR-008** — Containerization strategy (parent).
- **ADR-030** — Dual-deployment target (compose for dev, Helm for K8s; this ADR is the compose half of the GCP path).
- **ADR-034** — Production topology.
- **ADR-036** — GCP primary = single-VM GCE, not GKE (the deployment shape this ADR makes coherent).
- **ADR-037** — Dual-deployment cost honesty (Oracle Always-Free remains the $0 fallback; this ADR does not affect that path).

## Verification

- `python scripts/audit/verify_claims.py` — C26 and C27 must both PASS.
- `make verify-claims` — same, plus the summary line reflects 21 mechanical checks.
- After the next merge to main:
  - `gh run list --workflow=cd-gcp.yml --limit=5` shows a green run for HEAD's SHA.
  - `curl https://<host>/version` returns `{"git_sha":"<HEAD>", ...}`.
  - Frontend header chip matches `git rev-parse main | cut -c1-7`.

## Sprint anchor

Sprint 12 — Deploy Truth. One workstream, one ADR, four code changes, two new mechanical checks, one new visible signal. The chromatic / Atlas-Console UI that landed in PRs #6, #7, #9, #10 now reaches the GCP VM on the next merge.
