# CLAUDE.md — SYNAPSE Repository Governance

## Project Identity
- **Name**: SYNAPSE — Supply Yield Network with Autonomous Planning, Sensing & Execution
- **Domain**: Quick-commerce supply chain optimization (dark stores, 10-minute delivery)
- **Architecture**: Multi-agent RL system with LLM orchestration
- **Stack**: Python 3.11 | PyTorch | RLlib | FastAPI | Kafka | Neo4j | Redis | Ollama | React
- **License**: Apache 2.0
- **Cost**: $0 total — all components are open-source or free-tier (I-1)

## Critical Rules

### Workflow Rules
- **NEVER use `git worktree add` in this repo.** All work happens on a single working copy at the repo root, on a feature branch off `main`. To work on multiple things in parallel, use `git stash`, separate clones, or sequential branches — never worktrees. Reason: in May 2026 a worktree sprawl across `.claude/worktrees/` produced ~50K LOC of unmerged parallel rewrites that required an 8-PR consolidation effort (see `consolidate/backend-2026-05-24` branch + the `archive/*` tags) to recover from. The `.claude/worktrees/` directory is gitignored and must remain empty in any new clone.
- All consolidation source branches are preserved as immutable tags `archive/<branch>-<sha>` even after their working trees are removed. To revive any historical branch: `git checkout -b recover/<name> archive/<name>-<sha>`.

### Architecture Rules
- 8 specialized agents, each in `agents/<name>/` with canonical structure
- 4 layers: Orchestration → Agent → Digital Twin → Data Fabric
- A2A protocol (HTTP JSON-RPC 2.0) is the primary, supported inter-agent RPC path (I-9). Kafka topics are for event-sourcing, audit, and digital-twin synchronisation — NOT for inter-agent RPC (ADR-038). The `consumers` array in `infrastructure/kafka/topics.json` is mechanically enforced by `scripts/audit/topic_consumer_truth.py`; `consumers_planned` is design intent only.
- MCP protocol for agent-to-tool communication — NEVER conflate with A2A (I-9)
- 4 decision tiers: Tier 1 (<100ms RL-only) through Tier 4 (15-120s Monte Carlo+LLM)
- Independent reward functions per agent — NEVER share rewards across agents (I-2)
- Confidence-gated execution — below threshold triggers HITL escalation (I-5)

### Code Quality Rules
- NEVER use `print()` for logging — structlog only
- NEVER use bare `except:` — always catch specific exceptions
- NEVER import paid API clients (openai, anthropic, cohere, replicate) — CI blocks this (I-1)
- NEVER use fixed-delay retries — Full Jitter from `synapse_common.retry` only (ADR-016)
- NEVER mutate frozen Pydantic models after creation
- NEVER put dynamic data in LLM system prompts — breaks KV-cache (I-13)
- NEVER remove items from runtime context — append-only with status field (I-14)
- ALL functions MUST have type hints — `mypy --strict` must pass
- ALL JSON serialization: `json.dumps(obj, sort_keys=True, separators=(',',':'))`
- ALL agent outputs MUST validate against `proto/domain/*.schema.json` (I-3)

### Testing Rules
- Seven testing layers: SDD, Fuzz, Contract, Metamorphic, DbC, Oracle, Mutation
- Coverage minimum: **per-package floor in `infrastructure/quality/coverage-floors.yaml`**; target **84% line+branch combined on every package**; floors ratchet up via `scripts/coverage_ratchet.py --apply`, never down. Mechanical gate: `scripts/coverage_per_package.py` against `coverage.xml`. `branch = true` is mandatory in `[tool.coverage.run]` (C29)
- Mutation survival: <15% rewards, <10% guardrails/audit. Frontend Stryker `break: 26` ratcheting to 50→85. Python `mutmut` is PR-gated on changed `agents/*/training/rewards.py`, `orchestrator/guardrails/rules.py`, `orchestrator/audit/{logger,hash_chain}.py` via `mutation-fast` job (C30); full-matrix sweep stays on Sunday cron
- Every spec.yaml invariant MUST have a corresponding test. `scripts/check_spec_coverage.py` enforces **assertion-matched** coverage (an `assert` within 20 lines of the `INV-*` ID — substring matching was theatre and reported 100% while real coverage was 13.8%). CI gate `--threshold 12` (verified baseline) ratcheting toward 50 → 100 (C31)
- Spec-first development: write spec.yaml → generate tests (RED) → implement → GREEN
- NEVER use the broad `*/training/*` coverage omit — it hid `rewards.py` (mutation-tested at <15% survival) from the coverage gate. Use the narrow per-file patterns in pyproject (C32)

