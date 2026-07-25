---
inclusion: always
---

# Rule Authority — the CLAUDE/Claude-skill guidance is BINDING on Kiro

This repository's engineering law was authored for Claude. It applies to Kiro
**unchanged and in full**. There is no Kiro-specific dialect and no exemption.

## Precedence order (highest first)

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0** (local compute).
   Nothing below may be used to justify heating the laptop.
2. **`CLAUDE.md`** — the operating manual: the 14 invariants, the honesty
   contract, gate registry (C1..C60), the `E-S*` hard-won lessons, deploy-truth
   rules, and sprint precedent. Read it before proposing architecture, adding a
   gate, or touching audit/consensus/deploy paths.
3. `.claude/skills/synapse-engineer/SKILL.md` + its `references/`
   (`14_invariants.md`, `testing_topology.md`, `spec_schema.md`, `adr_index.md`)
   — the canonical engineering workflow.
4. `.cursorrules` and its `docs/cursor/*.md` reference docs — code conventions,
   agent pattern, domain models.
5. `docs/adr/ADR-*.md` — binding decisions for the areas they cover.

When two sources conflict, the higher-numbered authority wins and the conflict
must be surfaced to the user, never silently resolved.

## Non-negotiables carried over (summary — the files above are authoritative)

- **I-1 zero cost.** No paid API, SDK, or dependency. Ever. Never add `openai`,
  `anthropic`, `cohere` or similar; CI blocks them.
- **I-4 append-only audit.** Never UPDATE/DELETE audit rows. New facts go in new
  append-only tables (precedent: `decision_outcomes`). Never mutate
  `make_canonical_row` — the hash chain is byte-pinned.
- **I-7 honest degradation.** Never fabricate a result, a pass, or a model
  output. `DEGRADED`/`unknown`/`SKIP` are first-class states. A SKIP is not a
  PASS. Absence of proof is never a pass.
- **I-2, I-3, I-5, I-6, I-9, I-14** and the rest: reward isolation,
  schema-validated outputs, confidence-gated HITL, hard guardrails over learned
  policy, A2A-vs-MCP separation, append-only context.
- **Claims are mechanical.** Any number stated in docs must be derivable from a
  gate. If a fact is worth discovering twice, it is worth a gate
  (`scripts/audit/*`, `make verify-claims`).
- **Conventions.** Type hints everywhere (`mypy --strict`), Pydantic models,
  `structlog` never `print()`, canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`, jittered retries from
  `synapse_common.retry`, `encoding='utf-8'` on every `read_text` (E-S13-07),
  ASCII-only console output on Windows.
- **Spec-driven flow.** `spec.yaml` -> generated `test_spec.py` -> implement ->
  green -> commit.

## Operating requirement

Before any non-trivial change, consult the authority files for the area being
touched instead of inferring intent from surrounding code. Cite the invariant or
`E-S*` lesson that constrains the change when it is load-bearing. If a change
would violate one of them, stop and raise it rather than proceeding.

## Bound source files

#[[file:CLAUDE.md]]
#[[file:.claude/skills/synapse-engineer/SKILL.md]]
#[[file:.claude/skills/synapse-engineer/references/14_invariants.md]]
#[[file:.claude/skills/synapse-engineer/references/testing_topology.md]]
#[[file:.cursorrules]]
