# HANDOFF — decision-quality-proof

**State at end of session 7 (2026-09-11). Four commits pushed; the commit carrying this file is
the fifth.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At the time of writing that reported **142 leaf tasks: 66 done, 0 authored-pending-discharge, 76
open** — 70 authorable and **6** CI-gated. **Two leaves ticked (26.1 and 10.4), two registered
(26.4 and 26.5), and `pending: 0` for the first time in this spec's life.**

> **CHECKPOINT A RAN. THE MARGIN IS COMMITTED. AND THE MEASUREMENT FOUND THAT THE ARM LABELLED
> `perfect_foresight` LOSES TO THE INCUMBENT IT IS SUPPOSED TO BOUND.**
>
> Run `34570166681` (sha `e94a1ac`) then run `34574731853` (sha `2d86899`), both by the
> `measure-twin-regret` label, 200 of 200 replicates usable, `unusable_seeds: []`:
>
> | quantity | measured |
> |---|---|
> | `comparator_headroom` (A-C) | `8.937888952967558` — **unchanged from run `34366766968` to every digit** |
> | `mean_noop_cost` (A) | `11.835228527152536` |
> | `mean_foresight_cost` (C) | `2.897339574184977` |
> | `mean_reference_cost` (B) | `2.0849871282327` |
> | **`regret` (B-C)** | **`-0.8123524459522771`** |
> | 95% interval | `[-0.8273245113311902, -0.7977944274457321]` — **excludes zero** |
> | `margin_committed`, run 2 | **`0.4`** |
>
> **That is finding 54.** A negative regret means the difference is not a regret: arm C sits
> strictly between the other two, better than doing nothing and worse than `(s, S)`. Three
> candidate mechanisms were excluded before a fourth was accepted. Full record in **ADR-055
> D2.5.2**, landed this session.
>
> **Task 10.4 is `[x]`, discharged on run 2's own verdict — `margin_committed: 0.4` proves the
> value was re-derived from the rule and accepted by the headroom guard. Task 11 is deliberately
> still `[ ]`.**
>
> **E2c was NOT authored, and that is the session's most consequential decision.** The plan had
> approval to author all eleven leaves on an `inconclusive` verdict. Tasks 12.3 and 13.3 are the
> two flips that empty the insensitive set, and with them landed this same negative regret
> becomes **`sub-margin`** — the one verdict that **confirms** Finding 4. E2c is precisely the
> work that would convert this defect from a wrong verdict into a false confirmation.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree
as it *is*, not as a diff against how it was.

---

## The chain: still clear, and one red now has a landed repair awaiting CI

