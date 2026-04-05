#!/usr/bin/env bash
# ============================================================================
# SYNAPSE Ralph Loop — Spec-Driven Development Automation (ADR-020)
# Usage: ./scripts/ralph/ralph.sh <agent_name> <max_iterations>
# ============================================================================
set -euo pipefail

AGENT_NAME="${1:?Usage: ralph.sh <agent_name> <max_iterations>}"
MAX_ITERATIONS="${2:-20}"
PROGRESS_FILE="scripts/ralph/progress_${AGENT_NAME}.txt"
SPEC_FILE="agents/${AGENT_NAME}/spec.yaml"

if [ ! -f "$SPEC_FILE" ]; then
    echo "ERROR: ${SPEC_FILE} not found. Write the spec first."
    exit 1
fi

touch "$PROGRESS_FILE"

echo "SYNAPSE Ralph Loop — ${AGENT_NAME}"
echo "Max iterations: ${MAX_ITERATIONS}"

for i in $(seq 1 "$MAX_ITERATIONS"); do
    echo ""
    echo "--- Iteration $i / $MAX_ITERATIONS ---"

    if grep -q "<promise>COMPLETE</promise>" "$PROGRESS_FILE" 2>/dev/null; then
        echo "Agent ${AGENT_NAME} implementation COMPLETE."
        exit 0
    fi

    cat scripts/ralph/PROMPT.md | sed "s/{{AGENT_NAME}}/${AGENT_NAME}/g" > /tmp/ralph_prompt.md
    echo "Prompt prepared at /tmp/ralph_prompt.md"
    echo "Execute this prompt in Cursor AI Agent Mode, then continue the loop."
    echo "Press Enter when iteration is complete..."
    read -r

    echo "Iteration $i complete."
done

echo ""
echo "Max iterations ($MAX_ITERATIONS) reached for ${AGENT_NAME}."
echo "Check progress: cat ${PROGRESS_FILE}"
