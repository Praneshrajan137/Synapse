#!/bin/bash
set -euo pipefail

# ─── SYNAPSE DEMO CHOREOGRAPHY (v4.0 §8.2) ──────────────────────────────────
# Usage: bash scripts/demo/run_demo.sh <city> <speed_factor>
#   city:         bengaluru | mumbai
#   speed_factor: 1.0 (real-time) | 2.0 | 3.0 (fast verification)
#
# Delegates to 5 numbered Python segments per v4.0 plan:
#   01_living_map.py   - establishing shot
#   02_ipl_signal.py   - demand surge induction
#   03_disruption.py   - crisis injection
#   04_debate.py       - consensus deliberation
#   05_evidence.py     - audit + twin + MLflow provenance
#
# E-S6-06: each segment polls Kafka consumer-group lag (not wall-clock).
# I-1: no paid APIs anywhere in the chain.
# ────────────────────────────────────────────────────────────────────────────

CITY="${1:?Usage: $0 <city> <speed_factor>}"
SPEED="${2:-1.0}"
KIND="${3:-warehouse_offline}"

if [[ "$CITY" != "bengaluru" && "$CITY" != "mumbai" ]]; then
    echo "ERROR: city must be 'bengaluru' or 'mumbai', got '$CITY'" >&2
    exit 1
fi

log() { echo "[demo:${CITY}] $(date +%H:%M:%S) $*"; }

log "═══════════════════════════════════════════════════════════════"
log " SYNAPSE Demo — City: ${CITY}, Speed: ${SPEED}x, Kind: ${KIND}"
log "═══════════════════════════════════════════════════════════════"

PYTHONPATH="${PYTHONPATH:-.}:." python scripts/demo/01_living_map.py "$CITY" "$SPEED"
PYTHONPATH="${PYTHONPATH:-.}:." python scripts/demo/02_ipl_signal.py "$CITY" "$SPEED"
PYTHONPATH="${PYTHONPATH:-.}:." python scripts/demo/03_disruption.py "$CITY" "$SPEED" "$KIND"
PYTHONPATH="${PYTHONPATH:-.}:." python scripts/demo/04_debate.py "$CITY" "$SPEED"
PYTHONPATH="${PYTHONPATH:-.}:." python scripts/demo/05_evidence.py "$CITY" "$SPEED"

log "═══════════════════════════════════════════════════════════════"
log " Demo complete — 5 segments, cost \$0 (I-1), E-S6-06 compliant"
log "═══════════════════════════════════════════════════════════════"
exit 0
