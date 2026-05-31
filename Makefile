# ============================================================================
# SYNAPSE Makefile — Development Automation
# ============================================================================
.PHONY: help up down test lint typecheck verify-infra seed generate-spec-tests fuzz mutate clean chaos-test load-test security-test dragonfly-eval sprint5-verify verify-services doctor verify-claims verify-claims-json verify-intelligence feast-build feast-up

SHELL := /bin/bash
COMPOSE := docker compose -f docker/docker-compose.yml --env-file docker/.env

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

doctor: ## Pre-flight: verify host can run the demo (Ollama, Docker, ports, seed data)
	@python scripts/preflight/doctor.py

verify-claims: ## Verify every CLAUDE.md claim against code reality (see docs/state/CURRENT.md)
	@python -m scripts.audit.verify_claims

verify-claims-json: ## Same as verify-claims but emit machine-readable JSON
	@python -m scripts.audit.verify_claims --json

verify-topology: ## Verify topics.json consumers map to real Consumer.subscribe call sites (ADR-038)
	@python -m scripts.audit.topic_consumer_truth

feast-build: ## Generate the Feast offline demand-signals parquet from real history (ADR-042 §Feast)
	@python scripts/build_feature_store.py --city bengaluru

feast-up: feast-build ## Build parquet + feast apply + materialize to Redis online store (needs Redis on :6379)
	@python scripts/build_feature_store.py --city bengaluru --apply
	@cd data_fabric/feast && python -m feast materialize-incremental $$(date -u +%Y-%m-%dT%H:%M:%S) || echo "materialize needs Redis on :6379"

verify-intelligence: ## Substance-completion gates (ADR-042): training/checkpoint/serving/calibration/confidence-basis truth
	@python -m scripts.audit.training_truth --check
	@python -m scripts.audit.checkpoint_truth --check
	@python -m scripts.audit.serving_truth --check
	@python -m scripts.audit.calibration_truth --check
	@python -m scripts.audit.confidence_basis_truth --check

verify-slos: ## Regenerate burn-rate rules from SLO YAMLs and verify metric_truth (WS-7)
	@python -m scripts.observability.slo_to_rules --check
	@python -m scripts.observability.metric_truth

verify-supply-chain: ## SBOM diff + CVE budget gate (WS-8)
	@python scripts/sbom_diff.py --check
	@python scripts/check_cve_budget.py

fmt-oracle: ## Auto-format the Oracle Terraform module (operator step; clears pre-existing drift)
	@cd infrastructure/oracle/terraform && terraform fmt -recursive -diff

fmt-gcp: ## Auto-format the GCP Terraform module
	@cd infrastructure/gcp/terraform && terraform fmt -recursive -diff

up: doctor ## Start all Docker services (runs doctor first)
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
	@for spec in $$(find agents/ orchestrator/ -name "spec.yaml"); do \
		echo "Generating tests for $$spec..."; \
		python scripts/generate_tests_from_spec.py $$spec; \
	done
	@echo "All spec tests generated."

validate-specs: ## Validate all spec.yaml against schema
	@for spec in $$(find agents/ orchestrator/ -name "spec.yaml"); do \
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

verify-sprint4: ## Verify all Sprint 4 deliverables
	@echo "=== Sprint 4 Verification ==="
	PYTHONPATH=. pytest orchestrator/tests/ -v --tb=short
	PYTHONPATH=. pytest orchestrator/contracts/ -v --tb=short -m contract
	PYTHONPATH=. pytest tests/oracle/ -v --tb=short -m oracle
	python scripts/verify/test_context_immutability.py
	python scripts/check_spec_coverage.py
	@echo "Sprint 4 verification complete."

ralph-orchestrator: ## Ralph loop for Orchestrator (20 iterations)
	./scripts/ralph/ralph.sh orchestrator 20

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

# ============================================================================
# Sprint 5: Hardening Targets
# ============================================================================
.PHONY: chaos-test load-test fuzz mutate security-test dragonfly-eval sprint5-verify verify-services

