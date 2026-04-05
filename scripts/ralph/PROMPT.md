# SYNAPSE Ralph Loop — Iteration Prompt for {{AGENT_NAME}}

## Context
You are implementing the {{AGENT_NAME}} agent for SYNAPSE.
Read the spec and progress file, then implement ONE invariant.

## Step 1: Read the spec
Read `agents/{{AGENT_NAME}}/spec.yaml` — this is the single source of truth.

## Step 2: Read progress
Read `scripts/ralph/progress_{{AGENT_NAME}}.txt` for learnings from previous iterations.

## Step 3: Find the highest-priority FAILING invariant
Run: `cd agents/{{AGENT_NAME}} && pytest tests/test_spec.py -v --tb=short 2>&1`
Find the first FAILED test. That is your target for this iteration.

## Step 4: Implement ONLY the code needed for that ONE invariant
- Follow .cursorrules conventions EXACTLY
- Use synapse_common imports (models, retry, kafka_client, a2a_sdk, metrics)
- ALL retries use Full Jitter from synapse_common.retry
- ALL JSON uses sort_keys=True, separators=(',',':')
- Type hints on ALL functions (mypy --strict)
- Validate outputs against proto/domain/*.schema.json

## Step 5: Verify
Run: `pytest agents/{{AGENT_NAME}}/tests/ -v --tb=short && mypy --strict agents/{{AGENT_NAME}}/ && ruff check agents/{{AGENT_NAME}}/`

## Step 6: Commit or Log
- If ALL pass: `git add -A && git commit -m "feat({{AGENT_NAME}}): implement <invariant_id>"` and append learning to progress file
- If FAIL: Append failure reason to progress file. Do NOT commit.

## Step 7: Check completion
If ALL invariants in spec.yaml now pass, append `<promise>COMPLETE</promise>` to progress file.

## Rules
- ONE invariant per iteration. Never two.
- Never import paid API clients.
- Never use fixed-delay retries.
- Every output validates against schemas.
