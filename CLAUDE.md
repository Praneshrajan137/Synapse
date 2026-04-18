# CLAUDE.md — SYNAPSE Repository Governance

## Project Identity
- **Name**: SYNAPSE — Supply Yield Network with Autonomous Planning, Sensing & Execution
- **Domain**: Quick-commerce supply chain optimization (dark stores, 10-minute delivery)
- **Architecture**: Multi-agent RL system with LLM orchestration
- **Stack**: Python 3.11 | PyTorch | RLlib | FastAPI | Kafka | Neo4j | Redis | Ollama | React
- **License**: Apache 2.0
- **Cost**: $0 total — all components are open-source or free-tier (I-1)

## Critical Rules

### Architecture Rules
- 8 specialized agents, each in `agents/<name>/` with canonical structure
- 4 layers: Orchestration → Agent → Digital Twin → Data Fabric
- A2A protocol (JSON-RPC 2.0) for inter-agent communication (I-9)
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
- Coverage minimum: 80% on all packages
- Mutation survival: <15% rewards, <10% guardrails/audit
- Every spec.yaml invariant MUST have a corresponding test
- Spec-first development: write spec.yaml → generate tests (RED) → implement → GREEN

### Kafka Rules
- 16 topics defined in `infrastructure/kafka/topics.json` — FROZEN after Sprint 1
- NEVER use direct kafka-python — use `synapse_common.kafka_client` only
- NEVER enable `auto.create.topics` — all topics are pre-provisioned
- All messages use deterministic serialization for KV-cache preservation (I-13)

### Dependency Rules
- NEVER add a dependency with GPL-3.0 or AGPL-3.0 license
- NEVER add a dependency that costs money
- Allowed licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, PSF, ISC, MPL-2.0
- Pin all dependency versions with upper bounds in pyproject.toml

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

## Sprint Status
- **Sprint 1**: Infrastructure foundation (Docker, Neo4j, Kafka, Redis, PostgreSQL, shared packages, proto schemas, SDD framework, CI pipeline)
- **Sprint 2**: Agent implementation (Demand Prophet, Inventory Sentinel, Routing Navigator)
- **Sprint 3**: Orchestrator + Digital Twin
- **Sprint 4**: Remaining agents + API Gateway + Frontend
- **Sprint 5**: Hardening — Chaos engineering (9 failure modes), load testing, security (JWT, audit immutability, nginx), mutation testing, Schemathesis API fuzz, DragonflyDB evaluation (ADR-019)
- **Sprint 6**: Multi-city deployment — Mumbai via transfer learning, A/B testing framework, cold-start baselines, Feast multi-city, OSRM Mumbai, Docker Compose overlay, Grafana multi-city dashboard, demo choreography
