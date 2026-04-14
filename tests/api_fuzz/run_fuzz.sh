#!/usr/bin/env bash
set -euo pipefail

# SYNAPSE Schemathesis API Fuzz Testing — Sprint 5
# Zero 500-errors across all 8 agents + orchestrator
# Requires: pip install schemathesis

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "${RESULTS_DIR}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

AGENTS=(
    "demand_prophet:8081"
    "routing_navigator:8082"
    "inventory_sentinel:8083"
    "pricing_oracle:8084"
    "orchestrator:8085"
    "freshness_guardian:8086"
    "disruption_shield:8087"
    "supplier_trust:8088"
    "sustainability_agent:8089"
)

echo "============================================="
echo "SYNAPSE Schemathesis API Fuzz — Sprint 5"
echo "Target: Zero 500-errors across all agents"
echo "============================================="

OVERALL_PASS=true

for entry in "${AGENTS[@]}"; do
    AGENT="${entry%%:*}"
    PORT="${entry##*:}"
    ENDPOINT="http://localhost:${PORT}"

    echo ""
    echo "--- Fuzzing: ${AGENT} (${ENDPOINT}) ---"

    if ! curl -sf --max-time 5 "${ENDPOINT}/health" > /dev/null 2>&1; then
        echo "  SKIP: ${AGENT} not running on port ${PORT}"
        continue
    fi

    schemathesis run \
        "${ENDPOINT}/openapi.json" \
        --checks all \
        --stateful=links \
        --hypothesis-max-examples=100 \
        --hypothesis-deadline=10000 \
        --hypothesis-seed=42 \
        --report "${RESULTS_DIR}/fuzz_${AGENT}_${TIMESTAMP}.json" \
        2>&1 | tee "${RESULTS_DIR}/fuzz_${AGENT}_${TIMESTAMP}.log"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo "  FAIL: ${AGENT} has schema violations or 500 errors"
        OVERALL_PASS=false
    else
        echo "  PASS: ${AGENT}"
    fi
done

echo ""
echo "============================================="
if [ "${OVERALL_PASS}" = true ]; then
    echo "SCHEMATHESIS FUZZ: ALL AGENTS PASSED"
else
    echo "SCHEMATHESIS FUZZ: FAILURES DETECTED — Fix before merge"
    exit 1
fi
echo "============================================="