### Kafka Rules
- 17 topics defined in `infrastructure/kafka/topics.json`. Sprint 1 froze inter-agent topics (1-16). Sprint 7 added topic 17 `synapse.orders.demand` as the only ingress freeze exception per [ADR-029](docs/adr/ADR-029-orders-ingress-topic.md) (ingress is a different category from inter-agent communication). Future freeze exceptions require a fresh ADR
- NEVER use direct kafka-python — use `synapse_common.kafka_client` only
- NEVER enable `auto.create.topics` — all topics are pre-provisioned
- All messages use deterministic serialization for KV-cache preservation (I-13)

### Dependency Rules
- NEVER add a dependency with GPL-3.0 or AGPL-3.0 license
- NEVER add a dependency that costs money
- Allowed licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, PSF, ISC, MPL-2.0
- Pin all dependency versions with upper bounds in pyproject.toml

### GCP Deploy Rules (ADR-039)
- NEVER add a `build:` directive to a SYNAPSE-owned service in `docker/docker-compose.gcp.yml` — the GCP path is pull-from-Artifact-Registry only. `verify_claims.py` C26 fails CI on regression. Local dev uses `docker-compose.yml`, which keeps `build:` for fast iteration
- The `cd-gcp.yml` build matrix and `infrastructure/gcp/verify_images.sh`'s `IMAGES=()` array MUST stay in lockstep — `verify_claims.py` C27 enforces this. Add to both in the same PR when a new service is introduced
- Compose service `api` maps to AR image `api-gateway`; this alias is documented inline in the compose file. The other 11 SYNAPSE services use matching names
- The deployed SHA is visible in TWO places — `GET /version` on the API gateway and the `BuildSHAChip` in the frontend Shell. When a user reports "old UI", check the chip first; if it shows HEAD's SHA, the issue is browser cache (Ctrl+Shift+R), not deploy

### Chromatic System Rules (ADR-025)
- Frontend colour comes ONLY from chromatic tokens — NEVER a raw hex/`rgb()`/`hsl()` literal in `frontend/src/**`. The `no-raw-hex` hook blocks it (INV-CLR-009)
- Colour tokens are authored in OKLCH in `design-system/color/tokens/*.tokens.json` (W3C DTCG format). After ANY token edit run `npm run build` in `design-system/color/` and commit the regenerated `dist/`
- `dist/` artifacts are deterministic and committed — CI fails if a rebuild changes them (INV-CLR-010)
- Orthogonal Encoding Principle: agent identity → Hue, decision tier → Lightness, confidence → the diverging OKLab scale. NEVER cross these axes
- The 8 agent→hue assignments are FROZEN (INV-CLR-012) — changing one needs a version bump + an ADR supersede note
- Every `INV-CLR` invariant in `design-system/color/color-system.spec.yml` MUST have a test — `npm run spec:coverage` enforces it
- Validate colour against BOTH WCAG 2.1 AA and APCA; APCA targets are tiered by emphasis (primary 75 / secondary 60 / tertiary 45)

## Accumulated Error Patterns
- PostgreSQL REVOKE from superuser/owner is a no-op — use non-superuser app role
- Kafka CONTROLLER listener is KRaft-mode only — omit when using ZooKeeper
- Pydantic v2 frozen models require `object.__setattr__` in `model_post_init`
- Neo4j CREATE fails on uniqueness constraint re-run — use MERGE for idempotency
- Redis/Kafka/Neo4j do not expose /metrics natively — need exporters for Prometheus

### Sprint 5 Error Patterns
- E-S5-01: Chaos tests must be self-contained with simulated components, not depend on running services
- E-S5-02: Locust load tests require `--headless` flag for CI; `--html` for local debugging
- E-S5-03: Schemathesis requires OpenAPI spec at `/openapi.json` on each agent — ensure FastAPI auto-generates this
- E-S5-04: mutmut uses `.mutmut-cache/` — added to `.gitignore`
- E-S5-05: DragonflyDB uses same port 6379 internally — mapped to 6380 externally to avoid Redis collision
- E-S5-06: Nginx rate limiting uses `$binary_remote_addr` — Docker-internal IPs exempt via geo module
- E-S5-07: pytest-asyncio requires `asyncio_mode = "strict"` in `pyproject.toml` (set in Sprint 5)
- E-S5-08: python-jose requires `[cryptography]` extra for RS256 support
- E-S5-09: psycopg2-binary is for dev/test only; production uses psycopg2 with libpq
- E-S5-10: Mutation testing on reward functions requires `test_reward.py` to exist for EVERY agent
- E-S5-11: Chaos test fixture names must be namespaced (`chaos_*`) to avoid collision with orchestrator conftest
- E-S5-12: All RNG-dependent chaos tests must use `np.random.default_rng(seed)` for determinism in CI
- E-S5-13: `import logging` in shared packages replaced with structlog in Sprint 5 (retry.py, kafka_client.py, a2a_sdk.py)

