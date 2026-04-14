#!/usr/bin/env bash
set -euo pipefail

# SYNAPSE Sprint 5 Load Testing Protocol
# Prerequisites: pip install locust

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${SYNAPSE_API_HOST:-http://localhost:8000}"
RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "${RESULTS_DIR}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "============================================="
echo "SYNAPSE Load Testing Protocol — Sprint 5"
echo "Target: ${HOST}"
echo "Timestamp: ${TIMESTAMP}"
echo "============================================="

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