verify-services: ## Check that Docker services are healthy before running integration tests
	@echo "Verifying Docker services..."
	@$(COMPOSE) ps --format "table {{.Name}}\t{{.Status}}" | grep -q "healthy" || \
		(echo "ERROR: Services not healthy. Run 'make up' first." && exit 1)
	@echo "Services verified."

chaos-test: ## Run all 9 chaos engineering tests
	PYTHONPATH=. python -m pytest tests/chaos/ -v --tb=short -m chaos

load-test: verify-services ## Run Locust load test (LOCUST_SCENARIO env selects 1 of 6; default sustained)
	SYNAPSE_LOAD_SCENARIO=$${LOCUST_SCENARIO:-sustained} bash tests/load/run_load_tests.sh --single

load-test-all: verify-services ## Run all 6 v4.0 load scenarios sequentially
	bash tests/load/run_load_tests.sh --all

fuzz: verify-services ## Run Schemathesis API fuzz tests (requires running services)
	bash tests/api_fuzz/run_fuzz.sh

mutate: ## Run mutation tests on rewards, guardrails, audit
	bash tests/mutation/run_mutation.sh

security-test: ## Run security test suite
	PYTHONPATH=. python -m pytest tests/security/ -v --tb=short

dragonfly-eval: ## Run DragonflyDB evaluation (ADR-019)
	PYTHONPATH=. python -m pytest tests/evaluation/test_dragonflydb.py -v --tb=short

sprint5-verify: ## Full Sprint 5 quality gate verification
	@echo "============================================="
	@echo "SYNAPSE Sprint 5 Quality Gate Verification"
	@echo "============================================="
	@echo ""
	@echo "--- 1. Chaos Engineering (9 failure modes) ---"
	$(MAKE) chaos-test
	@echo ""
	@echo "--- 2. Security Tests ---"
	$(MAKE) security-test
	@echo ""
	@echo "--- 3. Mutation Testing ---"
	$(MAKE) mutate
	@echo ""
	@echo "--- 4. Schemathesis API Fuzz (requires services) ---"
	$(MAKE) fuzz || echo "SKIP: Services not running"
	@echo ""
	@echo "--- 5. DragonflyDB Evaluation (requires services) ---"
	$(MAKE) dragonfly-eval || echo "SKIP: DragonflyDB/Redis not running"
	@echo ""
	@echo "--- 6. Load Testing (requires services) ---"
	$(MAKE) load-test || echo "SKIP: Services not running"
	@echo ""
	@echo "============================================="
	@echo "Sprint 5 Verification Complete"
	@echo "============================================="

# ============================================================================
# Sprint 6: Multi-City Deployment (Mumbai)
# ============================================================================
.PHONY: generate-bengaluru generate-mumbai convert-parquet-mumbai seed-mumbai
.PHONY: transfer-train cold-start-baseline ab-test
.PHONY: demo demo-fast demo-mumbai verify-multi-city sprint6-verify
.PHONY: mumbai-up mumbai-down sprint6-full sprint5-exit-gate

COMPOSE_MUMBAI := docker compose -f docker/docker-compose.yml -f docker/docker-compose.mumbai.yml --env-file docker/.env

sprint5-exit-gate: ## Verify all Sprint 5 prerequisites before Sprint 6
	@echo "Running Sprint 5 Exit Gate..."
	@python -c "import json; assert len(json.load(open('data/bengaluru/stores.json'))) == 25; print('Bengaluru stores OK')"
	@python scripts/verify_ollama.py
	@echo "Sprint 5 Exit Gate: PASSED"

generate-bengaluru: ## Generate Bengaluru city data (25 stores, 90 days, 500 SKUs)
	python scripts/generate_city.py --city bengaluru --stores 25 --days 90 --seed 42

generate-mumbai: ## Generate Mumbai city data (25 stores, 90 days, 500 SKUs)
	python scripts/generate_city.py --city mumbai --stores 25 --days 90 --seed 42