### Sprint 6 Error Patterns
- E-S6-01: Mumbai SKU IDs must be identical to Bengaluru — transfer learning fails on embedding dimension mismatch otherwise
- E-S6-02: Each city's OSRM runs on a unique port (Bengaluru: 5000, Mumbai: 5001). Port collision causes routing failures
- E-S6-03: Each city has its own Feast project, registry file, and Redis DB index (Mumbai: db=1, Bengaluru: db=0)
- E-S6-04: ALWAYS recalibrate conformal intervals on Mumbai holdout after transfer learning. Bengaluru intervals are INVALID for Mumbai distribution
- E-S6-05: ALL Neo4j queries in multi-city mode MUST include `{city: $city}` filter. Add city property to every node
- E-S6-06: Each demo segment waits for Kafka consumer group lag to reach 0 before proceeding, not just wall-clock time
- E-S6-07: Mumbai models use `mumbai_` prefix in MLflow: `mumbai_demand_prophet_hgt_tft`, not `demand_prophet_hgt_tft`
- E-S6-08: A/B tests require minimum 1000 predictions per variant. Report Cohen's d alongside p-value
- E-S6-09: Mumbai Feast feature views MUST include `monsoon_intensity` (0-1 scale) not present in Bengaluru schema
- E-S6-10: Always use: `docker compose -f docker-compose.yml -f docker-compose.mumbai.yml up -d`. Never run Mumbai overlay alone
- E-S6-11: Run `scripts/convert_to_parquet.py --city mumbai` AFTER data generation, BEFORE Feast apply
- E-S6-12: Always use MERGE (not CREATE) for SKU nodes since they are shared across cities. SKU nodes have NO city property
- E-S6-13: All agent_card.json files must include `cities` array and `city_specific_config` object
- E-S6-14: Transfer-learned models are loaded from `mumbai_{model_name}` in Staging stage. Cold-start baselines from `mumbai_coldstart_{model_name}`
- E-S6-15: Neo4j property keys must match init.cypher constraints: store_id, warehouse_id, supplier_id, zone_id, rider_id, sku_id — NOT generic 'id'
- E-S6-16: Neo4j auth in scripts must match docker-compose.yml (`synapse_graph_2026`), not hardcoded values
- E-S6-17: Convergence speedup measures epoch at which transfer model achieves within 5% of Bengaluru's final metric, not early-stop epoch
- E-S6-18: A/B test control must be cold-start Mumbai model (not Bengaluru Production) for meaningful comparison
- E-S6-19: OSRM data prep (download/extract/process) is separate from container lifecycle (Docker Compose). Do not duplicate
- E-S6-20: `rng.normal()` with scalar args returns Python float, not ndarray — use `np.clip()` not `.clip()` method
- E-S6-21: `rng.uniform(low, high)` requires low < high — monsoon wind formula `rng.uniform(10, 60*m_intensity)` fails when m_intensity < 0.17; use `max(60*m_intensity, 11.0)` for high
- E-S6-22: Mumbai data generation MUST use start_date in monsoon window (June 1) not January 1, otherwise monsoon_intensity is all zeros and E-S6-09 tests fail
- E-S6-23: `make deploy-oracle` requires ORACLE_IP env var; VM must be provisioned manually via OCI Console first
- E-S6-24: Demo script (`scripts/demo/run_demo.sh`) must poll Kafka consumer group lag via Python confluent-kafka (not kafka-consumer-groups.sh) for cross-platform compatibility

