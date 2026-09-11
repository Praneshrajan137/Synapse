---
inclusion: always
---

# Standard of Work — what "done well" means here, stated as tests rather than adjectives

The fourth steering document, and the one the set was missing. `local-compute-budget.md` says how
much, `execution-routing.md` says where, `throughput-with-integrity.md` says how fast and how
safely. **This says what good looks like** — and it is subordinate to all three.

## First, the clause that protects this document from itself

**Superlatives are not a standard.** "Highest quality", "world-class", "best possible" cannot be
failed, and this repository's own rule is that **a claim that cannot fail is not a claim**. Every
bar below is therefore written as something a piece of work can *fail*, and if a line here ever
reads as encouragement rather than as a test, it has decayed and should be deleted.

## THE BAR, as a test

> **Would a reviewer who has never met you, who is looking for the reason to reject this, accept
> it as the reference implementation others are pointed at?**

That reviewer asks three questions, always, and they are the only three that matter:

1. **"What would make this wrong?"** If the work does not name its own falsifier, it is an opinion.
2. **"How do you know?"** Measured, read, or inferred — say which. The three are not
   interchangeable and conflating them is the defect this project exists to remove.
3. **"What can I now do that I could not before?"** If the answer is only "a document says
   something new", the work has not landed.

## Intent before implementation

**Every change states the intent it serves and the observable that would show it failed to serve
it.** Not the mechanism — the *intent*, in the domain's language, and the thing that would prove it
hollow.

- A task's **Demo** line is that observable. **A Demo that could have been written before the work
  began is not a Demo** — it is a restatement of the title.
- Changing a gate? Name what it now catches that it did not, and what it still cannot see.
- Changing a document? Name the reader whose next decision changes.

## Tests passing is not the deliverable, and this repo already gates that

Your outputs, outcomes and behaviour are the deliverable. **This is not an aspiration here; it is
mechanised, and the four gates are the precedent to imitate:**

| Gate | What it refuses |
|---|---|
| **`oracle_truth`** (C61) | a test whose docstring promises a measurable outcome while the body asserts only scaffolding — its stopword list deliberately excludes `scenario`/`count` so a vacuous `assert n == 1000` grants no credit |
| **`uplift_truth`** (C60) | an artifact that self-declares `incomplete: true` being read as evidence |
| **`outcome_truth`** (C51) | a fabricated `status="confirmed"`; absent evidence must be `unknown` |
| **`substance_truth`** (C33) | guard-then-ignore: warn that a dependency is missing, then use the fallback anyway |

**Write the assertion about the outcome a reader cares about, in the domain's words.** Not about
the call that produced it. `test_the_design_and_the_inventory_declare_the_same_properties` is the
house style: a declarative sentence naming a claim, which is why the suite reads as specification.

## The methodology, stated honestly — audited 2026-09-11, not assumed

**Claiming a practice the tree does not have is the same defect as claiming a number no gate
derives.** So each is recorded at its measured level, with what to do about it.

| Practice | Level | The honest position |
|---|---|---|
| **Spec-driven** | **PARTIAL** | `scripts/generate_tests_from_spec.py` and the `ci.yml` schema gate are real. But category-3 invariants emit `pytest.skip` stubs — **a SKIP is not a RED**. What actually forces assertions onto invariants is `check_spec_coverage.py --threshold 99` (C31), after the substring reading reported 100% against an assertion-matched reality of **13.8%**. |
| **TDD / property-first** | **PARTIAL** | A 37-property inventory is mechanically enforced — but for **one** feature only, and **test-before-implementation is enforced nowhere.** Do not cite it as practice; cite the inventory, which is real. |
| **BDD** | **ABSENT** | No framework, no `.feature`, no given/when/then. **Do not introduce the vocabulary without the mechanism.** The behaviour-first *intent* is served by the declarative-sentence naming convention already in use. |
| **DDD** | **PARTIAL** | Each domain term is defined exactly once — the real win. But there are **two** model families (`SynapseBaseModel` and `uplift/interfaces.py`), no ubiquitous-language glossary, and the anti-corruption layer is over Feast/MLflow infrastructure, not between agents and the orchestrator. A2A-vs-MCP is a **protocol-role** boundary (I-9), not an ACL. |
| **Intent / outcome verification** | **PRESENT** | The repo's strongest practice: **67 registered checks** (C2–C75) plus an append-only `decision_outcomes` stream where absent evidence is `unknown`. **This is the standard to extend.** |
| **Claim → mechanism pinning** | **PRESENT** | `doc-number-pins.yaml` + `doc_truth` (C56) + `ratchets.json` (C70). Adding a pin is a **data edit**, which is what makes the sweep total rather than per-number. |

**When you want a practice the tree lacks, add the mechanism first.** A name without a gate is
decoration, and this project's history is a list of names that turned out to have no gate behind
them.

## Verifying your own information

- **Cite the mechanism, not the claim.** A citation is not a mechanism: read the code path the
  assertion names, not the docstring of the object that holds it.
- **Distinguish measured / read / inferred, in the sentence.** Then say what you could not check.
- **Prefer the instrument whose answer is structural over the one whose answer is textual.** A grep
  that finds a name is not a lookup that finds every caller.
- **Worked example, and it is live.** `verify_claims.py`'s own docstring says the check IDs are
  `C1..C25`; the file carries **67** decorators spanning **C2..C75**. A documented claim, in the
  registry's own module, that no gate derives. **That is the failure mode, in the file whose job is
  to prevent it.** Assume nothing is exempt.

## The thinking, as questions rather than as adjectives

- **First principles** — what is the *irreducible* constraint here, and which of the things I am
  treating as fixed is merely inherited? (I-0's real constraint is sustained load, not "tests".)
- **Systems** — what else reads this value? What *translates* it? Finding 48 cost a CI run because
  a schema change reached a registry row before it reached the table that renders verdicts.
- **Critical** — what would make this wrong, and can my new assertion fail at all? A tautology
  dressed as an assertion is the same defect as no assertion.
- **Algebraic** — what does this guard *reduce to*? `headroom >= regret` reduces to `A >= B`; the
  oracle cancels, so the guard could never constrain it.
- **Taste and design** — how much must a reader hold in their head to be sure this is right? Fewer
  moving parts beats more cleverness. **Prose is not free**, and a document nobody finishes is a
  document that does not govern.
- **Product** — whose next decision does this change? Work that changes no decision is inventory,
  not progress.

## Two failure modes this document exists to prevent

1. **Ambition recorded as achievement.** Writing "highest quality" and shipping the same work.
   The antidote is the reviewer test and the Demo line: both can fail.
2. **A standard that only ever passes.** If nothing has been rejected against this document, it is
   not being applied. Rejecting your own draft is the evidence that it works.