At HEAD `5f55d3a` (session 7's STEP 0), run `34505290388`:

| Job | Result |
|---|---|
| `ci.yml::quality-gates` | **`success`, 26 of 26 steps** — no regression from session 6 |
| `ci.yml::uplift-verify` step 5, fast | **`850 passed, 1 skipped, 28 deselected, 2 xpassed`, 0 failed** |
| `ci.yml::uplift-verify` step 6, slow | `1 failed, 59 passed, 936 deselected` — the one failure is `main`'s |
| `truth-gates.yml::truth-gates` | step 5 **failure** (`C44=FAIL, C69=FAIL`), **steps 6–12 skipped** |
| `truth-gates.yml::falsification-sweep` | steps 5 and 6 failure, pre-existing |

The slow step's single failure is
`test_reproduction_path_is_zero_cost_network_free_and_synthetic_only`, reporting
`paid client used: ['pinecone.Pinecone']`. **Session 7 landed the repair** (the
construction guard, commit `446d5d5`); **CI has not yet judged it**, and that property is
`@pytest.mark.slow`, so `ci.yml::uplift-verify`'s slow step owns the verdict.

**The registry baseline, read from step 5's own verdict line:**
`PASS=55 FAIL=2 PARTIAL=0 SKIP=10 TOTAL=67 REGISTERED=67`, failing on C44 and C69. C56 is
**absent from the failure list**, so C56 is PASS.

---

## Findings 51–55, and conflicts P and Q

### 51 — the three generator `--check` gates and `gate_surface --check` have never executed here

`truth-gates.yml` step 5 fails on the pre-existing C44/C69 registry red, and **steps 6–12 are all
`skipped` behind it**: C56 narrative-truth, `readme_gen --check`, `ledger_gen --check`,
`gate_surface --check`, blocking-steps propagation, `required_checks_truth` and
`sweep_budget_truth`. Nothing had noticed because the job's colour was already accounted for as
"predicted red".

**Why it matters for the owed regeneration:** the two gates that would verify it *cannot report on
this branch*. The surviving readings are `ci.yml::quality-gates` step 17 (C56) and a **local**
`gate_surface --check`. One pre-existing red was hiding the execution status of seven gates —
the "read what got SKIPPED behind a failure" habit paying out a fourth time.

### 52 — finding 50's construction site is misattributed, in four documents

`semantic_cache.py:39` reads `if api_key:` **before** its lazy `from pinecone import Pinecone`, so
`consensus_arm.py:655`'s `SemanticDecisionCache(api_key=None)` **constructs nothing**. The site
that did is `agents/disruption_shield/inference/playbook_retriever.py:95-101` — `pc = Pinecone()`
with **no key argument at all** — reached by `build_consensus_arm` →
`DisruptionShieldA2AHandler.__init__` → `DisruptionShieldPipeline()` → `PlaybookRetriever(...)`.
Finding 50 was derived from a **comment describing an intent**, not from the call path the
assertion names. **A citation is not a mechanism.**

### 53 — I-1 is enforced twice, by two different deny-lists

`security.yml:98` carries a second `No paid API imports (I-1)` grep. It **omits `replicate`**,
covers three trees instead of eight, and `required-checks.yaml:248-251` declares its job
**ineligible, reason `path-filtered`** (`**/requirements.txt`, `**/package.json`,
`**/Dockerfile`), so a commit touching none of those never produces it.

### 54 — the regret is negative: the oracle does not bound its subject

The headline finding, recorded in full at **ADR-055 D2.5.2** and task 11.

- **Three mechanisms excluded before a fourth was accepted**, and excluding them is what makes the
  survivor more than a guess. **Unequal footing** — excluded by construction: `run_three_pass`
  imports `observe`, `_apply_reorders` and `_derive_unit_costs` from `uplift/harness.py` and drives
  every arm on one cadence with one `restock_threshold`. **Lead time** — excluded:
  `_apply_reorders` applies stock through `sim.add_stock`, which is **instantaneous**. **The
  `Mapping[str, int]` truncation D2.5.1 records** — excluded, and *checked rather than assumed*
  because the ADR predicted an effect of the right order (~0.24 units) in the right direction: arm
  C is genuinely not routed through `_drive`.
- **The surviving explanation is a HYPOTHESIS with a named falsifier.** `stockout_rate` carries
  weight **8.0** — equal to `unmet_service`, eight times `on_hand` — and **ADR-055 D3 already
  records that its numerator counts SKUs at zero stock and "does not count unmet demand".**
  `ForesightPolicy.decide` orders the shortfall "no more, no less", driving on-hand to zero every
  window; `Par_Level_Reorder(s=50, S=100)` holds a 50–100 unit buffer. The objective charges the
  efficient arm 8.0 for being efficient. **The per-term decomposition was not measured**, so the
  falsifier is owed: report each arm's per-term contribution in `twin-regret.json`.
- **Why the D2.5.1 guard could not have caught it.** `headroom >= regret` substitutes to
  `(A - C) >= (B - C)`, which reduces to **`A >= B`** and is silent about C, because **C cancels**.
  A guard built from two expressions that share a term cannot constrain that term. **Nothing
  anywhere asserted `regret >= 0`.**
- **The refusal added.** `uplift/regret.py::negative_regret_refusal`, a module-level pure function
  so the path is provable by construction rather than only by never firing. `_measure` reports
  `status: unavailable` and exits 2, naming both arm costs. **Property 61** (8 tests, fast step)
  proves the hole is real: on the measured numbers with the committed margin, `classify_regret`
  returns `inconclusive` today and **`sub-margin`, whose `confirms_finding_4` is `True`**, with an
  empty insensitive set. Conflict M's defect forced `material`, which stops the spec loudly. **This
  one would have confirmed the premise quietly.**

### 55 — the I-1 deny-list is not fail-open; `pinecone` is outside I-1's scope
- **`CLAUDE.md` states I-1 as a closed list of four:** "NEVER import paid API clients (openai,
  anthropic, cohere, replicate) — CI blocks this (I-1)." `ci.yml:102` greps exactly those four, so
  the gate is a **faithful projection** of the invariant.