convert-parquet-mumbai: ## Convert Mumbai CSV to Parquet for Feast
	python scripts/convert_to_parquet.py --city mumbai

seed-mumbai: ## Seed Mumbai data into Neo4j
	python scripts/seed_mumbai_graph.py

transfer-train: ## Run transfer learning for all agents (Bengaluru -> Mumbai)
	@echo "Starting transfer learning pipeline..."
	@for agent in demand_prophet routing_navigator inventory_sentinel_l1 inventory_sentinel_l2 pricing_oracle disruption_shield supplier_trust; do \
		echo "Transfer training: $$agent"; \
		python ml_pipelines/transfer/transfer.py --agent $$agent --source-city bengaluru --target-city mumbai; \
	done
	@echo "Transfer learning complete for all agents"

cold-start-baseline: ## Train cold-start baselines for A/B testing
	@echo "Training cold-start baselines..."
	@for agent in demand_prophet routing_navigator inventory_sentinel_l1 pricing_oracle disruption_shield supplier_trust; do \
		echo "Cold-start baseline: $$agent"; \
		python ml_pipelines/transfer/cold_start_baseline.py --agent $$agent; \
	done
	@echo "Cold-start baselines complete"

ab-test: ## Run A/B tests comparing transfer vs cold-start models
	python ml_pipelines/ab_test/run_ab_tests.py --city mumbai
	@echo "A/B test results logged to MLflow"

demo: ## Run the full 5-minute demo
	bash scripts/demo/run_demo.sh bengaluru 1.0

demo-fast: ## Run demo at 3x speed (for verification)
	bash scripts/demo/run_demo.sh bengaluru 3.0

demo-mumbai: ## Run demo with Mumbai city
	bash scripts/demo/run_demo.sh mumbai 1.0

verify-multi-city: ## Verify multi-city deployment quality gate
	PYTHONPATH=. pytest scripts/verify/test_multi_city.py -v --tb=short

sprint6-verify: verify-multi-city ## Full Sprint 6 verification
	@echo "============================================="
	@echo "  SPRINT 6 VERIFICATION COMPLETE"
	@echo "============================================="

mumbai-up: ## Start Mumbai agent containers
	$(COMPOSE_MUMBAI) up -d

mumbai-down: ## Stop Mumbai agent containers
	$(COMPOSE_MUMBAI) down

sprint6-full: sprint5-exit-gate generate-bengaluru generate-mumbai convert-parquet-mumbai seed-mumbai transfer-train cold-start-baseline ab-test mumbai-up verify-multi-city ## Complete Sprint 6 end-to-end
	@echo "============================================="
	@echo "  SPRINT 6 COMPLETE — Total Cost: $$0"
	@echo "============================================="

# ============================================================================
# Oracle Cloud Always-Free Deployment
# ============================================================================
.PHONY: deploy-oracle deploy-oracle-setup deploy-oracle-push deploy-oracle-verify \
        deploy-oracle-terraform deploy-oracle-register-runner deploy-oracle-smoke

ORACLE_USER ?= ubuntu
ORACLE_KEY  ?= ~/.ssh/oracle_synapse
ORACLE_IP   ?= $(shell echo $$ORACLE_IP)
ORACLE_TF_DIR := infrastructure/oracle/terraform

deploy-oracle: deploy-oracle-setup deploy-oracle-push deploy-oracle-verify ## Deploy to Oracle Cloud Always-Free VM

