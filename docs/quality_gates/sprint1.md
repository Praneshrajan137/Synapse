# Quality Gate — Sprint 1: Infrastructure Foundation

## Scope
Stand up the SYNAPSE base infrastructure (Docker, Neo4j, Kafka, Redis, Postgres),
shared Python packages, proto schemas, SDD framework, and CI pipeline.

## Milestones
| # | Milestone | Verification |
|---|-----------|--------------|
| 1 | Docker Compose brings up Kafka, Redis, Neo4j, Postgres, MLflow, Prometheus, Grafana | `make up && make verify-infra` |
| 2 | 16 Kafka topics provisioned, frozen | `cat infrastructure/kafka/topics.json \| jq '.topics \| length' == 16` |
| 3 | Neo4j init.cypher applied with constraints + indexes | `make seed && make test-neo4j-schema` |
| 4 | `synapse_common` shared package installable | `pip install -e packages/ && python -c "import synapse_common"` |
| 5 | Proto schemas validate | `make schema-validate` |
| 6 | SDD spec schema published; agent_spec_schema.json valid | `python scripts/check_spec_coverage.py` |
| 7 | CI pipeline runs lint+typecheck+test on every PR | `.github/workflows/ci.yml` green on baseline commit |

## Acceptance criteria
- All 7 milestones green
- `make quality` exits 0
- Coverage on `synapse_common` ≥ 80%
- No banned dependencies (CI gate)

## Verification command
```bash
make sprint1-verify
```