- **ADR-018 (Accepted) sanctions Pinecone and chose it for being free:** "Pinecone Starter (free)
  provides 2 GB / 5 indexes", naming both construction sites as the intended implementation.

Finding 50 conflated two rules. I-1 is about **paid** clients; the failing property asserts
**R9.2** — no paid or hosted SDK client may be **constructed** on a reproduction path — which is
why its `_PAID_CLIENT_TARGETS` also lists `boto3` and `ollama`. **And a text grep cannot answer
the property's question**: both sites are guarded lazy imports, and a grep matches the line
regardless of the guard.

### 56 — Property 61's own first draft was falsified by CI, and the defect was floating point

`uplift-verify` step **5** — the *fast* surface, `850 passed, 0 failed` all session — went red at
`446d5d5` on **one** test, mine, with step 6 skipped behind it. Hypothesis's counterexample at
CI's 500-example budget: `noop=0.0`, `reference=2.2722106724604736e-180`, `foresight=1.0`. Both
subtractions round to exactly `-1.0`, so `headroom >= regret` is **true** while
`noop >= reference` is **false**. **`(A − C) >= (B − C)` reduces to `A >= B` over the reals and
not over IEEE 754.**

**Repaired by correcting the claim's DOMAIN, not by adding a tolerance** (`Fraction`, where the
reduction is a theorem). And the repair exposed a second defect: once the reduction is exact, the
float branch that followed it became a **restatement** of the function's own contract. Its real
content was an **existence** claim — that the guard passing and the comparator being invalid are
simultaneously reachable — which a `@given` body cannot assert, so it is now made concretely on
run `34570166681`'s own arm means. Verified at `heavy` (100) then `ci` (500): 9 and 22 green.

**Third consecutive session in which `heavy` or `ci` failed what `dev` passed.** A scoped
pure-arithmetic file at 500 examples costs about five seconds.

### 57 — the construction guard is confirmed, and the assertion behind it is a false positive

Run `34578002704` (sha `4539b91`): step 5 back to **`success`**, and **step 6 RAN**.
**`guard.paid_client_attempts == []` passes for the first time since that property first
executed**, so the construction guard is verified by the job that owns the assertion rather than
by the probe that predicted it. Finding 52's walk to the constructor was right; there was no
second site.

**The next assertion fails instead:**
`real-data file read: ['.../site-packages/codecarbon/data/hardware/cpu_power.csv']` — a
dependency's **bundled hardware lookup table**, not a real, scraped or purchased dataset.

**The mechanism is one operator.** `_ZeroCostGuard._recording_open` reads
`if suffix in _DATA_SUFFIXES or under_data:`. The suffix clause alone flags any `.csv` **anywhere
on the filesystem**, so the declared `_REAL_DATA_DIRS` constant is **inert** — it can never be the
reason a path is recorded that the suffix clause has not already recorded. The assertion is about
file extensions rather than about provenance.

**This is the mirror of a shape this spec already carries.** "A level floor is a
tolerated-exception disjunct — assert a clause unconditionally" is about an `or` producing a false
**pass**; this is the same operator producing a false **failure**.

**Why it was never seen:** `paid_client_attempts` is asserted *before* `data_file_reads` in the
same test, so the property could not reach this line while the Pinecone construction stood.
**Fixing assertion N revealed assertion N+1** — the six-obstruction chain, now inside one test
function.