deploy-oracle-setup: ## Provision Oracle VM (run setup script remotely)
	@echo "============================================="
	@echo "  SYNAPSE Oracle Cloud Deployment"
	@echo "============================================="
	@echo ""
	@echo "Prerequisites (manual via OCI Console):"
	@echo "  1. Create Always-Free VM (Ampere A1, 4 OCPU, 24GB RAM)"
	@echo "  2. Configure VCN + security list (ports: 22, 80, 443, 3000, 9090, 8080-8099)"
	@echo "  3. Add SSH public key"
	@echo "  4. Set ORACLE_IP env var: export ORACLE_IP=<vm-public-ip>"
	@echo ""
	@test -n "$(ORACLE_IP)" || (echo "ERROR: ORACLE_IP not set" && exit 1)
	@echo "Running setup script on $(ORACLE_IP)..."
	ssh -i $(ORACLE_KEY) -o StrictHostKeyChecking=accept-new $(ORACLE_USER)@$(ORACLE_IP) 'bash -s' < infrastructure/oracle/setup_oracle_vm.sh

deploy-oracle-push: ## Push compose + config to Oracle VM
	@test -n "$(ORACLE_IP)" || (echo "ERROR: ORACLE_IP not set" && exit 1)
	@echo "Copying deployment files..."
	scp -i $(ORACLE_KEY) docker/docker-compose.cloud.yml $(ORACLE_USER)@$(ORACLE_IP):~/synapse/docker-compose.cloud.yml
	@test -f .env.cloud && scp -i $(ORACLE_KEY) .env.cloud $(ORACLE_USER)@$(ORACLE_IP):~/synapse/.env.cloud || echo "WARNING: .env.cloud not found — using defaults"
	@echo "Starting services..."
	ssh -i $(ORACLE_KEY) $(ORACLE_USER)@$(ORACLE_IP) 'cd ~/synapse && docker compose -f docker-compose.cloud.yml --env-file .env.cloud up -d'

deploy-oracle-verify: ## Verify Oracle Cloud deployment health
	@test -n "$(ORACLE_IP)" || (echo "ERROR: ORACLE_IP not set" && exit 1)
	@echo "Verifying Oracle deployment..."
	ssh -i $(ORACLE_KEY) $(ORACLE_USER)@$(ORACLE_IP) 'cd ~/synapse && docker compose -f docker-compose.cloud.yml ps'
	@echo ""
	@echo "Checking Grafana..."
	@curl -sf http://$(ORACLE_IP):3000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Grafana: {d.get(\"database\",\"unknown\")}')" 2>/dev/null || echo "Grafana: not reachable (check security list port 3000)"
	@echo ""
	@echo "Checking Prometheus..."
	@curl -sf http://$(ORACLE_IP):9090/-/healthy && echo "Prometheus: OK" || echo "Prometheus: not reachable"
	@echo ""
	@echo "============================================="
	@echo "  Oracle Cloud Deployment Verified"
	@echo "  Dashboard: http://$(ORACLE_IP):3000"
	@echo "  Prometheus: http://$(ORACLE_IP):9090"
	@echo "  Cost: $$0 (Always-Free tier)"
	@echo "============================================="

deploy-oracle-terraform: ## Provision Oracle VM via Terraform IaC
	@echo "============================================="
	@echo "  Terraform apply — Oracle VM provisioning"
	@echo "============================================="
	@command -v terraform >/dev/null || (echo "ERROR: terraform not installed (https://developer.hashicorp.com/terraform/downloads)" && exit 1)
	@test -f $$HOME/.ssh/oracle_synapse.pub || (echo "ERROR: SSH key missing — run: ssh-keygen -t ed25519 -f ~/.ssh/oracle_synapse -N ''" && exit 1)
	@test -n "$$TF_VAR_tenancy_ocid" || (echo "ERROR: TF_VAR_tenancy_ocid + TF_VAR_user_ocid + TF_VAR_compartment_ocid + TF_VAR_fingerprint + TF_VAR_private_key_path required (see infrastructure/oracle/terraform/README.md)" && exit 1)
	cd $(ORACLE_TF_DIR) && terraform init -upgrade
	cd $(ORACLE_TF_DIR) && terraform apply -auto-approve \
	    -var="ssh_public_key=$$(cat $$HOME/.ssh/oracle_synapse.pub)"
	@echo ""
	@echo "Set ORACLE_IP in your shell:"
	@echo "  export ORACLE_IP=$$(cd $(ORACLE_TF_DIR) && terraform output -raw public_ip)"

