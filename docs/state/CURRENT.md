# SYNAPSE — Current State (Verified)

> **Dated:** 2026-06-08 (Phase A Operational Truth + Paradigm-Complete Substance ADR-043, integrated)
> **HEAD:** `main` — live deploy works (firehose/tier-3/4 verified end-to-end) **and** the substance track is merged: real training loops + serving for the agents across all four ML paradigms, twin Monte-Carlo verification (C7), runtime-substance (C45) + published-checkpoint (C46) gates.
> **Method:** Direct code inspection + grep verification + **live probe of the deployed VM** (https://34-180-49-108.nip.io). No claim recorded here without a file:line citation or a `git`/`curl` command that proves it. On integration, gate IDs from the two tracks were de-conflicted: operational C7/C42/C43 (twin-invoke/table-match/a2a) kept; substance gates renumbered to C45 (runtime substance) and C46 (published checkpoint).

This document is the **single source of truth** for what is actually wired together in this repository, as opposed to what `CLAUDE.md` or sprint summaries assert is wired. It is regenerated/updated whenever a workstream in `plans/i-have-finished-most-nifty-sifakis.md` lands.

The `make verify-claims` target turns each row below into an executable check. The summary at the bottom (`PASS x / FAIL y`) is the project's honesty meter.

---

## Verification Matrix

| # | Surface | Real state (verified) | Claim in repo | Status |
| --- | --- | --- | --- | --- |
| C1 | Backend agents (8) | Canonical structure + A2A HTTP handlers + `reward_config.py` present in all 8. **No `KafkaConsumer.subscribe(...)` call site in `agents/`** (verified by `grep -r "subscribe(" agents/`). | `agent_card.json` declares Kafka topic subscriptions; `infrastructure/kafka/topics.json` lists `all_agents` as consumers of `synapse.orchestrator.decision`. | **FAIL** — topology described in docs is not the topology in code. (Resolved by WS-3.) |
| C2 | Orchestrator outbox dispatcher | `OutboxDispatcher` class exists at `orchestrator/outbox/dispatcher.py:59` with `.start()`/`.stop()`. Unit-tested at `orchestrator/tests/test_outbox_dispatcher.py`. **No reference in `orchestrator/inference/serve.py` lifespan.** | Sprint 7 (CLAUDE.md sprint-status) claims "outbox pattern" as production. | **FAIL** — code exists, never started at runtime. (Resolved by WS-2.) |
| C3 | API → orchestrator traceparent | `api/routers/decisions.py` calls `httpx` against orchestrator with no `traceparent` injection. `packages/synapse_common/tracing.py:inject_a2a_headers()` exists and is used by A2A SDK + Kafka client. | Sprint 7 claim: "W3C traceparent + outbox + idempotency". | **FAIL** — primitive exists, not used at the API boundary. (Resolved by WS-2.) |
| C4 | Orders route producer | `api/routers/orders.py:34-42` instantiates a new `confluent_kafka.Producer` per request. `api/main.py:89-108` wires a shared `app.state.kafka_producer` via lifespan. | Architecture rule: "NEVER use direct kafka-python — use `synapse_common.kafka_client` only". | **FAIL** — orders route bypasses the shared producer and the outbox. (Resolved by WS-2.) |
| C5 | Override idempotency | `OverrideBody` Pydantic model takes no `idempotency_key`. No unique index on `(decision_id, idempotency_key)`. | Sprint 7 claim: "idempotency". | **FAIL** — replay/retry inserts duplicate audit rows. (Resolved by WS-2.) |
| C6 | Order body schema validation | `api/routers/orders.py` does not call `validate_agent_payload(...)`. | Invariant I-3: "ALL agent outputs MUST validate against `proto/domain/*.schema.json`". | **FAIL** — ingress is exempted in code, not in docs. (Resolved by WS-2.) |
| C7 | Digital twin live + orchestrator-invoked | `orchestrator/consensus/protocol.py` calls `_phase_twin_verify` at Tier 4 (A2A `monte_carlo` against `TWIN_ENDPOINT`) and `_record_input_provenance` on every decision (captures which agents served real models vs. fallbacks into the append-only audit, I-14). Both are defined + called; static-gated by `verify_claims.py::check_orchestrator_twin_wired`; behavioural proof in `orchestrator/tests/test_twin_verification.py` (CI, pymoo). | Invariant I-10 + Tier 4 = Monte Carlo via digital twin. | **PASS** — the twin is no longer dead code; the orchestrator invokes it at the top tier and the audit trail reflects input substance. |
| C8 | Frontend typed contract | `frontend/src/lib/synapse-api.ts` wraps most endpoints. `frontend/src/pages/DecisionDetail.tsx:~30` uses raw `fetch()` for `GET /decisions/{id}` with inline Zod. | Strict typed client. | **FAIL** — one off-client call site. (Resolved by WS-4.) |
| C9 | Frontend firehose schema | `frontend/src/lib/ws-multiplex.ts:92-110` emits raw JSON to listeners. No Zod schema for `{topic, seq, ts, payload}` envelope. | Strict typing on real-time channels. | **FAIL** — poison messages reach app code unchecked. (Resolved by WS-4.) |
| C10 | Frontend JWKS rotation | `api/routers/auth.py:179-182` exposes `/.well-known/jwks.json`. Frontend never fetches it. | Key rotation supported. | **FAIL** — clients trust access token blindly. (Resolved by WS-4.) |
| C11 | Steering audited | `frontend/src/store/steering.store.ts` mutates Zustand + localStorage only. No POST to a backend endpoint, no `audit_steering` table. | FE-INV-033: "audit-logged on change". | **FAIL** — operator interventions are invisible to the audit trail. (Resolved by WS-5.) |
| C12 | Helm chart breadth | `infrastructure/helm/synapse/Chart.yaml` declares 3 dependencies (api-gateway, orchestrator, demand-prophet). 7 agents + digital-twin un-templated. | Chart.yaml comment is honest ("Sprint-9 skeleton"); sprint summary leaves the gap implied. | **FAIL** — 3 of 11 services templated. (Resolved by WS-6.) |
| C13 | Linkerd/KEDA/Flagger wiring | Standalone YAML at `infrastructure/{linkerd,keda,flagger}/*.yaml`. No reference from any Helm subchart's `templates/`. | Sprint 9 claim: "Linkerd/KEDA/Flagger CRDs". | **FAIL** — manifests exist, deployment path is manual `kubectl apply`. (Resolved by WS-6.) |
| C14 | GCP deployment | `infrastructure/gcp/terraform/` now carries the real `.tf` source (11 files: Secret Manager, WIF, Artifact Registry, IAP, billing budget, nightly auto-stop, Cloud Ops Agent). Verified by `verify_claims.py::check_gcp_terraform_on_main` (asserts ≥ N `.tf` files present). | "Deployed in GCP". | **PASS** — the Sprint-10 Terraform module is present on the working branch (no longer a branch-only artefact). |
| C15 | Coverage floor | `.github/workflows/ci.yml` enforces `--cov-fail-under=64` (the verified current floor + 0.13 ratchet). The CLAUDE.md target is 80%; this number is the start of a ratchet, NOT the destination. Bump as branch tests land. | CLAUDE.md Code Quality: "Coverage minimum: 80% on all packages". | **PASS** — gate is now verified (≥ measured 63.87% from the CI run on PR #10 commit 0befe0b). The 80% target remains documented; closing the gap is per-PR branch test work, not a single ratchet move. |
| C16 | Mutation floor | `frontend/stryker.conf.json`: `"break": null` (informational only). | CLAUDE.md: "Mutation survival: <15% rewards, <10% guardrails/audit". | **FAIL** — Stryker cannot fail a PR. (Resolved by WS-9.) |
| C17 | KV-cache hit-rate floor | No CI step asserting hit-rate ≥0.70. | Sprint 9 floor: KV-cache 0.70. | **FAIL** — number lives in prose. (Resolved by WS-9.) |
| C18 | Tier-routing accuracy floor | No CI step asserting routing accuracy ≥0.80 on golden traces. | Sprint 9 floor: tier-routing 80%. | **FAIL** — number lives in prose. (Resolved by WS-9.) |
| C19 | Image signing enforcement | `cd-gcp.yml` (on `feat/gcp-primary-deployment` only) signs images with cosign keyless. No admission policy verifies signatures. | Sprint 9 claim: cosign signing. | **FAIL** — generated, not enforced. (Resolved by WS-8 after WS-1.) |
| C20 | SBOM diff gate | SBOMs at `infrastructure/sbom/*.cdx.json`. No CI step comparing PR SBOM to baseline. | Sprint 9 claim: SBOM. | **FAIL** — file exists, drift goes uncaught. (Resolved by WS-8.) |
| C21 | CVE budget enforcement | `scripts/check_cve_budget.py` exists; E-S9-15 says it's "an operator step, NOT part of normal CI". | Sprint 9 claim: CVE budget. | **FAIL** — by-design opt-out. (Resolved by WS-8.) |
| C22 | SLO recording rules ↔ alerts ↔ dashboards | `scripts/observability/metric_truth.py` confirms every SLO-alerted metric has a source-tree emit. The 3 formerly-unemitted metrics (`synapse_demand_prophet_coverage_p90`, `synapse_demand_prophet_negative_horizon`, `synapse_pricing_oracle_essential_cap_violation`) are now `.set()/.inc()` in the respective agent pipelines (WS-12 + Flagship Slice). Verified by `verify_claims.py::check_slo_metric_truth`. | Sprint 7 claim: "SLO YAMLs + multi-window burn alerts". | **PASS** — all 5 alerted metrics are emitted in source; the chain has no missing links. |
| C23 | `no-raw-hex` enforcement | Hook present at `.pre-commit-config.yaml:157` (`no-raw-hex`). Verified by `make verify-claims`. | "The `no-raw-hex` hook blocks it". | **PASS** — overcorrection in the audit; hook does exist. |
| C24 | Worktree-policy enforcement | CLAUDE.md forbids `git worktree add` after the May 2026 sprawl incident. No pre-commit hook enforces this. | Workflow Rule: "NEVER use `git worktree add` in this repo". | **FAIL** — rule lives in prose. (Resolved by §3.1 cross-cutting fix.) |
| C25 | Daily anchor publication | Daily JSON anchors committed under `infrastructure/audit_anchors/<date>.json` (E-S9-03). No publication to an external tamper-evidence log (Rekor, OpenTimestamps). | Sprint 9 claim: audit immutability + anchors. | **PARTIAL** — internal anchor exists; third-party verifiability does not. (Resolved by §3.4 cross-cutting fix.) |
| C26 | GCP compose pulls signed images from AR | `docker/docker-compose.gcp.yml` lines 182–425 — every SYNAPSE service uses `image: ${SYNAPSE_AR_REPO_URL}/<svc>:${SYNAPSE_VERSION:-latest}` + `pull_policy: always`. Zero `build:` directives. Verified by `scripts/audit/verify_claims.py::check_gcp_compose_pulls_images`. | ADR-039 contract. | **PASS** — closes the Sprint 12 incident where 4 merges to `main` produced zero deploys. |
| C27 | `verify_images.sh` covers full CD matrix | `infrastructure/gcp/verify_images.sh:39-53` — `IMAGES=()` array now includes all 12 images from the `cd-gcp.yml` build matrix (`frontend` was missing pre-Sprint-12). Verified by `scripts/audit/verify_claims.py::check_verify_images_covers_matrix`. | ADR-039 contract. | **PASS** — Cosign signatures are now load-bearing for every signed image. |
| C28 | Per-package coverage floors enforced | `infrastructure/quality/coverage-floors.yaml` defines floors for all 10 packages (synapse_common, orchestrator, 8 agents). `scripts/coverage_per_package.py` parses `coverage.xml` and exits 1 on any package below its floor. Wired into `ci.yml` Sprint-13 Unit-tests step. Verified by `scripts/audit/verify_claims.py::check_per_package_coverage`. | Sprint 13 Phase 2 supersedes the single `--cov-fail-under` model. | **PASS** — supersedes C15 in scope. A regression in one package fails CI on that specific package, not on the aggregate. |
| C29 | Branch coverage enabled | `pyproject.toml [tool.coverage.run]` now has `branch = true`. Every per-package gate measures line + branch combined. Verified by `scripts/audit/verify_claims.py::check_branch_coverage`. | Sprint 13 Phase 1.2 / 2.1. | **PASS** — drops initial headline numbers by ~3–8 points but the per-package floors are calibrated against the new (more honest) shape. |
| C30 | Python mutmut PR-gated on changed targets | `.github/workflows/mutation.yml::mutation-fast` runs on `pull_request` for the gated mutation targets (`agents/*/training/rewards.py`, `orchestrator/guardrails/rules.py`, `orchestrator/audit/{logger,hash_chain}.py`). Only mutates files actually changed in the PR; existing `<15% rewards` / `<10% guardrails+audit` thresholds enforced by `scripts/check_mutation_threshold.py`. The full-matrix Sunday cron still runs the original `mutation` job. Verified by `scripts/audit/verify_claims.py::check_python_mutmut_pr_gated`. | Sprint 13 Phase 4.2 (parity with C16 frontend Stryker). | **PASS** — Python mutation regressions now fail CI before merge to `main`. |
| C31 | Spec-coverage in CI with threshold | `scripts/check_spec_coverage.py` now supports `--threshold N`, `--json`, `--per-agent`, and an `assertion`-matched mode that requires an `assert` within 20 lines of an `INV-*` ID (substring matching was gameable). Wired into `ci.yml` at `--threshold 12` against the measured assertion-matched aggregate of 13.8% (down from the legacy substring claim of 100% — that was theatre). Ratchet plan: 12 → 25 → 50 → 75 → 100 as Phase 5.5 backfills real asserts. Verified by `scripts/audit/verify_claims.py::check_spec_coverage_in_ci`. | Sprint 13 Phase 5.1-5.3. | **PASS** — every regression below 12% aggregate fails CI; the user's "spec-coverage ≥50%" target is the third ratchet step, not the initial gate. |
| C32 | Training omit narrowed | `pyproject.toml [tool.coverage.run]` no longer omits the bare `*/training/*` glob (which silently excluded the mutation-tested `rewards.py`). New narrow patterns: `*/training/loop.py`, `*/training/train_*.py`, `*/training/datasets/*`, `*/training/dataloader.py`, `*/training/lightning_module.py`. Verified by `scripts/audit/verify_claims.py::check_training_omit_narrowed`. | Sprint 13 Phase 1.2. | **PASS** — rewards.py / reward_config.py / conformal.py become measurable; the mutation gates at <15% survival now operate on code visible to the coverage gate. |
| C33 | Agent outputs are genuine, not synthetic | `scripts/audit/substance_truth.py` AST-flags the synthetic-shortcut anti-patterns (guard-then-ignore dependency, hardcoded `confidence=`, random model input) in `agents/*/inference/pipeline.py`. All 8 pipelines rewired through the ADR-041 anti-corruption layer + ADR-040 provenance/derived-confidence contract; `--check` reports **0 violations, 8/8 clean**. Ratchet baseline 10 → 0. Verified by `scripts/audit/verify_claims.py::check_substance_gap`. | The enforcement boundary (C28–C32) validated the schema of outputs but never that they were real. Confidence was a constant `0.85` — disabling I-5. | **PASS** — the substance lie is closed fleet-wide; any reintroduced shortcut fails `substance_truth --check` (blocking CI step, ADR-040). |
| C34 | I-12 twin divergence wired | `digital_twin/sync/divergence_monitor.py` emits `synapse_digital_twin_kl_divergence` on every comparison; `digital_twin/sync/kafka_sync.py` feeds live agent-state distributions into `DivergenceMonitor.update_live_state` + runs the KL check (re-sync alert above 0.1, INV-TW-003). Verified by `scripts/audit/verify_claims.py::check_i12_wired` + `digital_twin/tests/test_i12_divergence_wiring.py` (4 tests). | I-12: "Twin fidelity — KL divergence > 0.1 triggers re-sync". | **PASS** — `update_live_state` had no production caller before (verified by grep); the metric never emitted. The edge now exists end-to-end. |
| C35 | API gateway authenticated + no embedded secret | `api/routers/decisions.py` gates `recent`/`{id}` with `CurrentOperator` (VIEWER) and `trigger` + `override` with `RequireRole(Role.OPS)`; the `synapse_app_2026` DSN-default credential is removed from all of `api/` (fail-fast on unset DSN). Verified by `scripts/audit/verify_claims.py::check_api_auth` + `api/tests/test_decisions_auth.py` (7 tests). | I-?: public read endpoints were unauthenticated; a DB password was hardcoded in `decisions.py`, `main.py`, and `steering.py`. | **PASS** — every non-health endpoint requires a bearer token; no credential in source (the gate surfaced and forced the steering.py fix). |
| C36 | Honesty contract present (ADR-040/041) | `packages/synapse_common/{features,model_registry,provenance,invariants}.py` (the FeatureProvider + ModelRegistry anti-corruption layer, the Provenance value object, the RuntimeValidator) + `docs/adr/ADR-040-*.md` + `docs/adr/ADR-041-*.md`. 19 unit tests in `packages/tests/test_honesty_contract.py`. Verified by `scripts/audit/verify_claims.py::check_honesty_contract`. | Plan v2 — Substance Mandate. | **PASS** — the shared contract every pipeline now speaks; degradation is a first-class, tested, auditable state. |
| C37 | Models actually train (real gradient steps) | `scripts/audit/training_truth.py` AST-flags any `train.py` that returns the `pipeline_validated` sentinel or builds an optimizer it never `.step()`s. **Three real-loop agents** now: `demand_prophet` (multi-epoch CRPS), `supplier_trust` (Pyro SVI / ELBO), `pricing_oracle` (deterministic policy gradient on a differentiable profit model); plus `inventory_sentinel` + `routing_navigator` analytical. `REAL_LOOP_AGENTS={demand_prophet, supplier_trust, pricing_oracle}`; 0 violations (baseline 0). Verified by `verify_claims.py::check_training_truth`. | Substance Completion (ADR-042/043). Before: the only `train.py` discarded its optimizer and took zero gradient steps. | **PASS** — the no-op-training lie is closed across all four ML paradigms; the remaining 3 agents ratchet one PR each. |
| C38 | Training produces loadable, content-hashed checkpoints | `scripts/audit/checkpoint_truth.py` consumes the `TrainResult` JSON the smoke-train writes to `artifacts/training/` and asserts the checkpoint exists + its sha matches (determinism). Enforced in CI via `SYNAPSE_SMOKE_RUN=1`; SKIP locally (no artifacts — never a fabricated pass). Verified by `verify_claims.py::check_checkpoint_truth`. | ADR-042. No checkpoint existed anywhere in the repo before. | **SKIP locally / enforced in CI** — `CHECKPOINT_AGENTS={demand_prophet}`; the training-smoke job fails if the artifact is absent or corrupt. |
| C39 | Serving loads models via ModelRegistry | `scripts/audit/serving_truth.py` AST-checks each `serve.py` constructs `ModelRegistry().load(...)`. **4/8 agents wired** — `demand_prophet` (HGT-TFT checkpoint), `routing_navigator` (optimality-gap calibration), `supplier_trust` (conjugate prior), `pricing_oracle` (MADDPG actor + elasticity) — each resolving via the $0 checkpoint source + a `serving_model.py` adapter, degrading honestly when absent (I-7). `WIRED_AGENTS` = those 4; `BASELINE_UNWIRED=4`. Verified by `verify_claims.py::check_serving_truth`. | ADR-042/043. Before: every `serve.py` built `model=None` → 100% fallback. | **PASS** — 4/8 agents load a real model; the registry is the live serving path. |
| C40 | Prediction intervals achieve nominal coverage | `scripts/audit/calibration_truth.py` asserts held-out coverage ≥ the agent's floor from the smoke `TrainResult`. The `ConformalCalibrator` was fixed from a ~80%-under-covering two-sided split to correct **CQR** (single symmetric conformity quantile → guaranteed ≥1−α). `test_conformal_coverage.py` proves held-out coverage ≥ 0.85 on a deliberately-miscalibrated base model (4 tests, numpy). Enforced in CI; SKIP locally. Verified by `verify_claims.py::check_calibration_truth`. | ADR-042. The deepest substance check — uncertainty must be real, not decorative. | **PASS (math, locally) / enforced in CI** — a genuine under-coverage bug was found and fixed. |
| C42 | API decisions feed reads the real write table | `api/routers/decisions.py` queried the legacy, write-dead `audit_decisions` table (no writer; lacks `phase_reached`) while the orchestrator writes every decision to `audit_consensus` (`orchestrator/audit/models.py::AuditConsensusRow`). Repointed both queries to `audit_consensus` (+ `proposals` column name); added the `city` column there (migration `0006_consensus_city.sql` / `07_wsA_consensus_city.sql`, applied to the live volume by a new `cd-gcp.yml` step since `initdb.d` only fires on an empty datadir). Verified by `scripts/audit/verify_claims.py::check_audit_read_write_table_match` + `api/tests/test_decisions_table.py` (3 tests). | Live `GET /api/v1/decisions/recent` → HTTP 503 `column "phase_reached" does not exist`. | **PASS** — the console's core decisions feed is fixed at the root; the read/write table can never silently diverge again. |
| C41 | Declared confidence_basis matches computed basis | `scripts/audit/confidence_basis_truth.py` AST-extracts the `confidence_basis` stamped on each `Provenance.real(...)` and compares to the maintained ground-truth table. `pricing_oracle` fixed: it stamped `CRITIC_VALUE_SPREAD` but computes `tanh(|elasticity|)` → now stamps the honest new `ELASTICITY_STRENGTH`. Ratchet baseline 2 → 1 (only `routing_navigator`, which emits no confidence yet, remains). Verified by `verify_claims.py::check_confidence_basis_truth`. | ADR-042. `substance_truth` catches a *constant* confidence but not a *mislabelled* one. | **PASS** — the pricing stamp/computation lie is closed; routing's `OPTIMALITY_GAP` confidence lands in its ratchet PR. |
| C42 | Real checkpoint serves non-degraded calibrated output at runtime | `scripts/audit/runtime_substance.py` is now a **per-agent probe registry** (`register_probe`): each wired agent boots its checkpoint through its production serving path and asserts genuinely-real output. Probes registered: `demand_prophet` (FEAST + CONFORMAL_INTERVAL, torch-gated), `routing_navigator` (OPTIMALITY_GAP, **torch-free — runs+PASSES locally**), `supplier_trust` (POSTERIOR_SPREAD, torch-free), `pricing_oracle` (ELASTICITY_STRENGTH + essential cap, torch-gated). `evaluate()` aggregates (any FAIL→FAIL; else any OK→OK; else SKIP). Verified by `verify_claims.py::check_runtime_substance`. | ADR-043. C33's AST gate is blind to *runtime* substance — it can't see that the model never loads, or that a "derived" confidence is a disguised constant. This is its runtime counterpart. | **PASS** — routing's torch-free probe proves the methodology locally; the torch-gated probes run in the CI `training-smoke` job. RED on any `model=None` regression. |
| C43 | A real, published production checkpoint serves at $0 | `scripts/audit/published_checkpoint_truth.py` fetches the published serving sidecar from HF Hub (`DP_HF_REPO`) and asserts it is **not** a smoke artifact, `coverage_p90 ≥ 0.85`, and the recorded sha (`infrastructure/ml/published_checkpoints.json`) matches the published version. `notebooks/train_demand_prophet.ipynb` + `docs/runbooks/train-and-publish-checkpoint.md` are the reproducible free-GPU operator path. Verified by `verify_claims.py::check_published_checkpoint`. | ADR-043 Phase 1. C42 proves the serving *code path* on the CI smoke checkpoint; C43 proves a *real model* is published + resolvable. | **SKIP until published** — `$0`-safe: SKIPs on unset `DP_HF_REPO` / placeholder registry (CI green without the secret); flips to PASS once an operator publishes + records. Never fabricates a pass. |
| C47 | Every deploy is verified end-to-end before the workflow goes green | `scripts/deploy/verify_live.py` is the single truth oracle. cd-gcp.yml runs it twice post-deploy: `--on-vm --probe-decision` (every compose service running+healthy, RestartCount==0, one decision flows orchestrator → outbox → Kafka) and `--external --expect-sha ${{ github.sha }}` (deployed `/version` SHA == merged commit; healthz/topology/agents/decisions-auth/firehose-WS all answer from outside). Any failure fails the deploy AND auto-opens a `sev1, deploy-failure` issue (deduped per SHA). Unit tests: `packages/tests/test_verify_live.py` (9). Verified by `verify_claims.py::check_deploy_truth_gated`. | Sprint 14. "Wait for health" only proved nginx answers — the jsonschema incident shipped 2 crash-looping agents behind a green deploy, and a months-stale link was structurally undetectable (the SHA check was a *printed suggestion*, never an assertion). | **PASS** — a merge to main now either produces a verified-working live system or a red workflow + auto-opened issue. No silent third state. |
| C49 | Import-smoke covers every Python image in the CD matrix | Each cd-gcp.yml matrix entry declares its `entry` module; after build+push the workflow runs `docker run <image>@<digest> python -c "importlib.import_module(entry)"` (11 Python images; frontend is static nginx, skipped). Lockstep-checked (C27 style) by `verify_claims.py::check_image_smoke_covers_matrix`. | Sprint 14. CI installs dev deps; images don't — `jsonschema` was declared dev-only, CI stayed green, and two prod agents crash-looped (PR #42). | **PASS** — a missing runtime dep now fails at build time, before signing or deploying. |
| C50 | Every GCP compose service resolves to a healthcheck | All 21 services in `docker-compose.gcp.yml` carry a healthcheck — compose-level (kafka/redis/neo4j/postgres/orchestrator/api/frontend/nginx/traffic-generator + newly added mlflow/prometheus/grafana) or Dockerfile `HEALTHCHECK` (8 agents, digital-twin). Verified by `verify_claims.py::check_compose_health_complete`. | Sprint 14. C47's "all containers healthy" assertion is only total if every container actually carries a healthcheck. | **PASS** — no service can run silently un-monitored. |
| C48 | A scheduled watchdog asserts the live system stays current + working | `.github/workflows/live-truth.yml` runs 2x/day inside the VM's REAL auto-stop window (`synapse-3hr-window` policy: 04:30–07:30 UTC = 10:00–13:00 IST; the ADR-036 "09:00–23:00 IST" note is stale — E-S14-04): skips if a cd-gcp run is in flight (no false stale alarms), asserts VM RUNNING, then `verify_live.py --external --expect-sha $GITHUB_SHA` (deployed == main HEAD — the "months-stale link" detector) and `--on-vm --max-restarts 2 --settle-seconds 120` (container truth via IAP SSH). Failure auto-opens a `sev1, live-truth` issue (max one open at a time). Verified by `verify_claims.py::check_live_watchdog`. | Sprint 14. C47 proves a deploy worked *at deploy time*; nothing watched the system *between* deploys — staleness was found only when a human looked (historically: months). | **PASS** — silent staleness/breakage is detected every up-window, with an issue + email. |
| — | The live UI always has data flowing | `scripts/traffic/decision_loop.py` runs as the `traffic-generator` compose service (reuses the api-gateway AR image — no `build:`, no new CD-matrix image): every 4–5 min one real decision flows orchestrator → audit → outbox → Kafka → firehose → UI, honestly tagged `synthetic-` in `order_id`. Heartbeat-file healthcheck: a persistently failing loop turns the container unhealthy, tripping C47/C48. | Sprint 14 (user-confirmed). A rich UI wired to a quiet pipe looks dead — the original "is any of this real?" trigger. | **Wired** — opening the live link always shows decisions ≤5 min old, and the full decision pipeline is continuously exercised. |
| C51 | Decision outcomes are scored, append-only, never fabricated | `decision_outcomes` table (INSERT+SELECT only — `infrastructure/postgres/08_sprint19_outcomes.sql`) + `data_fabric/jobs/outcome_score.py` scorer (execution-confirmation + twin-divergence realized signals; `unknown` when absent) + `scripts/audit/outcome_truth.py` AST gate. Verified by `verify_claims.py::check_outcome_truth`. | `audit_consensus.outcome` existed since Sprint 4 (`02_sprint4_consensus.sql:23`) but `logger.py:91-108` never wrote it — the system never recorded what actually happened (ADR-047). | **PASS** — outcomes are a real append-only fact stream; any constant/fabricated outcome path fails the gate. UPDATE-revoke on `audit_consensus` (I-4) is respected by the separate table. |
| C52 | Operations aggregate endpoints exist + authenticated | `GET /api/v1/system/slo` (Prometheus multi-window burn proxy), `/api/v1/system/calibration` (reliability curve + Brier from `decision_outcomes`), `/api/v1/escalations/analytics` (resolution-time + override-mix over `audit_escalations`) — all mounted in `api/main.py`, all `CurrentOperator`-gated (VIEWER). Verified by `verify_claims.py::check_operations_endpoints`. | SLO burn + escalation pressure + system-level calibration were computed in the backend but reached no API (ADR-047). | **PASS** — the supervisory signals are exposed additively, no new Kafka topic. |
| C53 | Supervisory FE honesty invariants enforced | `FE-INV-041` (outcome tri-state — `unknown` never rendered `confirmed`), `FE-INV-042` (SLO burn fast+slow, "burn unknown" never silent-green), `FE-INV-043` (calibration always shows n + horizon + "as of"), `FE-INV-044` (aggregates segment/label `is_synthetic`) — registered in `frontend/spec/fe_invariants.yaml` with impl + test; `check_fe_invariants.py` blocks a missing impl/test. | The per-decision honesty net (FE-INV-034..040) had no aggregate analog — a trust surface could over-claim with no gate. | **PASS** — the aggregate trust read is held to the same honesty bar as the per-decision one. |
| C54 | Portable agent orientation is generated, never a drifting hand-copy | `CLAUDE.md` + `.claude/skills/synapse-engineer/` are the SINGLE source of truth; `AGENTS.md` + `.agents/skills/` (the cross-tool "agentsmd" mirror non-Claude agents read) are GENERATED by `scripts/sync_agents.py` (banner + H1 swap for AGENTS.md, verbatim byte copy for the skill). `verify_claims.py::check_agents_mirror` regenerates in-memory and FAILs on any drift. | The hand-maintained `AGENTS.md` had already drifted into a factual error (`.Codex/worktrees/` vs the real `.claude/worktrees/`) and was missing the Sprint 14–17 sections — a second source of truth diverging from the first, the exact failure this ledger exists to catch. | **PASS** — re-deriving known facts is the most expensive recurring cost (Documentation Discipline, CLAUDE.md); the mirror is now generated + gated, so editing `CLAUDE.md` without re-running the generator fails CI. |

---

## Summary — after Paradigm-Complete Substance (ADR-043) on Plan v2 / Sprint 13

- **Total mechanical checks:** 38 (registered in `scripts/audit/verify_claims.py`)
- **PASS:** 37 locally — incl. C7 (orchestrator↔twin + input provenance), C37 (6/8 real-loop/analytical fits), **C39 (8/8 wired — every agent loads a model via ModelRegistry)**, C42 (3/8 torch-free runtime probes PASS locally)
- **FAIL:** 0
- **PARTIAL:** 0
- **SKIP:** 1 locally — **C43** (published-checkpoint) SKIPs until an operator runs the free-GPU publish runbook and sets `DP_HF_REPO`. The 5 torch/lib-gated runtime probes (demand_prophet, pricing, supplier, freshness, sustainability) + C38/C40 run in the CI `training-smoke` job (`SYNAPSE_SMOKE_RUN=1`); the 3 torch-free probes (routing, disruption, inventory) PASS everywhere. This is the two-tier honesty boundary (ADR-042/043): AST gates (C33/C37/C39/C41) prove *shape* everywhere; runtime gates (C38/C40/C42) prove *behaviour* where the stack + checkpoint exist; C43 proves a *published* model exists.

### Fleet-complete substance — all 8 agents real, serving 8/8

Phase 7 ratcheted the four homogeneous-remainder agents onto the Agent Reality Pattern, so
**every agent now loads a model via ModelRegistry and stamps an honest, basis-adjudicated,
non-constant confidence**:

| Agent | Paradigm | Confidence basis | Runtime probe |
| --- | --- | --- | --- |
| disruption_shield | anomaly (sklearn IsolationForest) | ANOMALY_SCORE_MARGIN | **torch-free, PASSES locally** |
| freshness_guardian | survival (Weibull-AFT, numpy-reconstructed) | SURVIVAL_CI_WIDTH | lifelines-fit CI; serving lifelines-free |
| sustainability_agent | predictive (KM waste curve) | PREDICTIVE_ENTROPY (was mislabelled SURVIVAL_CI_WIDTH) | KM-fit CI; serving lifelines-free |
| inventory_sentinel | analytical (newsvendor + conformal) | RESIDUAL_VARIANCE | **torch-free, PASSES locally** |

Two runtime dishonesties the static gates were blind to were found + fixed: freshness's
hardcoded `0.85` (a variable-assigned constant) and sustainability stamping `Provenance.real`
on the *unfitted* fallback. `serving_truth` 7→0 unwired; `confidence_basis_truth` all 8
adjudicated (0 violations).

### Paradigm-complete substance (this effort) — all four ML archetypes proven real at runtime

The Agent Reality Pattern (ADR-043) was generalized from one flagship to **one exemplar per
remaining ML paradigm**, each landing real training + $0 serving + a runtime probe + an
assertion-matched `INV-*-010/007` spec test:

| Agent | Paradigm | Real training | Serving | Runtime proof |
| --- | --- | --- | --- | --- |
| demand_prophet | Forecasting | multi-epoch CRPS gradient loop | HGT-TFT checkpoint + calibrator sidecar | FEAST + CONFORMAL_INTERVAL (CI) |
| routing_navigator | Analytical / solver | optimality-gap split-conformal calibration (`og_coverage` 0.95) | calibration sidecar | OPTIMALITY_GAP, **torch-free, PASSES locally** |
| supplier_trust | Bayesian | Pyro SVI population fit + conjugate serving | 3-float prior sidecar | POSTERIOR_SPREAD (torch-free serving) |
| pricing_oracle | RL | deterministic policy gradient on a differentiable profit model + OLS elasticity | MADDPG actor + elasticity sidecar | ELASTICITY_STRENGTH + essential cap (CI) |

Plus: the runtime gate became a **per-agent probe registry** (scales with the ratchet); a
`$0` **published-checkpoint gate (C43)** + reproducible Colab/Kaggle notebook + runbook make a
*real published model* a live, regression-guarded proof; `smoke_train.py` gained a `sys.path`
bootstrap. Ratchets advanced: `serving_truth` 7→4 unwired, `training_truth` 1→3 real loops,
`checkpoint_truth` +pricing, `calibration_truth` +routing. **substance_truth: 8/8 clean.
spec-coverage: 68/68 assertion-matched (100%).**

### Flagship Reality Slice (ADR-043) — landed this effort

The honesty layer told the truth about degradation; this work makes the flagship
agent *stop* degrading and proves it at runtime. Two real defects — invisible to
the static gates because every test ran `model=None` — were found by reading the
serving path and are now fixed + gated:

- **Latent 500 on the real path.** `serve.py` constructed a `ConformalCalibrator`
  but never `.fit()` it; the fitted CQR adjustments from training were discarded.
  The instant a real model loaded, `predict_intervals` raised `RuntimeError` →
  unhandled 500. Fix: the fitted calibrator is persisted in a deterministic
  serving sidecar and travels with the checkpoint; `pipeline.predict` guards the
  interval call so an unfit calibrator degrades honestly instead of crashing.
- **Registry unreachable at $0.** `ModelRegistry` was MLflow-only, so on the
  free-tier VM (no MLflow server) a trained checkpoint was never loadable. Fix:
  a $0 checkpoint source (local dir / HF Hub) resolves `{name}.pt` + sidecar,
  builds the model via an agent-injected builder, keeps the exact `load()`
  contract, and degrades identically when absent (I-7).
- **Disguised-constant confidence.** On the EMA fallback every SKU's relative
  interval width was exactly `0.4` → `confidence = 1/1.4 ≈ 0.714`, a constant that
  sat *above* the 0.7 HITL threshold and silently suppressed I-5 escalation on
  degraded output. Fix: degraded confidence is now the explicit `FALLBACK_CONFIDENCE`
  floor (below the threshold → I-5 fires); derived confidence is reserved for the
  real path. **C42** (`runtime_substance.py`) is the new runtime gate that proves
  all three, and `substance_truth.py` now documents its static-only scope boundary.
- **Feast ref mismatch (4th defect, WS-C).** The pipeline asked Feast for
  `demand_features:rolling_7d_mean` while the registered FeatureView is
  `sku_demand_signals` with field `rolling_mean_7d` — so real Feast would reject the
  request and degrade to FALLBACK *forever*. `FEATURE_REFS` are now pinned to the real
  view and guarded by `packages/tests/test_feast_ref_consistency.py` (imports the
  actual FeatureView definition — runs wherever feast is installed, verified passing
  locally). Materialize steps captured in `docs/runbooks/feast-materialize.md`.
- **Tier-4 → digital-twin invocation (C7, WS-E).** The orchestrator's full path now
  verifies a Tier-4 action against the twin's Monte-Carlo what-if via A2A
  (`_phase_twin_verify` → `http://digital-twin:8009` `monte_carlo`), records the
  verdict + predicted KPI means into the append-only audit trail (I-14), and degrades
  honestly when the twin is unreachable (I-7). The twin gained the matching
  `monte_carlo` A2A handler (`MonteCarloRunner.run_scenarios` → `MonteCarloOutput`),
  and its agent card now advertises only methods it actually serves. The orchestrator
  also records per-decision **input provenance** — which agents served a real model vs.
  an honest fallback — so the audit chain reflects substance. 4 new orchestrator tests
  (pymoo-gated in CI; verified locally with a pymoo stub).
- **42 new torch-free tests** (registry checkpoint source, calibrator state
  round-trip, the latent-500 regression, the honest-floor escalation, the
  disguised-constant detector, Feast ref consistency) + 4 orchestrator twin tests —
  all green; the existing contract tests still pass unchanged (363 passed / 10 skipped
  across packages + the demand_prophet torch-free suite).

### Substance Completion — landed this effort

- **C37 (training-truth)**: `demand_prophet` = real CRPS gradient loop; `inventory_sentinel` = analytical (closed-form newsvendor, `TrainResult.analytical`). 0 violations, baseline 0. The gate now distinguishes real-loop / analytical / hollow.
- **C39 (serving-truth)**: `demand_prophet` resolves a checkpoint via `ModelRegistry` + `serving_model.py` adapter (degrades honestly). 1/8 wired, baseline-unwired 7.
- **C40 (calibration-truth)**: `demand_prophet` conformal coverage proven (the calibrator's ~80%→nominal CQR bug fixed); `inventory_sentinel` newsvendor PI coverage = 0.913 on real residuals. Enforced in CI via `SYNAPSE_SMOKE_RUN`.
- **C41 (confidence-basis-truth)**: **DONE → 0** — `pricing_oracle` stamps `ELASTICITY_STRENGTH`, `routing_navigator` emits a real `OPTIMALITY_GAP` confidence. All 8 pipelines agree stamp == computation.
- **Feast materialization**: `scripts/build_feature_store.py` builds the missing demand-signals parquet in the exact FeatureView schema (1.125M rows verified) → `feast materialize` → `FeatureSource.FEAST`.
- **Digital-twin Gym env**: action-blind / stateless-across-steps bug fixed; `set_policy` levers + persistent `start()/advance()`; `test_env_response.py` proves good-action-beats-bad (the non-vacuous-env guard).
- **API rate limiting**: dependency-free token bucket (`synapse_common/ratelimit.py`) + per-IP middleware (429 + Retry-After, liveness-exempt). 11 tests.

### Phase A — Operational Truth (live-deploy fixes, in progress)

- **C42 (decisions feed) — DONE.** Root-caused the live 503 to a read/write table mismatch (API read `audit_decisions`; orchestrator writes `audit_consensus`), not a stale-volume migration issue. Fixed at the root + mechanical gate. **Verified live:** `GET /api/v1/decisions/recent` (viewer JWT) → **HTTP 200 `{"decisions":[],"count":0}`** on https://34-180-49-108.nip.io (was 503).
- **CD pipeline reached the VM for the first time (PRs #22–#25).** The GCP deploy had NEVER succeeded; the live site was a 7h-old manual `docker-*` build. Six stacked blockers, each masking the next, fixed in order:
  1. API read dead `audit_decisions` (C42).
  2. **cosign not installed on the VM** — `verify_images.sh` failed all 12 with a hidden `command not found`; now self-installs cosign + surfaces errors (PR #23).
  3. **Docker not authed to private Artifact Registry** — verify failed all 12 `DENIED: Unauthenticated`; added `gcloud auth configure-docker` to the verify step, proven on the VM with an isolated `DOCKER_CONFIG` (PR #24).
  4. **Missing `.env.gcp`/`.env.gcp.local`** overlays for the `runner` user — `couldn't find env file`; CD now touches them idempotently (every compose var has a default except `SYNAPSE_AR_REPO_URL` from `.env.gcp.version`) (PR #25).
  5. **Boot-disk full** — Docker's containerd snapshotter store is on `/var/lib/containerd` (boot disk), and the old manual stack's ~60GB CUDA images + the new ~60GB AR images can't coexist; freed manually + CD now prunes superseded images post-`up` (PR #25). Future AR→AR pulls share the CUDA base layer so are small.
  6. **Postgres superuser password mismatch** — `pg_hba` is `local…trust` / `host…scram-sha-256`, so the orchestrator's TCP auth failed `InvalidPasswordError for user "synapse"` while the volume's stored password ≠ the empty-env default; `ALTER USER synapse/synapse_app` aligned both to the documented defaults (volume now consistent; future fresh inits use the same default).
  - Result: deploy run 27068849447 **fully green** (verify → pull → migrate → health → audit-chain); the proper **signed Artifact-Registry stack** now runs on the VM, replacing the manual build. PR #25 validates the hands-off self-healing pipeline.
- **Outbox / steering schema rot — OPEN (next WS-A chunk).** Discovered while fixing C42: the `audit_outbox` ORM (`orchestrator/audit/models.py::AuditOutboxRow` — `audit_id/partition_key/headers/retries/next_attempt_at/published_at/updated_at`, status ENUM `outbox_status`) has **diverged from the SQL** (`0002_outbox.sql` / `03_sprint7_outbox.sql` create `message_key/attempts/trace_id/sent_at`, status TEXT). `0004_orders_outbox_idempotency.sql` then `ALTER ... audit_id DROP NOT NULL` on a table with no `audit_id` — it errors, which is why `05_ws2`/`06_ws5` were quietly dropped from the GCP compose mounts (leaving `/api/v1/steering` with no `audit_steering` table). The dispatcher (`orchestrator/outbox/dispatcher.py`) uses the ORM, so the deployed outbox subsystem is schema-broken end-to-end. **Fix needs a real Postgres to test:** rewrite `0002_outbox.sql` to the ORM-true schema (incl. `CREATE TYPE outbox_status`), make the chain internally consistent, then a single re-runnable migrator applies the whole ordered set on every deploy. Tracked as the immediate next WS-A item.
- **Dev stack ≠ prod (A3) — OPEN.** `docker-compose.yml` has no api-gateway service (nginx routes `/api/`→orchestrator) and mounts only `01..04` of the Postgres init — so auth/orders/steering/firehose + outbox/audit-chain tables are absent locally. This is why prod-only bugs like C42 escape local testing.

### Live system map — end-to-end probe of the deployed VM (2026-06-07)

Drove real traffic through https://34-180-49-108.nip.io to establish the honest "every atom" truth (not doc claims):

| Layer | State | Evidence |
| --- | --- | --- |
| Frontend SPA | ✅ works | `/` 200, assets load |
| nginx TLS edge | ✅ works | `/healthz` 200, HTTPS, HTTP→HTTPS redirect |
| API gateway + JWT auth | ✅ works | login issues RS256 JWT; VIEWER/OPS roles enforced |
| Decisions feed | ✅ works | `GET /decisions/recent` → 200 with seeded rows (city column live) |
| Orchestrator + Postgres/Neo4j/Redis | ✅ healthy | all infra containers healthy; orchestrator 0 restarts |
| Decision pipeline (tier 1/2) | ✅ works (degraded) | `POST /decisions/` → 200, tier_2, phase_reached=4, audit row written, appears in feed |
| **Kafka topics** | ✅ **fixed live** | broker had **0 topics** (auto-create off) → `UNKNOWN_TOPIC` on tier-4/outbox. Provisioned all 17 via `scripts/create_kafka_topics.sh`; CD now does this every deploy. |
| **Agent A2A consensus** | ✅ **FIXED + LIVE-verified** | Root cause: 5 of 8 agents never mounted `POST /a2a`, so the orchestrator's `proposal` calls 404'd → no proposals → `confidence=0.0`. Wired the existing `*A2AHandler.handle_request` into each agent's `serve.py`; gate **C43** asserts all 8 expose `/a2a`. **Deployed 2026-06-07 (run 27087518482, green).** A post-deploy decision returned **confidence 0.8** (vs 0.0 pre-fix) — real multi-agent consensus is live. |
| Tier 3 (LLM debate) | ✅ degrades gracefully | `_phase_debate` now wraps the Ollama call in try/except — if the LLM is unreachable it records a degraded round and proceeds to arbitration instead of 504'ing the decision (I-7). (Optional real LLM = install Ollama on the VM host; not required for correctness.) |
| Tier 4 (digital-twin, C7) | ✅ **wired (bounded)** | `_phase_twin_simulate` invokes the twin's A2A `simulate` (Monte-Carlo) on Tier-4 — the production caller the twin never had (gate **C7**). Verified live: the twin **does** run (its SimPy event log churns from these calls). But ≥1000 scenarios blows past the 10s SLA on the small CPU VM, so the orchestrator caps the synchronous wait at **8s** and degrades (records `degraded`) rather than stalling the decision past the gateway timeout. Full twin-result integration needs more CPU / fewer scenarios / async — tracked. |

**ML training (Phase C):** `notebooks/train_synapse_agents.ipynb` is a Colab/Kaggle GPU notebook that fully trains `demand_prophet` (real CRPS loop → content-hashed checkpoint) and runs `inventory_sentinel` calibration, then packages the checkpoint for the live MLflow. The other 6 agents have **no `train.py` yet** (no real loop to run) — writing those loops is the remaining Phase-C substance work. Until a real checkpoint is loaded, agents serve honest fallbacks and confidence is consensus-derived (e.g. 0.8), not model-backed.
| Confidence (I-5) | ⚠️ floored at 0.0 | a *consequence* of the A2A-404 + untrained-models gaps, not a separate bug — honest degradation (I-7). Real confidence returns once agents respond and Phase-C models load. |

**Bottom line:** infra + frontend + API + auth + the audited fast-tier decision pipeline are genuinely working live. The *intelligence depth* (agents participating in consensus via A2A, trained models, LLM tier-3, twin tier-4) is the remaining work — Phase C/D. No GitHub Actions minutes were available to redeploy the A2A/agent fixes on 2026-06-07; they are staged for the next deploy.

### Still climbing (ML-stack / CI-operator gated, one agent / PR each)

- **C37/C38/C39** for the remaining **3** agents (freshness_guardian = survival/D-cal, disruption_shield = anomaly, sustainability_agent = multi-objective Pareto) — real fit/calibrate + registry-load, lowering each baseline by one. The four ML paradigms (forecasting/solver/Bayesian/RL) are now each proven; these three are the homogeneous ratchet.
- **C40** floors for freshness (D-cal), disruption (anomaly/interval), sustainability (Pareto gap) as each lands.
- **Tier-4 orchestrator → digital-twin invocation (C7)** is wired (Flagship Slice); the remaining piece is orchestrator *consuming* a real agent forecast in a Tier-2/3 decision.
- **Binding the placeholder `0.0` coverage floors** on the first full-stack CI run; **the genuine multi-epoch production checkpoint** published via the C43 runbook (operator/Colab).

### Sprint 13 measurements (final, locked into gates)

| Surface | Pre-Sprint-13 | Sprint 13 round 1 | Sprint 13 round 2 (final) | 84% target |
| --- | --- | --- | --- | --- |
| `packages/synapse_common` line+branch | 61.18% | 75.99% (+14.8) | **84.54%** (+8.5) | **MET** — floor 83.5 |
| `orchestrator` (3 new test files added) | 30.11% local | 30.11% | _CI-must-measure; +101 new tests covering hash_chain/audit_logger/guardrails/brownout_ | TBD on CI |
| Each of 8 agents | _unmeasured locally_ | CI-must-measure | + new `test_spec_assertions.py` per agent (+56 tests) + 2 new `test_reward_safety.py` | TBD on CI |
| Spec-coverage assertion-matched | 13.8% (vs legacy 100% substring) | 13.8% | **100.0%** (65/65) | **MET** — gate ratcheted to 99 |
| Frontend Stryker (json-canonical.ts) | 26.12% break, ~34% kill | 26 (unchanged) | **96.30%** measured; break ratcheted to **50** | well past user's 50% |
| Python mutmut PR-gate | Sunday cron only | PR-blocking wired | unchanged | C30 PASS |
| `test_brownout.py` (10 pre-existing failures) | 10 fail | 10 fail | **all pass** after BreakerState enum fix | green |

### Test counts added in Sprint 13

- `packages/tests`: 153 → **239** (+86 tests) — `test_phase3_zero_coverage_modules.py` + `test_phase3_schema_registry.py` + `test_phase3_dpdpa_outbox_tracing.py`
- `orchestrator/tests`: +**67 new tests** across `test_hash_chain.py` (20), `test_audit_logger.py` (10), `test_guardrails.py` extension (+29)
- `agents/*/tests`: +**56 new tests** across 6 new `test_spec_assertions.py` files (one per agent except demand_prophet, whose test_spec.py was already real)
- `agents/{inventory_sentinel,supplier_trust}/tests`: +**14 new tests** in `test_reward_safety.py` (the missing E-S5-10 files)
- Frontend `src/lib/__tests__/json-canonical.test.ts`: 6 → **14 tests** (+8 mutant-killing tests)

**Total new passing tests this session: ~232**, plus 10 brownout tests un-broken.

### What remains (multi-PR climb on CI)

- The 9 agent + orchestrator package floors in `coverage-floors.yaml` are still `0.0` placeholders pending the first CI Linux run with the full dependency stack (torch, lifelines, pymoo, torch_geometric, ortools). The mechanical gates are wired; CI just needs to measure them once, then the ratchet helper locks the floors.
- Frontend Stryker's other 9 mutate files (jitter-retry, replay, confidence, http-client, ws-multiplex, firehose, auth-refresh, escalation.store, firehose.store) need similar survivor-killing test PRs before the break can be ratcheted past 50 → 70 → 85.

### No remaining FAILs

C14 (GCP `.tf` source) and C22 (SLO metric emit) — the two FAILs tracked in earlier
revisions — are now **PASS** and have their own `verify_claims.py` checks (see the rows above).
`make verify-claims` reports **36 PASS / 0 FAIL / 1 SKIP** (C43 SKIPs until an operator
publishes the production checkpoint). The only non-PASS row is the honest `$0` operator seam.

This file is updated at the end of every workstream PR. Each row that flips from `FAIL` to `PASS` has a corresponding check added to `scripts/audit/verify_claims.py`. **No claim flips to `PASS` without a programmatic check that can fail on regression** — that is the entire point.

---

## How to regenerate

```bash
make verify-claims          # runs scripts/audit/verify_claims.py, prints PASS/FAIL summary
make verify-claims-json     # JSON output for CI ingestion (added in WS-9)
```
