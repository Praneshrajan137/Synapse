# ============================================================================
# SYNAPSE Makefile — Development Automation
# ============================================================================
.PHONY: help up down test lint typecheck verify-infra seed generate-spec-tests fuzz mutate clean

SHELL := /bin/bash
COMPOSE := docker compose -f docker/docker-compose.yml --env-file docker/.env

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

up: ## Start all Docker services
	cp -n docker/.env.template docker/.env || true
	$(COMPOSE) up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	$(COMPOSE) ps

down: ## Stop all Docker services
	$(COMPOSE) down

restart: ## Restart all Docker services
	$(COMPOSE) restart

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=50

ps: ## Show service status
	$(COMPOSE) ps

topics: ## Create all 16 Kafka topics
	./scripts/create_kafka_topics.sh

seed: ## Initialize Neo4j schema + seed data
	cat infrastructure/neo4j/init.cypher | docker exec -i synapse-neo4j cypher-shell -u neo4j -p synapse_graph_2026
	cat infrastructure/neo4j/seed.cypher | docker exec -i synapse-neo4j cypher-shell -u neo4j -p synapse_graph_2026
	@echo "Neo4j schema initialized and seeded."

test: ## Run all unit + contract tests
	cd packages && pytest tests/ -v --tb=short
	@echo "All shared package tests passed."

test-coverage: ## Run tests with coverage report
	cd packages && pytest tests/ -v --cov=synapse_common --cov-report=term-missing --cov-fail-under=80

lint: ## Run ruff linter
	ruff check packages/synapse_common/ agents/ orchestrator/ --fix

typecheck: ## Run mypy strict type checking
	mypy --strict packages/synapse_common/

format: ## Format code with ruff
	ruff format packages/synapse_common/ agents/ orchestrator/

generate-spec-tests: ## Auto-generate test stubs from all spec.yaml files
	@for spec in $$(find agents/ -name "spec.yaml"); do \
		echo "Generating tests for $$spec..."; \
		python scripts/generate_tests_from_spec.py $$spec; \
	done
	@echo "All spec tests generated."

validate-specs: ## Validate all spec.yaml against schema
	@for spec in $$(find agents/ -name "spec.yaml"); do \
		python -c "import yaml, json, jsonschema; spec=yaml.safe_load(open('$$spec')); schema=json.load(open('docs/specs/agent_spec_schema.json')); jsonschema.validate(spec, schema); print('OK $$spec')"; \
	done

check-spec-coverage: ## Verify every spec invariant has a test
	python scripts/check_spec_coverage.py

validate-schemas: ## Validate all proto schemas
	python scripts/validate_schemas.py

contracts: ## Run design-by-contract tests
	cd packages && pytest tests/test_contracts.py -v

generate-data: ## Generate synthetic Feast parquet files
	python scripts/data_gen/generate_feast_data.py

quality: lint typecheck test contracts validate-schemas ## Run all quality checks
	@echo "All quality gates passed."

verify-infra: ## Verify all infrastructure services are healthy
	@echo "SYNAPSE Infrastructure Verification"
	@echo ""
	@echo "Checking Docker services..."
	$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}"
	@echo ""
	@echo "Checking Kafka topics..."
	@docker exec synapse-kafka kafka-topics.sh --list --bootstrap-server localhost:9092 2>/dev/null | grep "^synapse\." | wc -l | xargs -I{} echo "  Kafka topics: {}/16"
	@echo ""
	@echo "Checking Redis..."
	@docker exec synapse-redis redis-cli ping 2>/dev/null | xargs -I{} echo "  Redis: {}"
	@echo ""
	@echo "Checking Neo4j..."
	@echo "RETURN 1" | docker exec -i synapse-neo4j cypher-shell -u neo4j -p synapse_graph_2026 2>/dev/null && echo "  Neo4j: OK" || echo "  Neo4j: FAILED"
	@echo ""
	@echo "Checking Prometheus..."
	@curl -sf http://localhost:9090/-/healthy && echo "  Prometheus: OK" || echo "  Prometheus: FAILED"
	@echo ""
	@echo "Checking Grafana..."
	@curl -sf http://localhost:3000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Grafana: {d.get(\"database\",\"unknown\")}')" 2>/dev/null || echo "  Grafana: FAILED"
	@echo ""
	@echo "Checking MLflow..."
	@curl -sf http://localhost:5000/health && echo "  MLflow: OK" || echo "  MLflow: FAILED"
	@echo ""
	@echo "Checking PostgreSQL..."
	@docker exec synapse-postgres pg_isready -U synapse -d synapse_audit 2>/dev/null && echo "  PostgreSQL: OK" || echo "  PostgreSQL: FAILED"

ralph-%: ## Run Ralph loop for specific agent (e.g., make ralph-demand_prophet)
	./scripts/ralph/ralph.sh $* 20

