#!/usr/bin/env bash
# SYNAPSE Schemathesis API Fuzz Runner
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
echo "Running Schemathesis against $BASE_URL/openapi.json"
schemathesis run "${BASE_URL}/openapi.json" \
    --checks all \
    --stateful=links \
    --max-examples=100 \
    --hypothesis-seed=42