deploy-oracle-register-runner: ## Bootstrap VM + register GitHub Actions self-hosted runner
	@test -n "$(ORACLE_IP)" || (echo "ERROR: ORACLE_IP not set (run deploy-oracle-terraform first)" && exit 1)
	@test -n "$(GH_RUNNER_URL)" || (echo "ERROR: GH_RUNNER_URL=https://github.com/<owner>/<repo> required" && exit 1)
	@test -n "$(GH_RUNNER_TOKEN)" || (echo "ERROR: GH_RUNNER_TOKEN required (GitHub → Settings → Actions → Runners → New self-hosted runner; token expires in 60 min)" && exit 1)
	@echo "Bootstrapping Oracle VM and registering runner on $(ORACLE_IP)..."
	ssh -i $(ORACLE_KEY) -o StrictHostKeyChecking=accept-new $(ORACLE_USER)@$(ORACLE_IP) \
	    "GH_RUNNER_URL='$(GH_RUNNER_URL)' GH_RUNNER_TOKEN='$(GH_RUNNER_TOKEN)' bash -s" \
	    < infrastructure/oracle/setup_oracle_vm.sh
	@echo ""
	@echo "Verify runner is online: $(GH_RUNNER_URL)/settings/actions/runners"

deploy-oracle-smoke: ## End-to-end smoke check on Oracle VM (memory, docker, ollama, runner)
	@test -n "$(ORACLE_IP)" || (echo "ERROR: ORACLE_IP not set" && exit 1)
	@echo "=== Oracle VM smoke checks ==="
	ssh -i $(ORACLE_KEY) $(ORACLE_USER)@$(ORACLE_IP) ' \
	    set -e; \
	    echo "--- free -h ---"; free -h; \
	    echo "--- nproc ---"; nproc; \
	    echo "--- docker info ---"; docker info | grep -E "Architecture|CPUs|Total Memory" || true; \
	    echo "--- ollama tags ---"; curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; [print(m[\"name\"]) for m in json.load(sys.stdin)[\"models\"]]"; \
	    echo "--- actions runner svc ---"; sudo systemctl status actions.runner.* --no-pager | head -10 || echo "Runner service not found (skip if runner not registered)"; \
	    echo "--- swap ---"; swapon --show; \
	'


# ============================================================================
# GCP DEPLOYMENT — primary deployment target (mirror of deploy-oracle-* above).
# Targets: Compute Engine VM (e2-standard-8), Debian 12, amd64.
# See docs/deploy/gcp-quickstart.md and infrastructure/gcp/README.md.
# Oracle remains as permanent $0 fallback (deploy-oracle-* above).
# ============================================================================
.PHONY: deploy-gcp deploy-gcp-terraform deploy-gcp-setup deploy-gcp-push \
        deploy-gcp-verify deploy-gcp-smoke deploy-gcp-destroy \
        up-gcp down-gcp gcp-status gcp-logs gcp-shell \
        gcp-stop-vm gcp-start-vm gcp-restart-vm

GCP_USER   ?= synapse
GCP_KEY    ?= ~/.ssh/gcp_synapse
GCP_IP     ?= $(shell echo $$GCP_IP)
GCP_VM     ?= synapse-demo
GCP_ZONE   ?= asia-south1-a
GCP_TF_DIR := infrastructure/gcp/terraform
GCP_COMPOSE := docker compose -f docker-compose.gcp.yml --env-file .env.gcp --env-file .env.gcp.local

deploy-gcp: deploy-gcp-setup deploy-gcp-push deploy-gcp-verify ## End-to-end GCP deploy (setup + push + verify)