ralph-all: ## Run Ralph loop for all agents in critical path order
	./scripts/ralph/ralph.sh demand_prophet 20
	./scripts/ralph/ralph.sh routing_navigator 20
	./scripts/ralph/ralph.sh inventory_sentinel 20
	./scripts/ralph/ralph.sh freshness_guardian 15
	./scripts/ralph/ralph.sh pricing_oracle 15
	./scripts/ralph/ralph.sh disruption_shield 15
	./scripts/ralph/ralph.sh supplier_trust 15
	./scripts/ralph/ralph.sh sustainability_agent 15

clean: ## Remove all generated files, caches, volumes
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ============================================================================
# Sprint 3+ Cloud Targets (Oracle Cloud Always-Free)
# ============================================================================
.PHONY: up-cloud down-cloud cloud-status migrate-neo4j-aura init-pinecone
.PHONY: ralph-sprint3 verify-sprint3

COMPOSE_CLOUD := docker compose -f docker/docker-compose.cloud.yml --env-file .env.cloud

up-cloud: ## Start all services on Oracle Cloud VM
	$(COMPOSE_CLOUD) up -d
	@echo "Waiting 60s for services to stabilize..."
	@sleep 60
	@$(MAKE) cloud-status

down-cloud: ## Stop all cloud services
	$(COMPOSE_CLOUD) down

cloud-status: ## Check health of all cloud services
	@echo "=== Infrastructure ==="
	$(COMPOSE_CLOUD) ps
	@echo ""
	@echo "=== Kafka ==="
	$(COMPOSE_CLOUD) exec kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>&1 | head -3
	@echo ""
	@echo "=== Neo4j Aura ==="
	@python -c "from neo4j import GraphDatabase; import os; d=GraphDatabase.driver(os.environ['NEO4J_AURA_URI'], auth=(os.environ['NEO4J_AURA_USER'], os.environ['NEO4J_AURA_PASSWORD'])); d.verify_connectivity(); print('OK Neo4j Aura connected'); d.close()"
	@echo ""
	@echo "=== Pinecone ==="
	@python -c "from pinecone import Pinecone; import os; pc=Pinecone(api_key=os.environ['PINECONE_API_KEY']); indexes=[i.name for i in pc.list_indexes()]; print(f'OK Pinecone connected: {len(indexes)} indexes: {indexes}')"
	@echo ""
	@echo "=== LangSmith ==="
	@python -c "from langsmith import Client; c=Client(); print('OK LangSmith connected')"

migrate-neo4j-aura: ## Migrate schema + data to Neo4j Aura Free
	python infrastructure/neo4j/migrate_to_aura.py

init-pinecone: ## Initialize Pinecone Starter index with playbooks
	python infrastructure/pinecone/init_pinecone.py

ralph-freshness_guardian: ## Ralph loop for Freshness Guardian (15 iterations)
	./scripts/ralph/ralph.sh freshness_guardian 15

ralph-pricing_oracle: ## Ralph loop for Pricing Oracle (15 iterations)
	./scripts/ralph/ralph.sh pricing_oracle 15

ralph-disruption_shield: ## Ralph loop for Disruption Shield (15 iterations)
	./scripts/ralph/ralph.sh disruption_shield 15

ralph-supplier_trust: ## Ralph loop for Supplier Trust (15 iterations)
	./scripts/ralph/ralph.sh supplier_trust 15

ralph-sustainability_agent: ## Ralph loop for Sustainability Agent (15 iterations)
	./scripts/ralph/ralph.sh sustainability_agent 15

ralph-sprint3: ## Run Ralph loop for all Sprint 3 agents sequentially
	$(MAKE) ralph-freshness_guardian
	$(MAKE) ralph-pricing_oracle
	$(MAKE) ralph-disruption_shield
	$(MAKE) ralph-supplier_trust
	$(MAKE) ralph-sustainability_agent

verify-sprint3: ## Verify all Sprint 3 deliverables
	@echo "=== Sprint 3 Verification ==="
	PYTHONPATH=. pytest agents/freshness_guardian/tests/ -v --tb=short
	PYTHONPATH=. pytest agents/pricing_oracle/tests/ -v --tb=short
	PYTHONPATH=. pytest agents/disruption_shield/tests/ -v --tb=short
	PYTHONPATH=. pytest agents/supplier_trust/tests/ -v --tb=short
	PYTHONPATH=. pytest agents/sustainability_agent/tests/ -v --tb=short
	PYTHONPATH=. pytest digital_twin/tests/ -v --tb=short
	PYTHONPATH=. pytest tests/integration/test_sprint3_agents.py -v --tb=short
	python scripts/check_spec_coverage.py
	@echo "Sprint 3 verification complete."