**Recorded, not repaired.** Another owner's file, and the repair is a judgement:
`... and under_data` would let a purchased CSV outside `data/` pass, which is a real narrowing and
is forbidden. **Do not weaken the property to make the job green (R2.10).**

### Conflict P — the pin count in the prompt's stop conditions is arithmetically impossible
It states `pin_extractor_truth` goes 14 → 15 → **16**. Three parked rows are in play, so it is
14 → 15 → **17**. As written the stop condition would have halted a correct session, and the halt
would have looked like a pin defect rather than a documentation defect.

### Conflict Q — the instruction to widen the deny-list contradicts authorities 2 and 5

The instruction was explicit and its cost accepted. It is not executed as given, and **the reason
is not the cost**: after the construction guard, neither site constructs a client without a
configured key, so a widened grep would report a violation **that does not exist** — a false
positive on a **required** check, blinding **13 steps** (14–26). A fail-open gate replaced by a
fail-loud-but-wrong one is not an improvement, and the `mutation-fast-required-job` precedent in
this repo's own pin table declines exactly this trade. **The construction guard was landed
instead**, which repairs the actual R9.2 violation without touching I-1's scope.

---

## What is still owed, and who owns it

- **Task 11's disposition, and it is the operator's.** Three options, costed in task 11: repair the
  objective's `stockout_rate` numerator so it counts unserved demand; replace `ForesightPolicy`
  with an arm that actually minimises the committed objective over the known trace; or **report
  the per-term decomposition first**, which is cheapest and is the falsifier the hypothesis needs
  before either repair is chosen. **The refusal makes the defect loud in the meantime; it does not
  expire on its own.**
- **E2c (11 leaves) is blocked behind that disposition**, for the reason in task 11: 12.3 and 13.3
  empty the insensitive set and turn this defect into a false confirmation.
- **Tasks 26.4 and 26.5**, registered this session: swap the two generator `--write` steps, then
  dispatch the regeneration and graduate the two `s`/`S` pins (15 → **17**).
- **Finding 45's stale C16 docstring** at `verify_claims.py:2406-2408`, which still calls the
  closed `stryker-break` hole live. **Its recorded reason for not being edited is measurably
  wrong:** the whole-table probe shows the 18 pins anchor to CLAUDE.md (9), ADR-055 (8) and
  `docs/state/CURRENT.md` (1) — **no pin anchors to `verify_claims.py`**, so `doc_truth` does not
  read it.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35).
- **CI's ruff scope** excludes nine trees: 530 lint, 254 format (upper bound).
- **Conflict O — CF-13's enforcement scope.** 41 files, 56 sites, none inside the checked inventory.
- **`scipy` is pinned in no requirements file** and arrives transitively (finding 41).

---

## Honesty ledger — verified vs merely authored

### Executed and measured, session 7