### Sprint 9 Error Patterns
- E-S9-01: `audit_consensus` rows pre-Sprint-9 have NULL `prev_hash`/`current_hash` — `synapse audit verify` skips them but flags the gap. New rows always populate the chain.
- E-S9-02: Audit-chain row contents are canonicalised by `orchestrator/audit/hash_chain.make_canonical_row` — adding/removing fields requires a chain-rewrite migration, not a silent field bump.
- E-S9-03: `infrastructure/audit_anchors/<date>.json` MUST use compact JSON (`separators=(',',':')`) — the JSON-determinism contract test scans `orchestrator/`; `indent=2` fails the gate.
- E-S9-04: `@tier_budget(on_exceed="brownout")` requires the city's `BrownoutController` to be registered first (`orchestrator.consensus.brownout.register`). Pre-registration calls no-op with a structured warning.
- E-S9-05: Reward kwargs default to `reward_config.WEIGHTS["<key>"]` via `None`-sentinel pattern. Direct numeric defaults are gone (Sprint 9 cutover, ADR-031).
- E-S9-06: `cyclonedx-py` CLI is optional — `scripts/generate_sbom.py` falls back to a deterministic minimal CycloneDX 1.5 doc when the CLI is absent. Both forms must satisfy `--check`.
- E-S9-07: cosign keyless signing requires GitHub OIDC reachable from the runner. Workflow uses `--certificate-identity-regexp` against `https://github.com/<repo>/.github/workflows/.*`.
- E-S9-08: Helm subcharts use `linkerd.io/inject: enabled` annotation — the mesh is the *outer* ring; circuit breakers in `synapse_common.breakers` remain the inner ring.
- E-S9-09: KEDA `ScaledObject` polling interval is 15s; per-city scaling needs per-city consumer-group labels on the Prometheus query, not just per-city replicas.
- E-S9-10: The DPDPA cascade helper requires the **privileged** `synapse_erasure_operator` Postgres role; `synapse_app` does not have DELETE.
- E-S9-11: 200 golden traces are generated by `tests/eval/generate_traces.py --check` against a fixed seed (`0xCAFEBABE`). Drift = CI failure.
- E-S9-12: Live LLM-judge requires `SYNAPSE_LLM_JUDGE_LIVE=1` AND `OLLAMA_URL` reachable. CI keeps the stub returning `{"ci_stub": True, "score": None}`.
- E-S9-13: `redact_pii` structlog processor uses `MutableMapping[str, Any]` → `Mapping[str, Any]` per structlog's `Processor` typing — `dict[str, Any]` fails `mypy --strict`.
- E-S9-14: The new `audit_outbox` migration (Sprint 7) and `audit_chain` migration (Sprint 9) are mirrored at `infrastructure/postgres/` because Docker init reads from there; the canonical lives under `orchestrator/audit/migrations/`.
- E-S9-15: `scripts/check_cve_budget.py --update-registry` is an operator step, NOT part of normal CI — it intentionally writes back to `infrastructure/security/cve-budget.json`.