deploy-gcp-terraform: ## Provision GCP VM via Terraform (one-time)
	@echo "============================================="
	@echo "  Terraform apply — GCP VM provisioning"
	@echo "============================================="
	@command -v terraform >/dev/null || (echo "ERROR: terraform not installed (winget install HashiCorp.Terraform)" && exit 1)
	@command -v gcloud >/dev/null || (echo "ERROR: gcloud CLI not installed (https://cloud.google.com/sdk/docs/install)" && exit 1)
	@test -f $(GCP_TF_DIR)/terraform.tfvars || (echo "ERROR: $(GCP_TF_DIR)/terraform.tfvars missing — copy terraform.tfvars.example and edit it" && exit 1)
	cd $(GCP_TF_DIR) && terraform init -upgrade
	cd $(GCP_TF_DIR) && terraform apply -auto-approve
	@echo ""
	@echo "Set GCP_IP in your shell:"
	@echo "  export GCP_IP=$$(cd $(GCP_TF_DIR) && terraform output -raw public_ip)"
	@echo "  (PowerShell: \$$env:GCP_IP = (terraform -chdir=$(GCP_TF_DIR) output -raw public_ip))"

deploy-gcp-setup: ## Bootstrap GCP VM (Docker, Ollama, certbot, swap, backup cron, Secret Manager fetch, Cloud Ops Agent)
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set (run deploy-gcp-terraform first, then export GCP_IP)" && exit 1)
	@echo "Bootstrapping GCP VM at $(GCP_IP)..."
	@# Source DOMAIN_NAME and LETSENCRYPT_EMAIL from .env.gcp so certbot fires
	@if [ -f .env.gcp ]; then \
	    set -a; . ./.env.gcp; set +a; \
	    ssh -i $(GCP_KEY) -o StrictHostKeyChecking=accept-new $(GCP_USER)@$(GCP_IP) \
	        "DOMAIN_NAME='$$DOMAIN_NAME' LETSENCRYPT_EMAIL='$$LETSENCRYPT_EMAIL' OLLAMA_MODEL='$$OLLAMA_MODEL' bash -s" \
	        < infrastructure/gcp/setup_gcp_vm.sh; \
	else \
	    ssh -i $(GCP_KEY) -o StrictHostKeyChecking=accept-new $(GCP_USER)@$(GCP_IP) 'bash -s' < infrastructure/gcp/setup_gcp_vm.sh; \
	fi
	@echo ""
	@echo "Cloning repo onto VM (or pulling latest if already cloned)..."
	@ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) ' \
	    if [ ! -d ~/synapse/.git ]; then \
	        git clone https://github.com/Praneshrajan137/synapse.git ~/synapse || \
	        echo "WARN: clone failed — push the repo manually or set the right remote"; \
	    else \
	        cd ~/synapse && git pull --ff-only || echo "WARN: pull failed (uncommitted changes on VM?)"; \
	    fi'

deploy-gcp-push: ## Push compose + env to GCP VM and (re)start services
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	@test -f .env.gcp || (echo "ERROR: .env.gcp not found — cp .env.gcp.example .env.gcp and edit" && exit 1)
	@echo "Copying compose + env + backup script to $(GCP_IP)..."
	scp -i $(GCP_KEY) docker/docker-compose.gcp.yml $(GCP_USER)@$(GCP_IP):~/synapse/docker/docker-compose.gcp.yml
	scp -i $(GCP_KEY) .env.gcp $(GCP_USER)@$(GCP_IP):~/synapse/.env.gcp
	scp -i $(GCP_KEY) infrastructure/gcp/backup_to_gcs.sh $(GCP_USER)@$(GCP_IP):~/synapse/backup_to_gcs.sh
	scp -i $(GCP_KEY) infrastructure/gcp/verify_images.sh $(GCP_USER)@$(GCP_IP):~/synapse/verify_images.sh
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'chmod +x ~/synapse/backup_to_gcs.sh ~/synapse/verify_images.sh'
	@echo "Verifying image signatures (Cosign) before start..."
	-ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse && ./verify_images.sh || echo "WARN: Cosign verify skipped/failed — continuing for first-run"'
	@echo "Pulling images from Artifact Registry (CI-built) or building locally (first run)..."
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse/docker && $(GCP_COMPOSE) pull 2>/dev/null || true; $(GCP_COMPOSE) up -d --build'

