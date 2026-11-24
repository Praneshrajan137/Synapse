---
name: synapse-engineer
description: Cognitive entry point for engineers working on the SYNAPSE multi-agent quick-commerce supply chain platform. Loads the 14 invariants, the 24-ADR index, the 7-layer testing topology, and the spec.yaml schema into working memory so any agent editing this repo obeys the v4.0 Definitive plan. Use when a task touches agents/, orchestrator/, digital_twin/, data_fabric/, infrastructure/, or any of the 14 invariants.
---

# SYNAPSE Engineer Skill

## Purpose
This skill bootstraps a Claude coding session into the SYNAPSE v4.0 mental model
in a single cognitive step. Instead of re-reading the 1942-line plan every time,
the skill pulls the four reference files below into context and points at the
two production-grade automation scripts.

## When to invoke
- Any task that edits files under `agents/`, `orchestrator/`, `digital_twin/`,
  `data_fabric/`, `packages/synapse_common/`, `infrastructure/`, or
  `ml_pipelines/`.
- Any PR that claims "v4.0 compliant".
- Any Ralph loop iteration (`scripts/ralph/ralph.sh`).

## Read-first references
Load these in order before writing code — they are the minimum viable model:

1. `references/14_invariants.md` — the architectural guarantees. A PR that
   breaks I-1, I-2, I-3 or I-13 is rejected by CI; the pre-commit hooks
   (`pre-commit install`) run the same checks before a commit.
2. `references/adr_index.md` — the 24 ADRs with one-line summaries, so you
   can point at a decision instead of re-deriving it.
3. `references/testing_topology.md` — the 7 layers (SDD → Fuzz → Contract →
   Metamorphic → DbC → Oracle → Mutation) and which layer each test belongs
   to.
4. `references/spec_schema.md` — the `spec.yaml` schema. Every invariant in
   `spec.yaml` must have a test. Use `scripts/spec_gen.py` to scaffold them.

## Automation scripts
- `scripts/spec_gen.py` — generate a starter `spec.yaml` for a new agent with
  the canonical structure (SDD layer, invariants, rewards signature,
  contracts).
- `scripts/ralph_runner.py` — Python wrapper around `scripts/ralph/ralph.sh`
  that pipes `PROMPT.md` into Claude Code CLI with fresh context per
  iteration, appends results to `progress_<agent>.txt`, and exits on
  `<promise>COMPLETE</promise>`.

## Hard rules (enforced by CI; the pre-commit hooks run the same checks)
- **I-1 (zero cost)**: no paid API imports (`openai`, `anthropic`, `cohere`,
  `replicate`). CI blocks any paid-API string.
- **I-2 (reward isolation)**: `agents/X/training/rewards.py` MUST NOT import
  from `agents.Y.*`. CI's I-2 step enforces this; the `reward-isolation` hook
  runs it.
- **I-13 (KV-cache)**: the system prompt (`SYSTEM_PROMPT` in
  `orchestrator/llm/context_builder.py`) is string literals only, bound once,
  and every system message uses it; dynamic data goes in the messages after
  the prefix. The `kv-cache-check` hook enforces this (`hooks.yml` runs it).
- **I-14 (append-only context)**: never `del`, `.pop()`, `.remove()`, or
  reassign `context.messages`. `ContextMessage` is `frozen=True`.
- **ADR-016 (jitter)**: never a fixed-delay retry. Use
  `synapse_common.retry.retry_with_jitter`; a `time.sleep` that is not a
  retry (a period, a pace, a poll) says so with `# not-a-retry: <reason>`
  (the `jitter-enforcement` hook, run by `hooks.yml`).

## Conventions
- `mypy --strict` must pass.
- `json.dumps(obj, sort_keys=True, separators=(',',':'))` for every payload.
- `structlog` only for logging — never `print()`.
- Agents communicate A2A (JSON-RPC 2.0). Tools use MCP. Never conflate the
  two (I-9).
- Every new invariant needs a matching test in the agent's `tests/` dir.
- Every new ADR uses `docs/adr/template.md` (Michael Nygard format).

## Recitation
Long-horizon tasks must call `recite_objective()` every 10 tool calls
(ADR-024). The `BaseAgentStateMachine` in `packages/synapse_common/fsm.py`
implements this automatically — subclasses only set `ACTIVE_OBJECTIVE` and
`ACTIVE_CONSTRAINTS`.
