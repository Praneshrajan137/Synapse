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

## Sprint Status
- **Sprint 1**: Infrastructure foundation (Docker, Neo4j, Kafka, Redis, PostgreSQL, shared packages, proto schemas, SDD framework, CI pipeline)
- **Sprint 2**: Agent implementation (Demand Prophet, Inventory Sentinel, Routing Navigator)
- **Sprint 3**: Orchestrator + Digital Twin
- **Sprint 4**: Remaining agents + API Gateway + Frontend