| What | Result |
|---|---|
| STEP 0 at the real HEAD (`5f55d3a`, 49 ahead) | `quality-gates` **26/26 success**; `uplift-verify` fast success, slow failure |
| The slow step's log, read for the failure | exactly **1 failed, 59 passed**, `pinecone.Pinecone`, still `main`'s |
| 26.1's four closure-parity test ids | read **individually** from the fast-step log, all `PASSED` |
| `truth-gates.yml` step list **and** step-5 log | steps 6–12 `skipped`; `PASS=55 FAIL=2 SKIP=10 TOTAL=67`, C44/C69 |
| Checkpoint A run 1 (`34570166681`) | **8/8 success**, `status: measured`, 200/200 usable |
| Checkpoint A run 2 (`34574731853`) | step 6 **failure** (refusal, exit 2), steps 7–8 ran, artifact uploaded |
| Predictions 1–5, written **before** the label | 1, 2, 3 confirmed; 4 did not fire; 5 confirmed by run 2 |
| `comparator_headroom` across two runs | `8.937888952967558` **to every digit** — arm A unperturbed by adding B |
| Run 2's `margin_committed` | **`0.4`** — the rule re-derived it and the headroom guard passed |
| Determinism of run 2 vs run 1 | every field identical; a materialisation, not a re-measurement |
| Anchor probe, validated **before** trusted | reported **zero** matches on the unamended ADR, then `'0.40'` on one line |
| Whole-table pin probe (18 rows, both sides) | **0** live document-side failures; 9 CLAUDE.md, 8 ADR-055, 1 CURRENT.md |
| `pin_extractor_truth` | **15 declared / 15 probed / 15 both sides**, exit 0 — the predicted 15 |
| `policy.py::materiality_margin` | `0.4` bare, and `0.4` with `measured_headroom=8.937888952967558` |
| The construction guard, behaviourally | unconfigured → `constructions=[]`; configured → `['pinecone.Pinecone']` |
| Property 61 | **8 tests green** at `dev`, including the `sub-margin`/`confirms_finding_4` clause |
| Bounded `pytest`, **2** invocations, serial, `dev` | **38 green** (8 + 13 + 17), then **13 green** after the precondition correction |
| `ruff check` | **0** on all four changed Python files |
| `ruff format` ownership | `test_materiality_margin_rule.py`'s deviation proven **PRE-EXISTING** by materialising HEAD's blob; **zero added** |
| `mypy --strict -m uplift.regret` | 6 errors, **all** in `uplift/fidelity.py` and `uplift/consensus_arm.py`; **zero** in the changed module |
| Ownership of those 6 | both files on `origin/main` with **empty** `git diff origin/main` |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0**, unchanged across all four commits |
| Census, predicted then measured | `140/64/2/74` → `140/65/1/74` → `140/66/0/74` → **`142/66/0/76`** |
| `task_claim_truth` | still exit **1**, same two `core-purpose-uplift` claims — no new claim created |
| Line endings / bytes | the `w/mixed` trap fired on **one** file, normalised to its dominant **worktree** ending (CRLF 157 vs LF 48); no BOM, no U+FFFD, no line over 100 chars |
| **`quality-gates` at `446d5d5`** | **`success`, 26 of 26** - the commit carrying the construction guard, so `agents/` was judged |
| CI's exact ruff commands, at CI's exact scope | `check` 0 and `format --check` **386 files already formatted**; the I-1 grep finds no matches |
| `uplift-verify` step 5 at `446d5d5` | **failure on ONE test, mine** (finding 56); step 6 skipped behind it |
| Property 61 after repair | **9 green at `heavy`**, **22 green at `ci` (500)** - the budget that found the defect |

**Budget, honestly counted.** **Two** bounded `pytest` invocations against a protocol figure of
three — the second was a re-verify after the designed precondition failure. **Two** `mypy --strict`
runs, both `-m uplift.regret`. No `pytest` at `heavy`, no repo-wide run, no `--cov`, no `-n auto`.
`ledger_gen`, `readme_gen`, `verify_claims` and `doc_truth` were **never run**; `doc_truth` was
imported for `documented_value` and `extract_source_values` as pure functions, which is the
sanctioned use. `tests/verify/test_ledger_gen_property.py` was never executed. No background
process was started. **Conflict T did not arise:** the seven-wave plan that would have needed six
to eight invocations stopped at four commits, so the protocol's figure of three was never
approached.

### NOT executed. Must not be claimed.

- **That `ci.yml::uplift-verify`'s slow step now passes.** It does not — but **not** for the reason
  it did all session. **The construction guard is CONFIRMED**: run `34578002704` (sha `4539b91`)
  has step 5 back to `success` and **step 6 RAN**, and `guard.paid_client_attempts == []` passes
  for the first time since that property first executed. The job is red on the **next** assertion,
  which is **finding 57** — a false positive over a dependency's bundled `cpu_power.csv`.
- **`quality-gates` at `daeb972` or `4539b91`.** Measured `success` at 26 of 26 at **`446d5d5`**,
  which is the commit that carries the construction guard, so `agents/` was judged. The two
  documentation commits after it were not read.
- **Task 11's verdict.** Refused, not measured — and that refusal is itself the finding.
- **The per-term decomposition of any arm's cost.** The `stockout_rate` hypothesis is inference
  from the weights plus ADR-055 D3's statement of the numerator, **not a measurement**.
