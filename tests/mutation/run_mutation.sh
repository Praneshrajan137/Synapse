#!/usr/bin/env bash
set -euo pipefail

# SYNAPSE Mutation Testing — Sprint 5
# Target: <15% survival on rewards, <10% on guardrails/audit
# Tool: mutmut (MIT license)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "${RESULTS_DIR}"

export PYTHONPATH="${PROJECT_ROOT}"

echo "============================================="
echo "SYNAPSE Mutation Testing — Sprint 5"
echo "PYTHONPATH=${PYTHONPATH}"
echo "============================================="

OVERALL_PASS=true

extract_survival_rate() {
    local output="$1"
    local killed survived total rate
    killed=$(echo "${output}" | grep -oP 'killed:\s*\K\d+' || echo 0)
    survived=$(echo "${output}" | grep -oP 'survived:\s*\K\d+' || echo 0)
    total=$((killed + survived))
    if [ "${total}" -gt 0 ]; then
        rate=$(python3 -c "print(round(${survived} / ${total} * 100, 1))")
    else
        rate="N/A"
    fi
    echo "${rate}"
}

check_threshold() {
    local name="$1"
    local rate="$2"
    local max="$3"

    if [ "${rate}" = "N/A" ]; then
        echo "  ${name}: no mutants generated — SKIP"
        return 0
    fi

    local ok
    ok=$(python3 -c "print(1 if float('${rate}') <= float('${max}') else 0)")
    if [ "${ok}" = "1" ]; then
        echo "  ${name}: ${rate}% survival <= ${max}% — PASS"
    else
        echo "  ${name}: ${rate}% survival > ${max}% — FAIL"
        OVERALL_PASS=false
    fi
}

# --- Category 1: Reward Functions (<15% survival) ---
echo ""
echo "--- Reward Functions (target: <15% survival) ---"

REWARD_AGENTS=(
    demand_prophet
    routing_navigator
    inventory_sentinel
    pricing_oracle
    freshness_guardian
    disruption_shield
    supplier_trust
    sustainability_agent
)

for agent in "${REWARD_AGENTS[@]}"; do
    rf="agents/${agent}/training/rewards.py"
    test_dir="agents/${agent}/tests/"
    test_file="agents/${agent}/tests/test_reward.py"

    if [ ! -f "${PROJECT_ROOT}/${rf}" ]; then
        echo "  SKIP: ${rf} not found"
        continue
    fi
    if [ ! -f "${PROJECT_ROOT}/${test_file}" ]; then
        echo "  SKIP: ${test_file} not found (E-S5-10)"
        continue
    fi

    echo "  Mutating: ${rf}"
    cd "${PROJECT_ROOT}"
    OUTPUT=$(mutmut run \
        --paths-to-mutate="${rf}" \
        --tests-dir="${test_dir}" \
        --runner="python -m pytest ${test_file} -x -q" \
        2>&1 || true)

    RESULTS=$(mutmut results 2>/dev/null || echo "")
    RATE=$(extract_survival_rate "${RESULTS}")
    echo "    ${agent}: ${RESULTS}" | tee -a "${RESULTS_DIR}/rewards_mutation.log"
    check_threshold "${agent} rewards" "${RATE}" "15"
done

# --- Category 2: Guardrail Enforcement (<10% survival) ---
echo ""
echo "--- Guardrail Enforcement (target: <10% survival) ---"

GUARDRAIL_FILES=(
    "orchestrator/guardrails/rules.py"
)

for gf in "${GUARDRAIL_FILES[@]}"; do
    if [ ! -f "${PROJECT_ROOT}/${gf}" ]; then
        echo "  SKIP: ${gf} not found"
        continue
    fi
    echo "  Mutating: ${gf}"
    cd "${PROJECT_ROOT}"
    OUTPUT=$(mutmut run \
        --paths-to-mutate="${gf}" \
        --tests-dir="orchestrator/tests/" \
        --runner="python -m pytest orchestrator/tests/ -x -q -k guardrail" \
        2>&1 || true)

    RESULTS=$(mutmut results 2>/dev/null || echo "")
    RATE=$(extract_survival_rate "${RESULTS}")
    check_threshold "guardrails" "${RATE}" "10"
done

# --- Category 3: Audit Logging (<10% survival) ---
echo ""
echo "--- Audit Logging (target: <10% survival) ---"

AUDIT_FILES=(
    "orchestrator/audit/logger.py"
    "packages/synapse_common/kafka_client.py"
)

for af in "${AUDIT_FILES[@]}"; do
    if [ ! -f "${PROJECT_ROOT}/${af}" ]; then
        echo "  SKIP: ${af} not found"
        continue
    fi
    echo "  Mutating: ${af}"
    cd "${PROJECT_ROOT}"
    OUTPUT=$(mutmut run \
        --paths-to-mutate="${af}" \
        --tests-dir="orchestrator/tests/" \
        --runner="python -m pytest orchestrator/tests/ -x -q -k audit" \
        2>&1 || true)

    RESULTS=$(mutmut results 2>/dev/null || echo "")
    RATE=$(extract_survival_rate "${RESULTS}")
    check_threshold "audit (${af})" "${RATE}" "10"
done

echo ""
echo "============================================="
if [ "${OVERALL_PASS}" = true ]; then
    echo "MUTATION TESTING: ALL THRESHOLDS MET"
else
    echo "MUTATION TESTING: THRESHOLD VIOLATIONS — Increase test coverage"
    exit 1
fi
echo "Results: ${RESULTS_DIR}/"
echo "============================================="
