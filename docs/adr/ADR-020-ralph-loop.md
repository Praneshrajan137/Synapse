# ADR-020: Spec-Driven Ralph Loop for Sprint Execution

## Status
Accepted

## Context
SYNAPSE v3 specifies *what* to build with 856+ lines of production-grade specifications and `spec.yaml` files with binary acceptance criteria. Manual Cursor AI prompt invocations create a bottleneck where the specification is autonomous but the execution is human-gated. The Ralph Wiggum workflow (Geoffrey Huntley, 2025) demonstrates that an external bash loop driving a coding agent with fresh context per iteration produces faster, more consistent results than a single long-running agent session — context degradation is the dominant failure mode in long sessions.

## Decision
Each agent implementation sprint executes as `scripts/ralph/ralph.sh <agent> <max_iterations>`. The loop:
1. Reads `agents/<name>/spec.yaml` (single source of truth).
2. Reads `scripts/ralph/progress_<agent>.txt` (append-only learnings log).
3. Pipes `scripts/ralph/PROMPT.md` into Claude Code CLI with fresh context.
4. The agent finds the highest-priority unmet invariant, implements ONE invariant, runs pytest+mypy+ruff.
5. On green: git commit with structured message and append to `progress_<agent>.txt`.
6. On red: log failure to `progress_<agent>.txt` without committing.
7. Exits when output contains `<promise>COMPLETE</promise>` or max iterations reached.

`CLAUDE.md` accumulates error patterns per Boris Cherny's "every mistake becomes a rule" principle. Makefile targets `ralph-<agent>` and `ralph-all` orchestrate the loops in critical-path order.

## Consequences
- Each iteration starts with maximum-quality context (no degradation from prior turns).
- ONE invariant per iteration → atomic commits, easy review and rollback.
- The loop runs outside the agent session, eliminating session timeout risks.
- Requires `claude` CLI installed and authenticated on the dev machine.
- `progress_<agent>.txt` files become a permanent record of the agent's learning curve.

## Alternatives Rejected
- **Manual Cursor prompting**: rejected — execution bottleneck.
- **Single long agent session**: rejected — context degradation.
- **Full autonomy without spec gates**: rejected — no acceptance criteria, no stop condition.