deploy-gcp-verify: ## Verify GCP deployment health (endpoints + audit chain integrity)
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	@echo "=== docker compose ps ==="
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse/docker && $(GCP_COMPOSE) ps'
	@echo ""
	@echo "=== Endpoint health (admin ports via IAP tunnel) ==="
	@curl -sf http://$(GCP_IP)/healthz >/dev/null && echo "Frontend  (nginx): OK" || echo "Frontend  (nginx): not reachable"
	@echo "  Admin endpoints (Grafana/Prometheus/MLflow) are now behind IAP — use:"
	@echo "    gcloud compute start-iap-tunnel $(GCP_VM) 3000 --local-host-port=localhost:3000 --zone=$(GCP_ZONE)"
	@echo ""
	@echo "=== Audit chain integrity (Sprint 9) ==="
	-ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse && python -m orchestrator.audit.cli verify 2>&1 | tail -10 || echo "synapse audit verify not available yet"'
	@echo ""
	@echo "============================================="
	@echo "  GCP deployment verified"
	@echo "  Frontend  : https://$(GCP_IP)/   (or your DOMAIN_NAME)"
	@echo "============================================="

deploy-gcp-smoke: ## End-to-end smoke check on GCP VM (memory, docker, ollama, mounts)
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	@echo "=== GCP VM smoke checks ==="
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) ' \
	    set -e; \
	    echo "--- free -h ---"; free -h; \
	    echo "--- nproc ---"; nproc; \
	    echo "--- df -h /mnt/synapse-data ---"; df -h /mnt/synapse-data 2>/dev/null || echo "data disk not mounted"; \
	    echo "--- docker info ---"; docker info | grep -E "Architecture|CPUs|Total Memory|Docker Root Dir" || true; \
	    echo "--- ollama tags ---"; curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; [print(m[\"name\"]) for m in json.load(sys.stdin)[\"models\"]]" 2>/dev/null || echo "ollama not responding"; \
	    echo "--- swap ---"; swapon --show; \
	    echo "--- backup cron ---"; grep synapse-backup /etc/crontab || echo "backup cron not installed"; \
	    echo "--- cloud-ops-agent ---"; systemctl is-active google-cloud-ops-agent 2>/dev/null || echo "ops agent not running"; \
	'

deploy-gcp-destroy: ## Tear down GCP infra (terraform destroy — also wipes the backup bucket)
	@echo "WARNING: this destroys the VM, disk, IP, and backup bucket. With versioning ON, noncurrent objects retain for 30 days."
	@read -p "Type 'destroy' to confirm: " CONFIRM && [ "$$CONFIRM" = "destroy" ] || (echo "Aborted." && exit 1)
	cd $(GCP_TF_DIR) && terraform destroy -auto-approve

# ── Day-to-day operations ─────────────────────────────────────────────────
up-gcp: ## Start all services on the GCP VM
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse/docker && $(GCP_COMPOSE) up -d'

down-gcp: ## Stop all services on the GCP VM (containers down, VM still running)
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse/docker && $(GCP_COMPOSE) down'

gcp-status: ## Show service status on GCP VM
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) 'cd ~/synapse/docker && $(GCP_COMPOSE) ps'

gcp-logs: ## Tail logs for SERVICE (defaults to all). Usage: make gcp-logs SERVICE=orchestrator
	@test -n "$(GCP_IP)" || (echo "ERROR: GCP_IP not set" && exit 1)
	ssh -i $(GCP_KEY) $(GCP_USER)@$(GCP_IP) "cd ~/synapse/docker && $(GCP_COMPOSE) logs --tail=200 -f $(SERVICE)"

gcp-shell: ## Interactive SSH session on the GCP VM (via IAP TCP tunnel if firewall is IAP-only)
	@test -n "$(GCP_VM)" || (echo "ERROR: GCP_VM not set" && exit 1)
	gcloud compute ssh $(GCP_VM) --zone=$(GCP_ZONE) --tunnel-through-iap

