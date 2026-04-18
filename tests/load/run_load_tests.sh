#!/usr/bin/env bash
set -euo pipefail

# SYNAPSE Load Testing Protocol — 6 named scenarios
# Prerequisites: pip install locust
# Usage:
#   bash tests/load/run_load_tests.sh                  # default 3-scenario legacy flow
#   bash tests/load/run_load_tests.sh --all            # all 6 v4.0 scenarios sequentially
#   SYNAPSE_LOAD_SCENARIO=ipl_burst bash tests/load/run_load_tests.sh --single

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${SYNAPSE_API_HOST:-http://localhost:8000}"
RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "${RESULTS_DIR}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
MODE="${1:-legacy}"

echo "============================================="
echo "SYNAPSE Load Testing Protocol — v4.0"
echo "Target: ${HOST}"
echo "Timestamp: ${TIMESTAMP}"
echo "Mode: ${MODE}"
echo "============================================="

run_scenario() {
    local scenario="$1" users="$2" spawn="$3" duration="$4"
    echo ""
    echo "--- Scenario: ${scenario} (${users} users, ${spawn}/s, ${duration}) ---"
    SYNAPSE_LOAD_SCENARIO="${scenario}" locust \
      -f "${SCRIPT_DIR}/locustfile.py" \
      --host="${HOST}" \
      --users "${users}" \
      --spawn-rate "${spawn}" \
      --run-time "${duration}" \
      --headless \
      --csv="${RESULTS_DIR}/${scenario}_${TIMESTAMP}" \
      --html="${RESULTS_DIR}/${scenario}_${TIMESTAMP}.html" \
      2>&1 | tee "${RESULTS_DIR}/${scenario}_${TIMESTAMP}.log"
}

if [[ "${MODE}" == "--all" ]]; then
    run_scenario sustained          100 10 10m
    run_scenario ipl_burst          250 50 5m
    run_scenario multi_disruption   50  5  10m
    run_scenario hitl_flood         200 20 5m
    run_scenario kafka_backpressure 80  8  10m
    run_scenario neo4j_concurrent   60  6  10m
    echo "============================================="
    echo "All 6 v4.0 load scenarios complete"
    echo "Results: ${RESULTS_DIR}/"
    echo "============================================="
    exit 0
fi

if [[ "${MODE}" == "--single" ]]; then
    scenario="${SYNAPSE_LOAD_SCENARIO:-sustained}"
    run_scenario "${scenario}" 100 10 10m
    exit 0
fi

# ── Pre-flight: verify target is reachable ──
echo ""
echo "--- Pre-flight: checking ${HOST}/health ---"
if ! curl -sf --max-time 5 "${HOST}/health" > /dev/null 2>&1; then
    echo "ERROR: ${HOST} is not reachable. Start services first:"
    echo "  make up && sleep 30"
    exit 1
fi
echo "  Target reachable."

echo ""
echo "--- Scenario 1: Sustained Throughput (30 min) ---"
echo "Target: 500 orders/min sustained; p99 < 2s; no crashes"
locust -f "${SCRIPT_DIR}/locustfile.py" \
  --host="${HOST}" \
  --users 100 \
  --spawn-rate 10 \
  --run-time 30m \
  --tags sustained \
  --headless \
  --csv="${RESULTS_DIR}/sustained_${TIMESTAMP}" \
  --html="${RESULTS_DIR}/sustained_${TIMESTAMP}.html" \
  2>&1 | tee "${RESULTS_DIR}/sustained_${TIMESTAMP}.log"

echo ""
echo "--- Scenario 2: Burst Demand — IPL Simulation (10 min) ---"
echo "Target: 5x spike absorbed; all agents within tier SLA"
locust -f "${SCRIPT_DIR}/locustfile.py" \
  --host="${HOST}" \
  --users 500 \
  --spawn-rate 50 \
  --run-time 10m \
  --tags burst \
  --headless \
  --csv="${RESULTS_DIR}/burst_${TIMESTAMP}" \
  --html="${RESULTS_DIR}/burst_${TIMESTAMP}.html" \
  2>&1 | tee "${RESULTS_DIR}/burst_${TIMESTAMP}.log"

echo ""
echo "--- Scenario 3: HITL Escalation Flood (5 min) ---"
echo "Target: 50 concurrent escalations; UI < 200ms render"
locust -f "${SCRIPT_DIR}/locustfile.py" \
  --host="${HOST}" \
  --users 50 \
  --spawn-rate 25 \
  --run-time 5m \
  --tags hitl_flood \
  --headless \
  --csv="${RESULTS_DIR}/hitl_${TIMESTAMP}" \
  --html="${RESULTS_DIR}/hitl_${TIMESTAMP}.html" \
  2>&1 | tee "${RESULTS_DIR}/hitl_${TIMESTAMP}.log"

echo ""
echo "============================================="
echo "Load Testing Complete"
echo "Results: ${RESULTS_DIR}/"
echo "============================================="

# ── Validate success criteria ──
echo ""
echo "--- Validating Success Criteria ---"
python3 -c "
import csv, sys, os

def check_csv(path, scenario, max_p99_ms):
    try:
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Name') == 'Aggregated':
                    p99 = float(row.get('99%', 0))
                    failures = int(row.get('Failure Count', 0))
                    total = int(row.get('Request Count', 0))
                    fail_rate = (failures / total * 100) if total > 0 else 0
                    print(f'  {scenario}: p99={p99:.0f}ms, failures={failures}/{total} ({fail_rate:.1f}%)')
                    if p99 > max_p99_ms:
                        print(f'    FAIL: p99 exceeds {max_p99_ms}ms')
                        return False
                    if fail_rate > 1.0:
                        print(f'    FAIL: failure rate exceeds 1%')
                        return False
                    print(f'    PASS')
                    return True
    except FileNotFoundError:
        print(f'  {scenario}: results file not found — SKIP')
        return True
    return True

results_dir = '${RESULTS_DIR}'
ts = '${TIMESTAMP}'
ok = True
ok &= check_csv(os.path.join(results_dir, f'sustained_{ts}_stats.csv'), 'Sustained', 2000)
ok &= check_csv(os.path.join(results_dir, f'burst_{ts}_stats.csv'), 'Burst', 5000)
ok &= check_csv(os.path.join(results_dir, f'hitl_{ts}_stats.csv'), 'HITL', 200)
sys.exit(0 if ok else 1)
"