- **That `Par_Level_Reorder(s=50, S=100)` reproduces the twin's endogenous restock.** Unchanged
  from session 5: unproven.
- **`mypy --strict` on any changed test module.** Not attempted; no CI step type-checks `tests/`.
- **`vitest`. At all.**

### The lesson from this session

**The instrument that can end this project was pointed at the wrong quantity for a second time,
in the opposite direction, and the guard installed to fix the first case was structurally
incapable of seeing the second.** Conflict M was "the verdict can only be `material`". This is
"the verdict would be `sub-margin`, and `sub-margin` is the one that **confirms** the premise".
The three-arm repair made `regret` and `comparator_headroom` different subtractions — which was
the right fix for conflict M — and left the oracle's own validity unasserted, because
`headroom >= regret` reduces to `A >= B` and **C cancels**.

**Two habits paid for themselves outright.** Writing five falsifiable predictions *before* adding
the label is what made a negative regret legible as a defect rather than as a number to interpret;
and probing the anchor as a pure function caught a defect **in the sibling pin**, because eight of
the fifteen pins anchor to the document I amended. **A document edit's blast radius is every pin
anchored to that document** — probing only the pin you are adding is finding 48 in a new place.

**And a citation is not a mechanism.** Finding 50 named a construction site read off a comment
describing an intent. The line constructs nothing; the real site was two modules away, behind a
lazy import, reachable only through the agent handler the consensus arm stands up.

---

## Environment notes and traps

- **`Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.** Use `*> $null`.
- **PowerShell 5.1's `ConvertFrom-Json` returns the array unenumerated.** Assign, then `foreach` —
  this fired again in session 7 and printed `System.Object[]` five times.
- **Complex inline `python -c` breaks on quoting.** Write a temp `.py` under `.tmp/` (git-ignored).
  There are no heredocs. Session 7 lost one call to a nested-quote `SyntaxError`.
- **An editor writing LF into a CRLF worktree file leaves `w/mixed`.** Normalise to the file's
  **dominant worktree** ending from Python at `newline=''`; the `i/` column is always `lf` here and
  cannot tell you what is on disk. `.tmp/normalise_eol.py` does it and reports the counts.
- **`mypy --strict` over `tests/**` exceeds a 120s budget**; `-m <dotted non-test module>` is fine.
  Mixing `scripts/audit/*.py` and `tests/**` in one invocation fails instantly.
- **`git push` writes progress to stderr**, so `$LASTEXITCODE` is non-zero on a **successful** push.
  Read the `old..new ref` line.
- **Identify a CI run by `head_sha`, NEVER by timestamp.**
- **A failing step's log does not always name the failing check**, and a job's colour is not a
  step's verdict. Read the step list, then the log.
- **`gh run download <id> -n <name> -D <dir>`** is cleaner than parsing a `| tee`'d log.
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks pre-existing errors.
- Python 3.14.0, mypy 1.19.1, pytest 8.4.2, hypothesis 6.151.11. `gh` 2.82.0.
  **Repository is PUBLIC — Actions minutes are unmetered on standard runners.**

---

## I-0 — the rule most likely to burn the machine

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`.**
`regenerate-truth-docs.yml` is the sanctioned route for the generators.

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, bounded scoped
`pytest`, `spec_ledger_census`, the six cheap gates, `command_path_truth` and `ratchet_truth` over
the committed tree, `replay_metrics` through its `measurers` seam, **`doc_truth.documented_value`
and `extract_source_values` as pure functions**, importing `verify_claims` for a constant, and
**`gh` API reads — free, and the highest-yield evidence in this repo.**

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — **ran in session 7, and returned a refusal rather than a verdict.** The
margin is committed and valid; the comparator it would be judged through is not. Task 11's three
dispositions are the operator's.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and the experiment must NOT be run.
**Blocked behind task 11's disposition**, because all four of task 13.7's measurements are regret
against the comparator finding 54 invalidated.

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves. **A number that cannot fail is
not a number, a verdict that cannot be anything else is not a verdict — and a regret measured
against a comparator that loses to its own subject is neither.**