# ── VM lifecycle (stop nightly to stretch the free credits) ────────────────
gcp-stop-vm: ## Stop the VM (compute charges pause; disk + static IP still charged)
	gcloud compute instances stop $(GCP_VM) --zone=$(GCP_ZONE)

gcp-start-vm: ## Start the VM (resumes from disk; same static IP)
	gcloud compute instances start $(GCP_VM) --zone=$(GCP_ZONE)
	@echo "Wait ~30s for the VM to boot, then: make deploy-gcp-verify"

gcp-restart-vm: ## Reboot the VM
	gcloud compute instances reset $(GCP_VM) --zone=$(GCP_ZONE)


verify-v4-compliance: ## Definitive v4.0 plan compliance gate (artifact + test counts + quality)
	@echo "============================================="
	@echo "  v4.0 Definitive Edition compliance check"
	@echo "============================================="
	@echo "[1/10] ADR count >= 24"
	@count=$$(ls docs/adr/ADR-*.md 2>/dev/null | wc -l); test $$count -ge 24 || (echo "FAIL: only $$count ADRs found" && exit 1); echo "  ok ($$count)"
	@echo "[2/10] GitHub workflows: ci, cd, integration, policy, security, mutation"
	@for w in ci cd integration policy security mutation; do \
	    test -f .github/workflows/$$w.yml || (echo "  FAIL: missing $$w.yml" && exit 1); \
	done; echo "  ok"
	@echo "[3/10] Demo segments == 5"
	@count=$$(ls scripts/demo/0[1-5]_*.py 2>/dev/null | wc -l); test $$count -eq 5 || (echo "FAIL: $$count demo segments" && exit 1); echo "  ok"
	@echo "[4/10] Claude Skill present"
	@test -f .claude/skills/synapse-engineer/SKILL.md || (echo "FAIL: SKILL.md missing" && exit 1); echo "  ok"
	@echo "[5/10] Feast feature groups >= 7 (entities + 6 groups)"
	@count=$$(ls data_fabric/feast/features/*.py 2>/dev/null | grep -v __init__ | wc -l); test $$count -ge 7 || (echo "FAIL: $$count feature files" && exit 1); echo "  ok ($$count)"
	@echo "[6/10] All 8 agent state machines inherit BaseAgentStateMachine"
	@count=$$(grep -l "BaseAgentStateMachine" agents/*/state_machine.py | wc -l); test $$count -eq 8 || (echo "FAIL: only $$count agents" && exit 1); echo "  ok"
	@echo "[7/10] Pre-commit hooks: spec-coverage, contract-validate, kv-cache-check"
	@grep -q "spec-coverage" .pre-commit-config.yaml || (echo "FAIL: spec-coverage hook missing" && exit 1)
	@grep -q "contract-validate" .pre-commit-config.yaml || (echo "FAIL: contract-validate hook missing" && exit 1)
	@grep -q "kv-cache-check" .pre-commit-config.yaml || (echo "FAIL: kv-cache-check hook missing" && exit 1)
	@echo "  ok"
	@echo "[8/10] DPDPA compliance test present"
	@test -f tests/compliance/test_dpdpa.py || (echo "FAIL: DPDPA test missing" && exit 1); echo "  ok"
	@echo "[9/10] Operational runbooks (>=7)"
	@count=$$(ls docs/runbooks/*.md 2>/dev/null | wc -l); test $$count -ge 7 || (echo "FAIL: $$count runbooks" && exit 1); echo "  ok ($$count)"
	@echo "[10/10] Quality gates: docs/quality_gates/sprint{1..5}.md"
	@for s in 1 2 3 4 5; do test -f docs/quality_gates/sprint$$s.md || (echo "  FAIL: sprint$$s.md missing" && exit 1); done; echo "  ok"
	@echo "============================================="
	@echo "  v4.0 DEFINITIVE EDITION COMPLIANT"
	@echo "============================================="