### Sprint 12 Error Patterns
- E-S12-01: `docker compose pull` is a silent no-op for services using `build:` — that is exactly how 4 PRs on `main` produced zero GCP deploys. C26 now fails CI before this can re-happen. (`docs/adr/ADR-039-gcp-deploy-pull-from-artifact-registry.md`)
- E-S12-02: `docker compose up -d` against a `:latest` tag that has moved digest does NOT re-pull and does NOT recreate the container. Use `--pull always --force-recreate` on the deploy step (now in `cd-gcp.yml`)
- E-S12-03: `cd-gcp.yml` previously fired only on `v*` tags; now it fires on push to `main` as well. Tag pushes remain valid for explicit releases. Both paths sign images with Cosign keyless via GitHub OIDC
- E-S12-04: The deploy job recomputes `VERSION` independently of the build-push-sign matrix (separate runners, no inherited outputs). Both use the same logic: tag→strip-v, main→`main-<sha7>`, dispatch→`dryrun-<sha7>`
- E-S12-05: `.env.gcp.version` is workflow-written on every deploy and is the LAST `--env-file` arg passed to `docker compose`, so it shadows anything a human edited in `.env.gcp.local`. Do not commit `.env.gcp.version` (it's transient, regenerated per run)
- E-S12-06: `VITE_BUILD_SHA` / `SYNAPSE_BUILD_SHA` are baked at IMAGE BUILD TIME via Docker build-args, not at compose-up time. A `dev` / `unknown` value in the chip or `/version` means the image was not produced by the CD pipeline (local dev or manual `docker build`)
- E-S12-07: `BuildSHAChip` styles via chromatic tokens only — no raw hex (INV-CLR-009). It uses `bg-surface-raised`, `text-ink-muted`, `bg-signal-warning/15`, `text-signal-success`. The `no-raw-hex` pre-commit hook would catch any regression
- E-S12-08: Cosign keyless signing in CI REQUIRES `permissions: id-token: write` on the workflow (or job). Without it, the cosign-installer cannot mint a GitHub OIDC token, falls back to the device-flow URL, and times out after 5 minutes in non-interactive CI with `error obtaining token: expired_token`. `cd-gcp.yml` had it; `cd.yml` did not (fixed in Sprint 12 follow-up)
- E-S12-09: When ADR-036's nightly auto-stop schedule is active, a CD run inside the stopped window hits IAP error `4003: failed to connect to backend` because port 22 is unreachable on a STOPPED instance. `cd-gcp.yml` now has an "Ensure VM is running" step that idempotently calls `gcloud compute instances start` and waits up to 90s for SSH to become reachable
- E-S12-10: The repo is private under `Aegis15`, so an unauthenticated `git clone https://github.com/<owner>/<repo>.git` on the VM hits `fatal: could not read Username for 'https://github.com': No such device or address`. The `Ensure repo cloned` step in `cd-gcp.yml` now builds an `x-access-token` URL using the workflow's own `GITHUB_TOKEN`, runs the clone/fetch/checkout, then resets `origin` back to the token-less URL so the token never persists in the VM's git config. Never `git push` with the token URL — it's read-only-scoped to this repo for the workflow's lifetime
- E-S12-11: `scripts/sbom_diff.py --check` fails CI on any dependency present in `infrastructure/sbom/*.cdx.json` that has no entry in `infrastructure/security/sbom-allowlist.yaml`. The allowlist is initialised by running `python scripts/sbom_diff.py --update` once (operator step). A `__placeholder__` entry means no operator has run `--update` yet — every dep will then fail the gate
- E-S12-12: Playwright E2E (`frontend.yml::e2e`) boots `pnpm preview` (the static build) and proxies `/api` to `localhost:8085` — there is no backend on the runner, so every test hits ECONNREFUSED. E2E only runs on `pull_request` (where the PR author is responsible for the data path) and on `v*` tag pushes (where infra-up is implied). The real end-to-end signal on push-to-main is `cd-gcp.yml::Wait for health` against the deployed VM
- E-S12-13: Bash inline env vars `A=1 B=2 cmd1 && cmd2` apply ONLY to `cmd1`. The previous `Cosign verify images BEFORE start` step set `SYNAPSE_AR_REPO_URL` next to `chmod`, then ran `./verify_images.sh` without it. Always `export` env vars or put them directly on the actual command line. The verify script's metadata-server fallback works only when the VM was created with the `artifact-registry-repo` attribute, which is not guaranteed
- E-S12-14: Stryker mutation testing is gated like E2E — `pull_request || v*` only. A push to `main` that drops the score 0.08 below the break threshold (25.92 < 26) turns CI red with no human in the loop to act on it. Mutation regressions are caught in PRs where the author can add tests before merging, and at tag time where the release is held until the score recovers
- E-S12-15: `scripts/sbom_diff.py` imports `yaml`; if PyYAML is not installed in the CI environment, the import resolves to `None` and `_load_allowlist` falls back to JSON parsing — which fails on the YAML allowlist and returns `{}`. The visible symptom is "SBOM components: 24, Allowlisted: 0, NOT allowlisted: 24" even when the on-disk allowlist is fully populated. Always include `pyyaml` in the `pip install` step that precedes the SBOM gate. Same trap applies to any operator script that imports YAML behind a try/except

### Sprint 13 Error Patterns
- E-S13-01: Per-package coverage gates require `coverage.xml` from a SINGLE pytest run that includes all three test trees (`packages/tests`, `agents`, `orchestrator`). Running pytest per-package and merging XMLs wastes ~3× wall-clock and creates merge inconsistencies. The CI step uses one `pytest --cov=packages/synapse_common --cov=agents --cov=orchestrator --cov-branch` invocation; `scripts/coverage_per_package.py` then attributes classes to packages by `<source>/<filename>` path-segment match
- E-S13-02: The previous `*/training/*` coverage omit (pyproject.toml) was the kind of "code-coverage hygiene" that silently disabled a critical gate — it excluded `rewards.py` from coverage while mutation testing relied on those very files. Always cross-check that a coverage omit pattern does NOT shadow a mutation target
- E-S13-03: `branch = true` lowers measured coverage by ~3–8 percentage points on the first measurement (uncovered conditional branches now count). Always seed per-package floors from a POST-branch baseline; setting floors against line-only numbers and then turning branch on fails CI on day one — this is what reverted Sprint 11 WS-9
- E-S13-04: `scripts/check_spec_coverage.py` substring matching was theatre — a comment containing `INV-DP-001` satisfied the check. The aggregate reported 100% while real assertion-matched coverage was 13.8%. Always prefer AST-walked assertion proximity over substring matching for any "X must have a corresponding Y" gate
- E-S13-05: `mutmut` on Windows is flaky (shells out to pytest per mutant; path-length and file-locking issues). Validate the PR-gate (`mutation-fast` job in mutation.yml) in CI Linux runners, not locally on the Windows dev box. Local runs on the relevant pure-function modules work but the per-mutant subprocess cost makes the dev loop painful
- E-S13-06: Cobertura `<coverage>` XML uses `<source>` roots plus `<class filename>` relative to a root. With multiple `--cov=` args you get multiple `<source>` entries — the per-package script must try every `<source>` as the prefix for each class and match by **path-segment containment** (`/pkg/` in `/source/pkg/file.py`), not by `startswith()`. A naive `startswith` returns 0 classes
- E-S13-07: Windows console default codepage is cp1252; both `Path.read_text()` and `print()` raise on Unicode (em-dashes, arrows). Always pass `encoding='utf-8'` to `read_text` in scripts and replace `→` with `->`, `─` with `-`, `•` with `*` in print output. The previous `check_spec_coverage.py` crashed on the first non-ASCII byte in any test file
- E-S13-08: `coverage_ratchet.py`'s `Path.relative_to(ROOT)` raises `ValueError` when the input path is on a different drive than `ROOT` (Windows). Wrap in try/except — `.resolve()` first, then `.relative_to()` with fallback to the absolute path

### Chromatic System Error Patterns
- E-CLR-01: Gamut-map with `culori.clampChroma` (preserves L+H exactly), NOT `toGamut` — `toGamut`'s RGB round-trip drifts hue several degrees
- E-CLR-02: Round chroma DOWN after gamut mapping — rounding to nearest can re-inflate a boundary colour back out of sRGB gamut (INV-CLR-008)
- E-CLR-03: The colour spec is named `color-system.spec.yml` (`.yml`, NOT `spec.yaml`) so the agent `spec-validate` hook does not validate it against the agent schema; the `color-spec-validate` hook handles it
- E-CLR-04: APCA has tiered Lc targets by text emphasis (75/60/45) — it is not a single threshold; button-label text is the secondary (60) tier
- E-CLR-05: Agent hues intentionally overlap semantic-state hues (disruption≈danger red, pricing≈warning gold) — separation is by disjoint UI role, not hue distance
- E-CLR-06: Agent palette lightness MUST be staggered, not held equal — equal-lightness categorical colours collapse under CVD simulation (INV-CLR-005)
- E-CLR-07: After editing any token JSON, rerun `npm run build` and commit `dist/` — CI's determinism gate fails on a stale `dist/`
- E-CLR-08: The frontend imports chromatic artifacts via the `@chromatic` Vite alias; `vite.config.js` `server.fs.allow` must include the repo root

## Sprint Status
- **Sprint 1**: Infrastructure foundation (Docker, Neo4j, Kafka, Redis, PostgreSQL, shared packages, proto schemas, SDD framework, CI pipeline)
- **Sprint 2**: Agent implementation (Demand Prophet, Inventory Sentinel, Routing Navigator)
- **Sprint 3**: Orchestrator + Digital Twin
- **Sprint 4**: Remaining agents + API Gateway + Frontend
- **Sprint 5**: Hardening — Chaos engineering (9 failure modes), load testing, security (JWT, audit immutability, nginx), mutation testing, Schemathesis API fuzz, DragonflyDB evaluation (ADR-019)
- **Sprint 6**: Multi-city deployment — Mumbai via transfer learning, A/B testing framework, cold-start baselines, Feast multi-city, OSRM Mumbai, Docker Compose overlay, Grafana multi-city dashboard, demo choreography
- **Sprint 7**: Foundation — resilience mesh (breakers, bulkheads, lifespan, tier-aware A2A), W3C traceparent + outbox + idempotency, KV-cache surface fix, brownout policy, decision replay, SLO YAMLs + multi-window burn alerts, ADR-029 orders-ingress topic, ADRs 025-030
- **Sprint 8**: Spec-as-source shadow mode + eval harness — `spec_cli.py validate / generate-reward-config / generate-alerts`, 20 golden traces, tier-routing accuracy gate, replay equivalence, reward-safety counterfactuals (demand_prophet + pricing_oracle), conformal city-stratify stub, LLM-judge stub, `@tier_budget` metric-only, `SemanticCache.retrieve_batch`, N+1 fixture, KV-cache 0.65 floor, ADRs 031-032
- **Sprint 9**: Supply chain + data lifecycle + production topology — CycloneDX SBOMs, cosign keyless signing, uv hash-pinned deps, audit chained-hash + verifier CLI + daily anchor, gated security scans, CVE-budget enforcement, SOPS secrets skeleton, audit archival (MinIO), DPDPA cascade helper, PII redaction structlog processor, KV-cache PII guard, Feast compaction, APScheduler jobs, brownout-budget integration, reward cutover (8/8 agents have reward_config.py), 200 golden traces, live LLM-judge behind flag, Helm chart **skeleton** (3 of 11 services — full chart lands in Sprint 11/WS-6), Linkerd/KEDA/Flagger CRDs as standalone YAML, DR runbooks, ADRs 033-035, 4 remaining test_reward_safety files, KV-cache 0.70 floor (gate added in Sprint 11/WS-9), tier-routing 80% floor (gate added in Sprint 11/WS-9)
- **Sprint 10**: Worktree consolidation + GCP-first deployment — Removed the `wonderful-franklin` worktree, deleted the 8 leftover unmerged branches (2 wip/* local, 6 claude/* remote) after pushing fresh archive tags (27 archive/* tags total preserved). Grafted GCP scaffolding from `archive/wip-gcp-deployment-96486c2` onto a feature branch (additive only — never merged the branch since its base predates Sprint 9). New Terraform module `infrastructure/gcp/terraform/` with Tier-A hardening (Secret Manager, Workload Identity Federation, Artifact Registry, Cloud Billing budget, nightly auto-stop schedule, Cloud Ops Agent install) and Tier-B hardening (Identity-Aware Proxy on admin + SSH, Cosign verify on image pull, dual-region-ready bucket with versioning + 30-day noncurrent lifecycle, Cloud DNS managed zone, opt-in Cloud Armor WAF). New `.github/workflows/cd-gcp.yml` triggers on `v*` tags: WIF auth, 12-image matrix build + Cosign keyless sign + push to Artifact Registry, IAP-tunneled SSH to GCE VM, `verify_images.sh`, `docker compose pull && up -d`, post-deploy audit-chain verify. Oracle Always-Free retained as the permanent $0 fallback. ADR-036 (single-VM GCE not GKE) and ADR-037 (dual-cloud cost honesty for I-1) capture the design. Sprint 7/9 Postgres SQL mounts added to docker-compose.gcp.yml (dev + cloud composes have the same pre-existing gap — out of scope, flagged for a follow-up).
- **Sprint 11 — Verification Rigor** (`plans/i-have-finished-most-nifty-sifakis.md` — landed): every load-bearing CLAUDE.md claim becomes a mechanical CI gate. Deliveries by workstream:
  - **WS-0**: `docs/state/CURRENT.md` truth ledger + `scripts/audit/verify_claims.py` (one check per former drift point).
  - **WS-1**: GCP branch merge artefacts (`terraform-validate.yml`, `.env.cloud.{gcp,oracle}.example`, `docs/deploy/README.md`); merge of `feat/gcp-primary-deployment` lands the Sprint-10 module on `main`.
  - **WS-2**: `OutboxDispatcher` wired into orchestrator lifespan; `api/routers/orders.py` rewritten to use shared producer + outbox + schema validation; traceparent injected at API→orchestrator boundary; idempotency_key on override (migration `0004_orders_outbox_idempotency.sql`).
  - **WS-3**: ADR-038 (HTTP-A2A primary, Kafka for event-sourcing); `topics.json` v1.2.0 with empirical `consumers`; `topic_consumer_truth.py` CI gate; 8 `agent_card.json` updated.
  - **WS-4**: typed `getDecision` + `getTopology` + JWKS hook; Zod schema on firehose envelope (`firehose-schema.ts`); raw fetch eliminated from FE surfaces.
  - **WS-5**: `POST /api/v1/steering` endpoint + `audit_steering` table (migration `0005_steering.sql`); FE store posts before mutating.
  - **WS-6**: Helm chart now templates **11/11 services** (8 agents + orchestrator + API + digital-twin); Linkerd/KEDA/Flagger moved into orchestrator subchart templates; NetworkPolicy/PDB/HPA/ServiceAccount added everywhere.
  - **WS-7**: SLO→burn-rate generator (`slo_to_rules.py`); Alertmanager config; `metric_truth.py` surfaced 3 alerted-but-not-emitted metrics.
  - **WS-8**: cosign keyless signing in `cd.yml`; admission policy (`cosign-policy.yaml`); SBOM diff gate + CVE budget gate in CI.
  - **WS-9**: coverage floor restored 60→80; Stryker `break: 50`; KV-cache + tier-routing floor tests; nightly live LLM-judge workflow.
  - **WS-10**: Hypothesis property fuzz on consensus invariants; counterfactual replay; chaos-day runbook.
  - **WS-11**: README, CLAUDE.md sprint status, ADR index, `make verify-claims` count posted to PR.
  - **WS-12**: emit the three alerted-but-not-emitted metrics flagged by WS-7; closes C22.
- **Sprint 12 — Deploy Truth** (`plans/on-past-five-days-parsed-wilkinson.md` — landed): the GCP CD pipeline now mechanically reaches the VM on every merge to `main`. ADR-039 captures the contract: `docker-compose.gcp.yml` references **`image:` only** (no `build:`), with `pull_policy: always`; `cd-gcp.yml` fires on push-to-main (tags `:main-<sha7>`/`:main`/`:latest`) **and** on `v*` tags (explicit release). `verify_images.sh` now covers all 12 signed images (frontend was the missing one). The API gateway exposes `GET /version` and the frontend Shell carries a `BuildSHAChip` so the deployed SHA is visible without leaving the page. Two new mechanical checks — C26 (`gcp_compose_pulls_images`) and C27 (`verify_images_covers_matrix`) — prevent the trap from re-arming. Closed the incident where 4 PRs on `main` produced zero GCP deploys.
- **Sprint 13 — Coverage & Mutation Truth** (`plans/i-want-the-coverage-vectorized-eagle.md` — landed): the WS-9 attempt to restore "60→80 coverage in one CI edit" was reverted same-day because nothing was measured. This sprint replaces the single global `--cov-fail-under` with a per-package mechanical gate, turns branch coverage on, makes Python mutation testing PR-blocking on changed targets (parity with frontend Stryker), and replaces the gameable substring-match spec-coverage with an assertion-matched gate. Deliveries:
  - **Phase 0** — Measured per-package baseline written to `docs/state/coverage-baseline-2026-05-29.md`. The 100% spec-coverage substring claim was theatre — verified assertion-matched aggregate is 13.8%, with only demand_prophet's `test_spec.py` putting `assert` near `INV-*` IDs.
  - **Phase 1** — Two missing `test_reward_safety.py` files created (`inventory_sentinel`, `supplier_trust`); `*/training/*` omit narrowed to per-file patterns so `rewards.py` is now covered; CI pytest scope expanded from `packages/tests` only to `packages/tests + agents + orchestrator`; `check_spec_coverage.py` UTF-8 crash fixed for Windows.
  - **Phase 2** — `infrastructure/quality/coverage-floors.yaml` (10 packages, seeded from Phase 0); `scripts/coverage_per_package.py` (Cobertura XML → per-package gate); `scripts/coverage_ratchet.py` (operator helper that bumps floors after gains, never down).
  - **Phase 3** — 54 new tests covering 5 previously-0% modules in `synapse_common`: `budget.py`, `dbc.py`, `reward_shadow.py`, `outbox.py::canonical_payload`, `schema_registry.py`. Coverage 61.18% → 75.99% (+14.8 pts); floor ratcheted to 75.5.
  - **Phase 4.2** — `mutation-fast` job added to `.github/workflows/mutation.yml`: runs `mutmut` on `pull_request` for files actually changed under `agents/*/training/rewards.py`, `orchestrator/guardrails/rules.py`, `orchestrator/audit/{logger,hash_chain}.py` with the existing <15%/<10% survival thresholds. Sunday cron remains for the full matrix.
  - **Phase 5** — `scripts/check_spec_coverage.py` rewritten with `--threshold`, `--json`, `--per-agent`, and assertion-matched mode (an `assert` within 20 lines of the `INV-*` ID, via `ast`). Wired into ci.yml at `--threshold 12` (just below measured 13.8); ratchet plan 12→25→50→75→100.
  - **Phase 6** — Five new C-rows in `docs/state/CURRENT.md` (C28 per-package floors, C29 branch coverage, C30 mutmut PR-gate, C31 spec-coverage in CI, C32 training omit narrowed) each with a `verify_claims.py` mechanical check. `make verify-claims` now reports 25 PASS / 0 FAIL / 1 SKIP (the unrelated pre-existing C22 metric_truth import).
  - **Outstanding ratchets** (multi-PR climb): per-package coverage 75.5→84 on synapse_common, CI-must-measure baselines on orchestrator + 8 agents → 84 each, Stryker break 26→50→85, spec-coverage assertion-matched 13.8→50→100. Each is a mechanical ratchet now, not aspirational prose.
