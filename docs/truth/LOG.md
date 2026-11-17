# docs/truth/LOG - the running record of session 2

Written so that a successor with none of this session's context can resume. Newest entries are
at the bottom of each section. Nothing here is a conclusion until `TRUTH-MAP.md` carries it with
its reproduction.

## How to read this file

Every statement carries one label:

| Label | Meaning |
|---|---|
| measured | a command run in this session produced it; the command is given |
| read | a file, pull request or page says it; not reproduced by this session |
| checked | an outside source opened by the main session itself, today |
| reported | a subagent's return, not yet re-checked by the main session |
| inferred | reasoning from the above |
| hypothesis | a claim with a stated way to prove it false, not yet tested |
| unknown | named and not yet known |

Baseline for every measurement unless another is named: the working tree on branch
`docs/knowledge-base` at `c1277f5`, which is `origin/main` `d4f985c` plus 24 files under
`docs/knowledge/` (measured: `git diff --stat origin/main...docs/knowledge-base`).

## State of the session

- **2026-11-17, at the close of the session's work.** The deliverables are committed on
  `docs/truth-session-2`: `OPENING.md`, this log, `TRUTH-MAP.md`, `FRONTIER.md`, `DIRECTION.md`,
  `DECISIONS.md`, the instruments in `docs/truth/instruments/`, and `docs/knowledge/VERDICTS.md`
  with pointers from the knowledge base. Nothing pushed. Decision D-08 below explains why the
  instruments were not moved to `scripts/truth/`.
- **2026-11-17, after the gate.** The operator answered the gate's four questions (see "The
  operator's answers"). Branch `docs/truth-session-2` was cut from `docs/knowledge-base` at
  `c1277f5` and the opening and this log were committed first. Window 1 of five is under way:
  the release path, what exists only off `main`, and one decision traced.
- **2026-11-16, before the gate.** Nothing in the repository had been changed. The only files
  written were under `docs/truth/`, uncommitted. No branch cut, no commit, no push, no fetch.
- Reads of outside services so far: GitHub through `gh` (pull-request list and bodies, workflow
  run lists, issue list and two issue bodies, repository visibility, one run's job list and its
  9 KB artifact downloaded to a temporary folder) and `git ls-remote origin`; five research
  subagents on the public web; four pages fetched by the main session. All read-only.
- One reviewer with fresh context was given only `OPENING.md` and this file and asked to
  reproduce a sample and attack the reasoning. Its findings are under "Review before the gate".
- **Next step:** whatever is first open under "Open questions, in order".

## The operator's answers (2026-11-17)

- **OA-1 The cloud account of June was a different account and expired long ago.** This
  confirms H-01: no VM, registry or identity pool from that deployment exists. The release
  environment must be built from nothing.
- **OA-2 The $300 is on a new account, not yet connected to this project, with its full
  credit.** The trial terms admit only new customers and let the provider end a trial at any
  time (EX-01). That stays on the risk list for the release date; it is the operator's matter.
- **OA-3 Credit may be spent before the release**, on deployment tests and a rehearsal, with
  every machine turned off straight after each use. When to use it is left to this program's
  judgment.
- **OA-4 The reviewers are to judge the work as a whole**, not the agents alone and not the
  proof harness alone. Every layer is therefore held to one height (question A, answered in
  part: who the reviewers are and what they were promised remain unknown).
- **OA-5 A belief to check.** The operator said the VM, GPUs and the rest would use the whole
  credit in five days. This session's figures say about $40 for five days of the planned VM
  (reported, from a third-party price table), no GPU appears in the plan read so far, and a
  trial account cannot attach one (reported). To be re-priced from a primary source and the
  Terraform read for any GPU before this is stated as a finding.
- **OA-6 The thirteen decisions (2026-11-17, answered through multiple-choice questions in the
  session).** D-1 no external user: the reviewers are the audience and the first screen leads
  with the proof. D-2 incumbent first. D-3 replenishment and disruption response. D-4 both
  limits. D-5 retire by experiment. D-6 move the history out of `CLAUDE.md`. D-7 the merge
  order approved. D-8 the thin slice. D-9 waste by age plus skewed demand fitted to
  FreshRetailNet-50K. D-10 the map by cell. D-11 stay on the trial, with no upgrade and no
  fallback host. D-12 view free, sign in to act. D-13 the facts made mechanical as proposed.
  The full record is at the top of `DECISIONS.md`.
- **The gate.** The reply answered every question of section 12, left the remaining choices to
  this session's judgment and objected to nothing. It is taken as approval of the seven
  defaults in section 11 of `OPENING.md`. Everything done under them is local and reversible:
  `git checkout docs/knowledge-base; git branch -D docs/truth-session-2` removes this session's
  commits.

## How to resume

1. Read `OPENING.md`, then this file from "Measurements".
2. Re-run M-14 and compare the two digests, to confirm nothing moved while the session was away.
3. Take the first open item under "Open questions, in order".
4. Subagents: at most three at a time, each with a stated cap on calls (see D-03).

## Decisions of this session

- **D-01 (2026-11-16). Measure against `origin/main`, not local `main`.** Local `main` is 125
  commits behind (M-01). Reason: local `main` predates the whole decision-quality-proof merge.
- **D-02 (2026-11-16). Pre-gate work is reconnaissance, not the audit.** Enough reading and
  measuring to write an opening that already holds verified surprises; the deep mapping, the
  runs and the fault injection wait for approval. Reason: the gate governs change, and usage on
  the plan is finite, so the expensive part should follow the operator's go-ahead.
- **D-03 (2026-11-16). Subagents go out at most three at a time, with a cap on calls.** Reason:
  M-15. Five research threads launched together exhausted the plan's five-hour limit before any
  had returned. The same lesson is already recorded for this project as steering rule G8
  (read, `HANDOFF.md` on `origin/main`: batches wider than five finished 4 of 18 agents).
- **D-04 (2026-11-16). Worktrees and other branches are read in place and never written.** All
  commands against them use `git -C <path>` or read files. No test is run inside another
  worktree, because a test run writes caches there.
- **D-05 (2026-11-16). `docs/truth/` names no person and no network address.** The repository is
  public. Run identifiers are cited by number, not by URL.
- **D-06 (2026-11-17). No cloud resource is created or touched in session 2**, although OA-3
  allows spending. Reason: nothing a truth session must learn needs a cloud machine; the new
  account is not connected; connecting it needs the operator's own sign-in. The first cloud use
  belongs to the implementation session that rebuilds the deploy path, and `DIRECTION.md` will
  propose the schedule of uses and their cost.
- **D-08 (2026-11-17). The instruments stay in `docs/truth/instruments/` and were not moved to
  `scripts/truth/`, departing from approval 3's default.** Reason: they run against exported
  trees of an unmerged branch and import its modules; placed under `scripts/` they would enter
  the repository's lint, type and gate runs on the next merge and fail there for reasons that
  have nothing to do with the product. Their useful form is a fast local proof check, proposed
  for session 4 (`DECISIONS.md`, D-13). Reversible: a move is one commit.
- **D-07 (2026-11-17). Code from an unmerged branch is run from an exported copy, never in its
  worktree.** `git archive <commit> | tar -x -C <temporary folder>` writes nothing to the
  repository, and the project's `.venv` runs it with `PYTHONPATH` pointing at the copy.

## Measurements

Scripts for M-03 to M-05 are in `docs/truth/instruments/` (uncommitted copies; the gate proposes
a proper home). Run them with any Python 3.11 or later, from the repository root.

- **M-01 Baseline (measured).** `origin/main` is `d4f985c`, dated 2026-11-01, "Merge PR #85".
  Local `main` is `045f44c`, dated 2026-07-25, 125 commits behind. `git ls-remote --heads origin`
  on 2026-11-16 returned the same heads as the local remote-tracking refs for `main` and the four
  open branches, so no fetch was needed.
  `git rev-parse --short main; git rev-parse --short origin/main;
  git rev-list --left-right --count main...origin/main`
- **M-02 History (measured).** 364 commits on `origin/main`, 527 on all refs, first commit
  2026-04-06, 29 tags of which 27 are `archive/*`.
  `git rev-list --count origin/main; git rev-list --count --all; git tag | wc -l`
- **M-03 Size (measured).** 2,121 tracked files, 384,345 text lines.
  `python docs/truth/instruments/inventory.py .`

  | Kind | Files | Lines |
  |---|---|---|
  | Python source | 441 | 100,785 |
  | Python tests | 444 | 112,784 |
  | TypeScript source | 278 | 35,684 |
  | TypeScript tests | 165 | 22,880 |
  | Markdown | 192 | 50,434 |
  | YAML | 170 | 21,410 |
  | JSON | 281 | 10,375 |
  | Lockfiles | 4 | 19,663 |

- **M-04 Size by role, Python source lines (measured, same script).**

  | Role | Paths | Lines |
  |---|---|---|
  | Decision core | `agents` 14,092; `orchestrator` 8,984; `packages/synapse_common` 6,753; `digital_twin` 3,966; `api` 3,645; `data_fabric` 2,174; `ml_pipelines` 1,334 | 40,948 |
  | Proof harness | `uplift` | 18,375 |
  | Audit gates | `scripts/audit` (38 files) | 32,743 |
  | Tests of the core | beside the code under `agents`, `orchestrator`, `packages`, `digital_twin`, `api` 37,796; top-level `tests/` other than `uplift` and `verify` 7,594 | 45,390 |
  | Tests of harness and gates | `tests/uplift` 32,100; `tests/verify` 34,474 | 66,574 |
  | Console | `frontend/src` source 24,278, tests 14,726 | 39,004 |
  | Console's effectiveness harness | `frontend/spec` source 9,073, tests 4,314 | 13,387 |

  The whole `frontend` directory holds 34,684 lines of TypeScript source; an earlier draft gave
  that as the console's size. `inventory.py` counts `frontend/spec` as source where `history.py`
  counts it as tests: the two instruments disagree there, and one rule must be chosen before
  they are committed.

  Also: 20 workflow files with 6,861 lines of YAML; 58 files in `docs/adr`; 24,622 lines of
  markdown under `.kiro/specs`. Each of the eight agents is between 1,325 and 3,004 source lines.
  Harness plus gates (51,118 lines) is larger than the decision core they examine (40,948).
- **M-05 Where the added lines went (measured).**
  `python docs/truth/instruments/history.py . origin/main` and `... . 045f44c..origin/main`

  | Class of path | All 326 non-merge commits | The 122 since `045f44c` (dated 2026-08 to 2026-11) |
  |---|---|---|
  | Core source | 13.2% | 5.7% |
  | Console source | 9.1% | 2.5% |
  | Core tests | 13.5% | 8.5% |
  | Console tests | 9.0% | 5.9% |
  | Proof harness and its tests | 23.3% | 38.7% |
  | Gates, CI, state documents | 13.1% | 20.5% |
  | Documents and specs | 12.8% | 17.6% |
  | Infrastructure and deploy | 3.3% | 0.3% |

  Shares are of added lines, lockfiles excluded. In the later period 25 of 122 commits touched
  core or console source. Limits of this measure: the classes are path prefixes chosen by this
  session; an added line is not a unit of effort or of value; squashed commits hide their dates
  (July shows 4 commits and August 7, carrying tens of thousands of lines).

  Biases named by the fresh reviewer, all accepted. The later window begins where the
  decision-quality-proof spec began, so it is circular as evidence that the project "turned" to
  proof: that period was chartered to produce a harness. All of `.github/` counts as gates,
  deploy workflows included, which inflates gates and deflates infrastructure. Every document
  counts as "documents", including ADRs that describe the core. Working the other way,
  `orchestrator/audit`, `orchestrator/guardrails` and the provenance and invariant modules of
  `synapse_common` count as core. The fair headline is the whole history: 22.3% core and
  console source against 49.2% harness, gates and documents.
- **M-06 Pull requests (measured, `gh pr list --state all --limit 40`).** Open: #87
  `fix/consensus-reads-request` (+2725 -94, 36 files, checks green, mergeable, last updated
  2026-11-02); #91 `feat/pathway-probe-trace`, stacked on #87; #90 `fix/owed-gate-defects`; #89
  `fix/frontend-gates`. Merged on 2026-11-01: #84 and #85. Before those, the last merge to
  `main` was #80 on 2026-07-23.
- **M-07 Worktrees and loose state (measured, `git worktree list`, `git -C <wt> status --short`,
  `git stash list`).** Seven worktrees: five under `.claude/worktrees/` and two under
  `.gl_scratch/`. `ledger` (branch `docs/dqp-session-13`, equal to `origin/main`) holds four
  modified, uncommitted files: `tasks.md`, `HANDOFF.md`, `NEXT_SESSION_PROMPT.md` and
  `SESSION_PROTOCOL.md` of the decision-quality-proof spec. They are the only record of that
  spec's session 13 and still contain unfilled `<<EXECUTOR: ...>>` placeholders.
  `frontend-gates` holds 20 uncommitted changes. One stash exists, on
  `feat/gcp-primary-deployment`. The four `ledger` files as read on 2026-11-16, by sha256
  prefix: `tasks.md` `794b691a20fa8f1c` (8,162 lines); `HANDOFF.md` `1180663b8aef0aaf` (220
  lines, 15 of them holding a placeholder); `NEXT_SESSION_PROMPT.md` `cc60f0c100e32ac6`;
  `SESSION_PROTOCOL.md` `9acbb06f1c6b9fec`. A different prefix means the file has moved on and
  RD-01 to RD-03 must be read again.
- **M-08 Deploy and watchdog (measured, `gh run list --workflow cd-gcp.yml --limit 100`,
  `gh run list --workflow live-truth.yml --limit 200`, `gh issue list --state open`).**
  - `cd-gcp.yml`: the last run whose deploy job succeeded is 27505645209, 2026-06-14T16:51Z at
    `3f84c32`. From 2026-06-15 a push builds and signs only: the eight successful runs of
    2026-06-16 to 2026-06-19 all show the job "Deploy to GCE VM (IAP)" as skipped. All 22
    scheduled runs on record failed, the first on 2026-06-22. The 28 newest runs all failed, including the scheduled run
    of 2026-11-16. (`gh run view <id> --json jobs` per run; `gh run list --event schedule`.)
    An earlier draft of this entry gave 2026-06-19 as the last deploy, reading a green
    build-only run as a deploy; the fresh reviewer caught it.
  - The newest run, 43874415454 of 2026-11-16: all 12 build legs fail at the step "Authenticate
    to GCP via Workload Identity Federation"; the deploy job is skipped. The error returned by
    the provider is `invalid_target`: "This might either be because the pool or provider is
    disabled or deleted or because it doesn't exist." (`gh run view 43874415454 --log-failed`)
  - `live-truth.yml`: 26 runs since 2026-06-11, 26 failures, no success on record. The oldest
    run failed at the step "VM must be RUNNING inside the up-window"; the newest at
    "Authenticate to GCP via Workload Identity Federation". No run on record reached an
    assertion about the system, so the watchdog has reported a schedule and a credential, never
    the system. It was already failing on 2026-06-11 to 2026-06-14, while deploys still worked.
  - Open issues opened by automation: seven `sev1 deploy-failure` (#75, #78, #81, #82 and #83
    from 2026-07-06 to 2026-07-25; #86 and #88 from 2026-11-01) and one `sev1 live-truth` (#76,
    2026-07-06, without a comment); and seven `sev2 eval-regression` titled "LLM judge nightly
    regression: score=" with no score, from 2026-05-28 to 2026-06-06.
- **M-09 The twin's seeded store (measured, file read).** `digital_twin/simulation/engine.py:904`
  seeds `{f"sku_{i}": 100.0 for i in range(10)}` when no opening stock is supplied; `:703` draws
  the demanded item with a uniform `choice` over the stocked items. Whether any scenario cell or
  world source changes the assortment or the mix: unknown (R-59).
- **M-10 Reversibility (measured, text search).** `reversib|irreversib|undo|compensat|rollback`,
  case-insensitive, over `orchestrator/**/*.py`: one match, a `rollback` method on a test double
  (`orchestrator/tests/test_audit_logger.py:77`).
- **M-11 The project's own agency audit (measured).**
  `.venv/Scripts/python.exe scripts/audit/agency_truth.py` reports: five of five structural loop
  invariants hold; "8 agent(s) reach an actuator or event source", none a stub; arbitration
  selects through `select_binding_action`. It also reports "Behaviour (NOT PROBED): UNAVAILABLE",
  eight agents unclassified, and no actuating baseline recorded. So the statement in `CLAUDE.md`
  that six of eight `execute()` methods do not act is out of date against this audit, and no
  recorded run shows any agent's `execute()` changing the world.
- **M-12 Machine and tools (measured).** `.venv` holds Python 3.11.15; the system has 3.14 and
  3.12. Node 24.11.0, pnpm 10.20.0, uv 0.10.9, GNU Make 4.4.1, gh 2.82.0. Docker 29.9.2 and
  Compose v5.6.1 are installed; the Docker engine was not running when measured. The laptop has
  15.7 GB of memory (4.5 GB free when measured), 8 cores and 12 threads, and 183.7 GB of free
  disk. The release VM type has 32 GB.
- **M-13 Console surfaces (measured, `frontend/src/app` route table).** Fourteen routes besides
  `/login`: the index, `cockpit`, `decisions`, `decisions/:id`, `council/:id`, `audit`,
  `agents`, `agents/:name`, `twin`, `markets`, `ingress`, `demo`, `steering`, `operations`.
  Twelve surfaces if a detail page is counted with its list.
- **M-14 The unchanged-proof baseline (measured, 2026-11-16).**
  `git for-each-ref --format='%(objectname) %(refname)' | sha256sum` begins `57d932cbfc359db2`
  over 125 refs. `git ls-remote origin | sha256sum` begins `33be221323372c56`.
  `git status --short` showed only `?? .kiro/settings/` before `docs/truth/` was written.
- **M-15 Usage (measured, by its failure).** Five research subagents started together, with the
  main thread working beside them, hit the plan's five-hour limit before any returned. They were
  resumed after the reset in waves of three and two, each capped at six further calls.

- **M-16 The pathway trace, read from the project's own CI artifact (measured).** Workflow
  "SYNAPSE Uplift Cost Probe", run 43630594693 on 2026-11-14 at `1c484fb` (PR #91), conclusion
  `success`. `gh run download 43630594693` to a temporary folder; `probe-trace.json`, sha256
  beginning `767a5f47ed39c31c`; `cost-probe-e5.json` beside it.
  - The Inventory Sentinel bound 15 of 15 recorded decisions: three observations, each as the
    full request, its replay and three variants with one input withheld. The artifact's own
    prediction P1 reads "held".
  - Six agents returned a proposal in every traced decision: demand_prophet, routing_navigator,
    inventory_sentinel, disruption_shield, supplier_trust, sustainability_agent. Pricing Oracle
    and Freshness Guardian returned none.
  - In the first traced decision the proposals carried (confidence, utility): inventory_sentinel
    (0.898, 0.898); demand_prophet, routing_navigator and sustainability_agent (0.5, 0.5);
    disruption_shield (0.5, 0.3); supplier_trust (0.189, 0.3). Four of six carry confidence
    exactly 0.5. Whether those are defaults is inferred from the round values, not read in code.
  - The Sentinel ordered nothing in all twelve traced variants. For the first item traced: on
    hand 143, order-up-to level q* 26.7, mean landed lead time 134.8 minutes. The ledger records
    the tuned control's levels as 118 to 183 (RD-02's source).
  - The E5 path measured 72 decisions, all `tier_2`, all dispatched, at a mean of 0.0209 s each.
  - Scope: three probe states at one seed. It does not show which agent bound each of E5's
    24,000 decisions.

- **M-17 The gate surface (measured by count, results read).** `scripts/audit/verify_claims.py`
  defines 68 check functions. `README.md:33` states that `make verify-claims` reports
  "56 PASS / 0 FAIL / 0 PARTIAL / 12 SKIP / 68 TOTAL". This session has not run the suite.

### Window 1 (2026-11-17): decisions traced on the repaired tree

How these were run (D-07). The tree of PR #91 (`1c484fb`, which is PR #87 plus the trace) was
exported with `git archive 1c484fb | tar -x -C <folder>`. From that folder, with
`PYTHONPATH=<folder>;<folder>/packages` and the project's `.venv` Python 3.11:
`python -m scripts.diagnostics.pathway_trace --output <file>` for M-18, and the three scripts
in `docs/truth/instruments/` (`scan_binding.py`, `scan_shocked.py`, `scan_paired.py`) for M-19
to M-21. All use the E5 consensus arm exactly as E5 builds it (`uplift.e5_suite.
e5_consensus_policy`, reorders only) and the primary-cell twin (`e5_world`).

- **M-18 The pathway trace reproduces on this laptop, byte for byte (measured).** The local
  `probe-trace.json` has sha256 prefix `767a5f47ed39c31c`, equal to the CI artifact of M-16;
  `cmp` reports no difference. So the repaired decision path runs here in under a minute, and
  the trace is deterministic across a Linux runner and this Windows machine. A recorded working
  rule that no simulation runs locally (read, `HANDOFF.md`) does not hold for runs of this size.
- **M-19 Unshocked: one agent binds every decision (measured, 360 decisions).** Five seeds (296,
  1, 2, 3, 4), 24 hourly decisions each, under three ways of driving the world: the probe's own
  ordering schedule, no ordering at all so that stock falls to zero, and a closed loop in which
  the arm's own orders are placed.
  - Binding agent: `inventory_sentinel` in 360 of 360. Tier: `tier_2` in 360 of 360. All
    dispatched. Mean time per decision 0.02 s.
  - Six agents propose in every decision. Five of them returned one constant value across all
    360 decisions, whatever the state of the world: `demand_prophet`, `routing_navigator` and
    `sustainability_agent` utility 0.5; `disruption_shield` and `supplier_trust` utility 0.3.
    Only the Sentinel's score moved (0.850 to 0.973; 65 distinct values at seed 296, 221 over
    the other four seeds).
  - `pricing_oracle` and `freshness_guardian` proposed in none.
  - In the closed loop stock still reached zero for some item at every seed.
- **M-20 Shocked: the full path chooses the same agent (measured, 12 decisions), and a
  retraction.** Setting an observation's `active_shock`, with all multipliers at 1.0 so that
  only the flag differs, routes it to `tier_4`. Seed 296, twelve hourly decisions in a closed
  loop: `inventory_sentinel` bound 12 of 12; one debate round each; a recorded front of six
  members; none escalated. Debate lowered the Sentinel's score (first decision 0.85 to 0.671)
  and left the five constant scores untouched.
  **Retracted:** the first version of this entry, committed in `0741ba8`, gave a mean of 24.2 s
  per decision and concluded that the full path was about 1,200 times slower and that a shocked
  cell would take about 160 hours. That timing was an artifact of this session's instrument.
  The script had no `__main__` guard, and on Windows the twin's worker processes start by
  re-importing the main module, so each worker re-ran the whole scan before doing its work.
  The paired run showed it by printing its results three times. The scripts are corrected and
  the valid timing is in M-21.
  A re-run of the twelve-decision scan with the guarded script did not finish within ten
  minutes and was stopped; no process was left behind. Its counts above come from the first
  run and do not depend on timing. Why the twin check stalls under repeated use on this
  machine is not known.
- **M-21 The same states through both paths (measured, guarded script `scan_paired.py`).** Six
  states at seed 296, with nothing ordered so that stock only falls. The orders were identical
  in 6 of 6, and so was the binding agent. Time per decision: 0.013 s on the fast path; 1.3 to
  1.9 s on the full path, and 5.1 s for the one decision run under the profiler. In that
  decision the twin check took 4.5 s and returned `twin_unavailable`, and the arbitration step
  took 0.5 s. So on this machine the full path costs on the order of a hundred times the fast
  path and changes nothing in the order. The twin check produced no verdict here; whether it
  does on a Linux runner, and what it then costs against its 8 s cap, is not measured.
- **M-22 What exists only off `main` (measured, `git diff --numstat origin/main...<branch>`).**

  | Branch | Commits ahead | What it carries |
  |---|---|---|
  | `fix/consensus-reads-request` (PR #87) | 5 | The repair of finding 112: `agents` +858 in 12 files, `packages` +205 (the one envelope reader), `uplift` +406, ADR-058, a re-measured Power_Report |
  | `feat/pathway-probe-trace` (PR #91) | 6 | PR #87 plus `scripts/diagnostics` +1,376 and its tests |
  | `fix/owed-gate-defects` (PR #90) | 6 | Repairs to gates: `scripts/audit` +146, `tests/verify` +559, `tests/uplift` +414 |
  | `fix/frontend-gates` (PR #89) | 16, plus 15 files uncommitted | Console: `frontend/src` 38 files +2,520, `frontend/spec` +3,763, ADR-059 |
  | `docs/knowledge-base` | 22, unpushed | Session 1's knowledge base |
  | `ledger` worktree | 0, four files uncommitted | The only record of the proof spec's session 13 (M-07) |
  | `ci/differentiated-schedules` | 11, dated July | A second CI system's configuration |

  `main` therefore still runs the consensus that reads none of its request, the state task 25
  measured at -4.40. Every statement in this window about the repaired path is about a tree
  that is not merged.

- **M-23 A miniature of E5 runs on this laptop in half a minute, repeats exactly, and
  reproduces the loss (measured, `mini_e5.py 12`).** Twelve of E5's own replicate seeds, each
  priced by E5's own function (`uplift.e5_suite.production_arm_cost`: one 24-hour replicate),
  for the consensus arm and for the tuned control E, and then again with freshly built arms.
  - Every repeat was identical to the last digit, 24 of 24. This answers R-43 for one machine;
    M-18 shows identity across two machines for the trace.
  - Mean cost: consensus 3.9073, tuned 2.5119, difference -1.3954. E5's 1,000 replicates gave
    3.9266, 2.4804 and -1.4463 (RD-01). The consensus arm was worse in 12 of 12 (R-33, in
    miniature).
  - 28.1 s for 48 replicate runs, 0.6 s each. At that rate E5's 2,000 runs are about twenty
    minutes here, against 53 minutes as a labelled CI job.
- **M-24 What the loss is made of: a sensitivity probe (measured, `sensitivity_level.py`).**
  Nothing in any tree was edited. In the probe's own process the Sentinel's reading of its
  request was wrapped so that the lead-time demand it plans against is multiplied by k, over
  the same twelve seeds. It is a what-if fitted to the seeds it is judged on. It can show what
  accounts for the loss; it cannot show an uplift.

  | k | Every reading scaled | Only readings from landed orders scaled |
  |---|---|---|
  | 1 (as it is) | 3.9073 | 3.9073 |
  | 2 | 3.4559 | 2.9284 |
  | 3 | 4.5173 | 2.6697 |
  | 4 | 5.7321 | 2.7525 |
  | 5 | 6.9448 | 2.8847 |
  | 6 | 8.1553 | 3.0284 |
  | 8 | 10.5717 | 3.3254 |

  The tuned control's mean is 2.5119. Two things follow. First, the Sentinel has two regimes:
  until a supplier's first order lands it plans against a 24-hour lead-time prior, which
  already orders far above the tuned rule's levels, so scaling everything makes cost grow
  without limit; afterwards it plans over lead time plus review (about 6.4 hours, M-32; the
  first version of this entry said "about two hours", wrongly). Second, tripling only
  the second regime's level takes the difference from -1.3954 to -0.1578, about 89% of the
  gap, and no single factor does better. So most of the loss is one quantity in one heuristic,
  set at about a third of what this objective rewards, and the rest is plausibly the prior's
  glut at the start of the run (inferred). The first reading this session made of the cause,
  "a mis-set level", was too simple: the first column refuted it and the second refined it.

- **M-25 Where any policy could win on the measured cell, and why waste cannot be one of the
  places (measured from the committed record; read in source).** The record is
  `docs/state/bprime/twin-regret-primary.json`, the artifact of run 36860454801 committed on
  2026-10-24: 200 replicates per arm on the primary cell, priced by the same objective as E5.

  | Arm | Mean cost | Unfilled demand | Stock held | Delivery | Spoilage |
  |---|---|---|---|---|---|
  | Never order | 6.870 | 5.156 | 0.373 | 1.282 | 0.0589 |
  | Untuned par level (50, 100) | 4.416 | 2.624 | 0.449 | 1.284 | 0.0589 |
  | Foresight arm (decides from a recorded trace of the run's demand, `uplift/foresight.py:13`) | 5.193 | 3.464 | 0.384 | 1.285 | 0.0589 |
  | Tuned rule E | 2.459 | 0.254 | 0.858 | 1.287 | 0.0589 |
  | Structure-aware base stock O | 2.212 | 0.345 | 0.521 | 1.287 | 0.0589 |
  | Hindsight oracle | 1.829 | 0.014 | 0.468 | 1.287 | 0.0589 |

  - The spoilage term is the same for every arm, the arm that never orders included, and the
    delivery term nearly so (1.282 to 1.287). They are 1.346 of the tuned rule's 2.459, so 55% of its cost responds to no
    decision.
  - The tuned rule's gap to hindsight is 0.630: 0.390 from holding more stock, 0.240 from
    unfilled demand. The structure-aware arm, which knows the world's declared demand shape
    and lead times, beats the tuned rule by 0.246, interval [0.214, 0.276]. The margin a win
    must clear is 0.4 (five service points at weight 8).
  - The record's own verdict is `room_to_win`, by a rule that tests the hindsight ceiling's
    interval against the margin. The best arm without hindsight on record does not clear it.
  - Read in source, `digital_twin/simulation/engine.py`: a per-item freshness clock loses 0.1
    every ten simulated minutes and, below 0.3, counts one spoiled order and resets (`:859-875`,
    identical on `main`);
    `spoilage_rate` is that count over orders created (`:143`); only a fulfilled demand takes
    stock away (`:831`). So waste in the twin is a clock: it consumes no stock and does not
    depend on how much is held or ordered.

- **M-26 Faults introduced into the decision core, and what the tests caught (measured,
  `fault_injection.sh`).** Each case is a fresh `git archive` of `1c484fb` in a scratch folder,
  one line changed by `sed`, then the CI fast selection for the decision core:
  `orchestrator/tests`, `agents/inventory_sentinel/tests` and the four test files under
  `tests/uplift` that name the faulted symbols, `-m "not slow"`.
  `orchestrator/tests/test_internal_only_routes.py` was left out because it imports `jose`,
  which this laptop's `.venv` lacks. Baseline: 664 passed, 26 skipped, in 18 s.

  | Fault | Line changed | Tests failed |
  |---|---|---|
  | F1 the confidence floor never fails | `orchestrator/guardrails/rules.py:460` | 15 |
  | F2 the fast path binds the lowest score | `orchestrator/consensus/protocol.py:654` | 1, which pins "raw utility argmax" |
  | F3 the Sentinel's review period tripled | `agents/inventory_sentinel/inference/request_state.py:53` | 1, which pins the constant's value and provenance as ADR-058 records them |
  | F4 nothing is executed | `protocol.py:1568` | 3 |
  | F5 a failed guardrail dispatches anyway | `protocol.py:889` | 4 |

  Every fault was caught. The safety behaviour (the confidence floor, the dispatch choke point,
  execution) is guarded by tests that fail when it breaks. F2 and F3 are caught by tests that
  pin the present design rather than judge it: F3 scales the Sentinel's plan by about 1.3 (two
  more hours on about 6.4, M-32), and its test fails whatever the change does to cost. The first
  version of this entry called F3 "close to the change that removes most of E5's loss"; the
  second review showed it is not. No
  test at this level judges whether a decision is good; that is left to E5, which runs in CI
  only when a person applies a label.
- **M-27 Pace, from the proof spec's own session log (read).** Its progress table
  (`SESSION_PROTOCOL.md` in the `ledger` worktree) dates sessions 1 to 10 between 2026-09-01
  and 2026-09-16, and sessions 11, 12 and 13 at 2026-09-29 to 10-12, 10-15 to 11-01 and 11-01
  onward. The spec was committed on 2026-08-20. So the record has two regimes: about a day and
  a half a session while work was local, and two weeks or more a session once each step waited
  on labelled CI runs. 63 days remain before the release must start. At the slow regime they
  hold four or five sessions; at the fast one, all eleven (inferred).

- **M-28 The console, opened cold with no backend (measured, the built-in browser on the
  existing ignored launch configuration `synapse-frontend`, `vite` dev server on port 3001,
  2026-11-17).** No backend runs anywhere (MAP F-19), so this shows the face a reviewer meets
  when the services are down, and the layout of the first screen, not the system at work.
  - Every API call returned 500 and the live feed's socket failed. The first screen, Mission
    Control, said so plainly: "SYSTEM TRUST Degraded", "Autonomy unknown", "0 DEC / MIN no
    signal", a banner "POSTURE UNKNOWN", and on each panel a note that the read is degraded or
    of unknown provenance. The header's attention control read "3 items need attention. Live
    feed offline". In one screenshot taken during the first seconds of loading it read
    "All clear" in green while the page said "Connecting to the console".
  - The first screen leads with the system's own state (trust, autonomy, the eight agents'
    activity, decisions a minute), then a KPI band and the map. The store's fill rate and
    waste are not on it.
  - The navigation offers Mission Control, Live Markets, Operations and more (fourteen routes,
    M-13). The Demo Theater runs a five-part story: Living Map, IPL Surge, Disruption, Debate,
    Evidence.
  - The map failed with a dev-server error: `basemap.ts:6` imports a worker file that exists
    only in maplibre-gl 6. This checkout's `frontend/node_modules` was installed on 2026-06-06
    and holds 4.7.1, against `^6.4.1` in `package.json` and 6.14.0 in the lockfile. A fresh
    install would differ; nothing was installed in this session. The local console has
    evidently not been run since June.
  - The server was stopped after the walk. It had rebuilt its dependency cache under
    `frontend/node_modules/.vite/deps`, an ignored folder; nothing else was written.

- **M-29 What was to stay unchanged, measured at the close (2026-11-17).**
  - `git for-each-ref --format='%(objectname) %(refname)'`, with this session's own branch
    `docs/truth-session-2` removed from the list, hashes to `57d932cbfc359db2`: the same digest as
    at the gate (M-14). No other branch, tag or remote-tracking ref moved.
  - `git ls-remote origin | sha256sum` begins `33be221323372c56`, as at the gate. Nothing was
    pushed.
  - `git diff --name-only docs/knowledge-base..HEAD`, excluding `docs/truth` and
    `docs/knowledge`: no file.
  - `git ls-files .kiro/settings`: nothing tracked. One stash, as before.
  - The five `.claude/worktrees`: the same heads and the same counts of uncommitted changes
    (consensus 0, frontend-gates 20, gate-defects 0, ledger 4, open-access 0); the `ledger`
    files keep the hashes of M-07.
  - Outside the repository: no GCP, Colab or GitHub write. GitHub was read through `gh` list,
    view and run download. The console's dev server was started and stopped; it wrote only its
    dependency cache under the ignored `frontend/node_modules/.vite`.
  - One slip, recorded: the last check above was run with a `cd` into the `ledger` worktree to
    hash two files. Nothing was written there.

- **M-30 Why the Freshness Guardian never proposes in E5 (measured).** The request the harness
  builds from an observation (`uplift/consensus_arm.py::observation_to_decision_request`) has no
  `store_id` key. Called with that request through its own entry point
  (`FreshnessGuardianA2AHandler.handle_request`, method `proposal`), the Freshness Guardian
  answers with error -32000: "1 validation error for FreshnessRequest / store_id / String should
  have at least 1 character". So its silence in E5 is a gap in the harness's request, of the
  same class as finding 112, not a property of the agent. The sensor's live request does carry
  `store_id` (V-05), so on the live path it would propose. The scans of M-19 filtered the
  handlers' error lines out of their output, which is why this was not seen there.

- **M-31 Every decision is bound by a proposal that declares itself degraded (measured).** 24
  hourly E5 decisions at seed 296 on the repaired tree, reading each proposal's `provenance`:
  `inventory_sentinel`, `demand_prophet`, `routing_navigator`, `disruption_shield` and
  `sustainability_agent` reported `degraded=True` in 24 of 24, each with confidence basis
  `fallback_floor`; `supplier_trust` reported `degraded=False` in 24 of 24, although its score is
  a configured prior that uses no data (MAP F-02). The Sentinel, which bound every decision,
  thus declared itself degraded every time while reporting a confidence of 0.85 to 0.97, and the
  confidence floor of 0.7 let each one through. In source, `orchestrator/guardrails/rules.py`
  never mentions `degraded`, and `protocol.py:1528-1546` only appends the names of degraded
  agents to the decision's context for the audit record. This answers R-21: the share of decisions with a
  degraded agent is all of them, and the top reason is no calibrated model or feature source.

- **M-32 What the Sentinel plans against after its first deliveries (measured, the second
  reviewer's probe, re-run by the main session).** The probe wraps the Sentinel's reading of its
  request and prices three of E5's seeds with E5's own function; it was re-run unchanged on the
  export of `1c484fb`. Costs 4.0109, 3.8735 and 3.6964, identical to M-23's first three seeds.
  Readings planned from landed lead times: 503, with lead time plus review of 3.29 to 11.52
  hours, median 6.36. Their planned demand rate: median 8.58 units an hour per item. Readings
  still on the 24-hour prior: 187. The true average rate, from the committed record's counters
  (568,547 demand events over 200 replicates of 24 hours and ten items), is 11.84 an hour per
  item. The Freshness Guardian was called 72 times and refused all 72 for the missing
  `store_id`, as in M-30.

### Window 1: read in the source by the main session

Each was first reported by a mapping subagent and then read at the cited lines by the main
session, on the exported tree of `1c484fb`. Paths are relative to the repository root.

- **V-01 How a tier is chosen.** `orchestrator/consensus/tier_router.py:69-92`. A request is
  tier 4 only if it carries `disruption_active` or `requires_twin_simulation`; tier 3 if more
  than three agents are named or `avg_confidence` is under 0.4; otherwise tier 2 unless one
  agent is named and `avg_confidence` is at least 0.9. `avg_confidence` defaults to 0.5, so a
  request that carries none of these keys is tier 2.
- **V-02 The fast path is an argmax.** `orchestrator/consensus/protocol.py:654`:
  `fast_best = max(proposals, key=lambda p: p.utility_score) if proposals else None`. Tiers 1
  and 2 run no debate, no arbitration and no twin check (`_fast_path`, lines 647 to 666).
- **V-03 Every proposer executes its own proposal.** `protocol.py:1568-1588` loops over
  `decision.proposals` and sends each agent an `execute` carrying that agent's own
  `ratified_proposal`; the comment reads "an agent enacts ITS OWN ratified proposal on the
  world". So on the live path the selection does not decide what is executed: all proposals
  are. In the E5 harness only the selected action reaches the twin (reported by the mapping
  subagent at `uplift/consensus_arm.py:413-432, 812-820`; not yet re-read), so E5 measures a
  different execution rule from the one the live path runs.
- **V-04 Below the gate nothing ever executes, even after a person approves.**
  `protocol.py:889-941`. A failed guardrail, the confidence floor among them, calls
  `self._hitl.escalate` and then records a withheld dispatch. The docstring states: "Nothing is
  executed after a human approves either." This answers R-32, and R-28 in part: an operator can
  neither release nor amend a withheld action.
- **V-05 What the sensor sends.** `orchestrator/sensor/loop.py:196-211, 296-312`. One trigger:
  any item below the reorder point. The request carries the low items, a fixed quantity of four
  times the reorder point for each, and the inventory. `disruption_active` is true only for a
  `disruption` trigger, which no detector produces (reported). By V-01 every decision the
  sensor convenes is therefore tier 2, so debate, arbitration, the LLM and the twin check are
  unreachable from autonomous operation.
- **V-06 The forecaster's `execute` changes demand.**
  `agents/demand_prophet/a2a/handler.py:127-186`. For each ratified forecast it applies a
  `SET_POLICY` action on the world's `demand_mult` lever, "the world scales its arrival rate
  through it", with a multiplier derived from the forecast's point value over its lower bound.
  A forecast is thereby given the power to change the quantity it forecasts. The project's
  agency audit counts this as an agent that "reaches an actuator" (M-11).
- **V-07 The one-command local start cannot produce a decision.** `docker/docker-compose.yml`
  defines seventeen services, among them the orchestrator and the console, and no API gateway,
  no digital twin and none of the eight agents. `Makefile:384-387` (`demo-up`, labelled "ONE
  COMMAND (fresh clone)") waits up to 180 s for a service named `api` that this file does not
  define, then runs the demo regardless. Read, not yet run. The only compose file with all 23
  services pulls its images from a registry that no longer exists (OA-1).
- **V-08 The Terraform is not what was deployed, and its default would fail again.**
  `infrastructure/gcp/terraform/wif.tf:17,24` names the pool `synapse-github-pool` and the
  provider `github`; the failing workflow asks for pool `github`, provider `github-aegis15`
  (M-08), so the June identity provider was not made by this code. `variables.tf:120-124`
  defaults `github_repo` to the repository's name in lower case, while the repository's
  canonical name has a capital letter (`git remote get-url origin`); the attribute condition at
  `wif.tf:36` is an exact string comparison (inferred: a fresh apply with the default would
  reject the workflow's token). `infrastructure/nginx/nginx.gcp.conf:92-95` hard-codes the old
  machine's address in the server name and the certificate paths.
- **V-09 Confirmations never reach storage, and the scorer reads storage.** `protocol.py:921`
  writes the audit row before `_phase_execute` runs. `protocol.py:1593-1615` reuses that row's
  id and returns the confirmations only on the in-memory decision. A text search of
  `orchestrator`, `packages`, `data_fabric` and `api` finds no other writer.
  `data_fabric/jobs/outcome_score.py:75-96` selects `execution_confirmations` from
  `audit_consensus` and passes `twin_divergence=None`, noting that the twin signal "is not yet
  joinable". Inferred: on the live path every scored outcome is `unknown`.
- **V-10 The meta-learner's system state is three values, two of them constants.**
  `protocol.py:1837-1842`: the hour of the day, `active_disruptions: 0`, `avg_fill_rate: 0.95`.
- **V-11 Where the objective's weights came from (R-29).**
  `digital_twin/simulation/policy.yaml`, section `regret_objective`. The cost is 8.0 times the
  unfilled share of demand, plus stock on hand over 1,000, plus the spoilage rate, plus the
  mean delivery time over 27.5 minutes; the stockout rate carries weight zero as a duplicate.
  The file's own `weight_provenance` gives the source of 8.0 and the two 1.0s as
  `agents/inventory_sentinel/models/newsvendor.py`, the default shortage and holding costs of
  the agent that E5 measures, and marks the delivery weight "chosen: ... no committed
  antecedent". No weight has a source outside the project. By arithmetic on RD-01's figures
  the tuned control's 2.4804 is about 0.49 for unfilled demand, 0.85 for stock, 0.06 for
  spoilage and 1.09 for delivery time (the last by subtraction), and nearly all of the
  consensus arm's extra 1.45 is the unfilled-demand term. Stock is cheap in this objective: a
  hundred more units held on every item costs what 12.5 points of fill rate cost.

Reported by the three mapping subagents and not yet re-read by the main session: the single
LLM call site inside debate (`protocol.py:1149`); the arbitration's weighted-sum selection and
what the NSGA-II step optimises (`orchestrator/consensus/pareto.py:91, 289-294`); the 0.7
confidence floor and the 300 s wait (`orchestrator/config.py:75-82`); the list of guardrails
(`orchestrator/guardrails/rules.py:368-460`); the per-agent sources of each constant score and
each agent's training code; the eleven steps from an empty cloud project; the sum of declared
memory limits; the list of published default credentials. Each is cited in `TRUTH-MAP.md` as
"reported" until re-read.

## Read, not reproduced

Source for RD-01, RD-02 and RD-06: `.claude/worktrees/ledger/.kiro/specs/decision-quality-proof/
tasks.md`, lines 6928 to 7074, uncommitted (M-07), and the bodies of pull requests #87 and #91.

- **RD-01 A repaired E5 exists and still loses.** Run 41352100304 at `4b659e6`, the head of
  PR #87: headline -1.4463, 95% interval [-1.4650, -1.4286], verdict `baseline_wins`, 1,000
  paired replicates per arm. Objective means: consensus 3.9266, tuned control E 2.4804. Fill
  rate 0.762 against 0.939; stockout rate 0.218 against 0.036; spoilage equal; units on hand 837
  against 847, so the arm holds about the same stock and runs out six times as often. All
  24,000 decisions were dispatched. The run took 3,206.964 s. The minimum detectable effect,
  0.0235, comes from the controls run 41343879850, not from this run.
- **RD-02 The recorded cause.** An unshocked request routes to Tier 2, whose fast path binds the
  highest-utility proposal (`orchestrator/consensus/protocol.py:654`, cited there). Only the
  Inventory Sentinel's payload names reorders. It orders up to an untuned newsvendor level from
  a run-average demand rate, with a 1,440-minute lead-time prior until an order lands. That the
  Sentinel bound every decision is inferred in the ledger, not measured. The pathway probe found
  `on_order` and `demand_to_date` changed 0 of 3 decisions; the ledger records ADR-058's
  falsification item 1 as firing as written. PR #91 adds a trace to settle it; this session read
  its artifact (M-16). Two things the first draft of this entry left out, both caught by the
  fresh reviewer. The ledger disagrees with itself: leaf 31.11 says whether item 1 fired "is
  not read yet", leaf 31.12 says it "FIRES as written". And the ledger offers its own innocent
  explanation (lines 7066 to 7071): where stock already sits above the order-up-to level the
  order is zero with or without the withheld input, so an unresponsive input need not be a
  wiring fault. M-16 supports that explanation: the trace's predictions P2 to P4 read "held".
- **RD-03 Before the repair.** E5 run 41289052859: -4.4026, [-4.4218, -4.3843]; 24,000 of 24,000
  decisions `untranslatable`, so that arm applied none of its decisions (same ledger).
- **RD-04 Finding 123.** `cd-gcp.yml` fails at Workload Identity Federation with
  `invalid_target`, "since at least 2026-08-17"; the provider is the operator's. Against M-08 the
  failures began no later than 2026-07-06, so the finding's date is late.
- **RD-05 Finding 89.** The deployed console signs every visitor in as admin. Its repair, PR #85,
  is merged and has never been deployed (inferred there and consistent with M-08).
- **RD-06 The controls.** Negative control `pass`; positive control `detected`, E minus O in
  [0.1875, 0.2200]. Checked by this session in `uplift/regret.py:95-115`: arm O is
  `structure_aware`, a base-stock arm that knows the world's structure, and the oracle is
  `hindsight`. So 0.20 is the gain of a better-informed rule over the tuned one, not the ceiling.
  The same controls returned agreement `harness_mis_measuring` (finding 117, conflict V, an open
  operator decision); the ledger attributes it to the seed sets. It is an open flag on the
  harness's internal validity.
- **RD-08 Headroom figures exist and are not yet interpreted.** The ledger carries `regret`
  0.4534 (reference cost 2.0850 against hindsight 1.6316) and `comparator_headroom` 8.94 and
  10.20 under definitions that changed between runs (`tasks.md` lines 1358 to 2494). Which cell,
  which arms and which definition apply to E5's comparison is question C.
- **RD-07 Fidelity.** The twin's fidelity is recorded `unknown` and gate C60 `unavailable`; the
  M5 dataset's terms were declined (C74).

## Outside sources

Checked by the main session on 2026-11-16:

- **EX-01 Google Cloud free-trial terms (last modified 2026-02-12).** Section 3.1: Compute
  Engine "restricted to only eight cores of concurrent usage per Free Trial". Section 1.3: $300,
  ending at three months from the start date, when unused credit expires. Section 1.2: only new
  customers are eligible. Section 3.6: Google may end or change the trial at any time. Sections
  4.2 and 4.3: after an upgrade the credit stays usable until the same date and these terms stop
  applying. Section 5.1: at the end, no access to the services.
- **EX-02 arXiv 2507.22040, "Structure-Informed Deep Reinforcement Learning for Inventory
  Management" (2025-07-29), Table 4.** Lost sales with lead times 2 to 7: the learned policy
  beats base-stock by 0.79% to 5.68% and vector base-stock by 0.29% to 3.79%, on 100,000
  simulated products, with the benchmarks given the demand distribution. No field result for
  these experiments.
- **EX-03 FreshRetailNet-50K (Hugging Face dataset page).** Licence tag `cc-by-4.0`. Hourly
  sales and hourly stock status per store and product, tagged for censored demand; 4.85 million
  rows; dates from 2024-03-28. Store, product and city counts are not on the page.

- **EX-04 DeHoratius and Raman, "Inventory Record Inaccuracy: An Empirical Analysis",
  Management Science 54(4):627-641, 2008 (abstract page, read 2026-11-17).** Of nearly 370,000
  inventory records from 37 stores of one retailer, 65% were inaccurate; auditing practice
  reduces inaccuracy and a complex store environment increases it.
- **EX-05 arXiv 2512.08296, "Towards a Science of Scaling Agent Systems" (v1 2025-12-09, v3
  2026-04-08; abstract read 2026-11-17).** Relative change against one agent ranges from +80.8%
  on decomposable financial reasoning to -70.0% on sequential planning; architectures without
  central verification propagate errors more; coordination gives diminishing returns once the
  single agent is strong. The abstract gives no amplification figures, no threshold number and
  no token overhead: those came from a subagent's reading of the body and remain reported.
- **The official Compute Engine price page could not be read by fetch** (its content loads by
  region selector). The VM price stays third-party until read in the console or the billing
  catalog.

Reported by subagents, not re-checked (their own grading in brackets):

- e2-standard-8 in asia-south1 at $0.3219 an hour, from a third-party price table [fetched, not
  official]. Five days about $40 with disk; fourteen days about $113.
- At trial end resources are stopped and Compute Engine data is marked for deletion, with a
  30-day window [fetched from the free-trial description page].
- `invalid_target` from the federation exchange is associated with a provider or pool that is
  deleted, disabled or misnamed [search snippet only].
- Deep RL did not beat capped base-stock in all lost-sales cases in the best-known comparison
  [snippet]. A field experiment found merchants' overrides of an algorithm cut profit by 5.77%
  [snippet].
- ACM artifact badges: Available, Functional, Reusable, Results Replicated, Results Reproduced
  [snippet].
- Multi-agent evidence, arXiv 2512.08296 [fetched by the subagent]: against one agent, several
  agents gain up to 80.8% on separable finance tasks and lose 39% to 70% on sequential planning;
  token overhead 285% (central) to 515% (hybrid); adding agents returns less once the single
  baseline is strong. Error amplification 17.2x for independent agents against 4.4x under
  central coordination, which the paper itself reports as not significant after controls
  (p = 0.658). That last clause corrects the reading in `docs/knowledge/TENSIONS.md` T-001.
- A vendor's own multi-agent research system gained 90.2% on an internal evaluation at about 15
  times the tokens of a chat [fetched]. A shop run by one agent did not make money in its first
  phase [fetched]. The best-known business simulation for agents has no measured human or rule
  baseline [fetched].
- Indian quick commerce, from press and aggregators quoting filings, none read in a filing:
  2,751, 1,240 and 1,139 dark stores for the three largest operators in 2026; 1,192 to 2,140
  orders a store a day; items per store from 2,000 to over 40,000 depending on source and
  definition; the largest operator dropped its ten-minute branding in January 2026 after a
  labour-ministry meeting. Replenishment cadence, lead times, wastage and demand concentration
  were not found.
- Stock records: 65% of nearly 370,000 records in 37 stores of one retailer did not match the
  shelf (DeHoratius and Raman, 2008) [fetched, abstract page].
- All five threads marked large parts of their briefs as not researched. The gaps are listed in
  each return and become the first research task after the gate.

## Hypotheses, each with what would prove it false

- **H-01 The cloud environment that ran the system no longer exists.** For: M-08, including the
  provider's own error text that the identity pool or provider is disabled, deleted or absent.
  A rival reading, that the repository changed owner and only the provider's condition is stale,
  would return a different error and is not supported. A second rival is not excluded: only
  that provider was removed, and the project and VM live on. Also for: the credit is
  "untouched" with 70 days left on 2026-11-15, which puts its start near 2026-10-26, months
  after the deploys of June; EX-01 ends service at a trial's end. False if the operator confirms
  the VM exists, or a read of the public address answers.
- **H-02 In the measured path the consensus of eight is one agent's heuristic.** For: RD-02,
  and now M-16, which measures it at the probe's three states: 15 of 15 decisions bound by one
  agent, in 21 milliseconds, with no debate tier reached. Still open for E5's 24,000 decisions
  and for the shocked cells. False if a trace shows another agent binding any E5 decision, or
  debate or full arbitration altering one.
- **H-03 On the present twin a tuned rule is near the ceiling for any policy without foresight,
  so a material win must come from structure the twin lacks.** For: EX-02; RD-06. Against: the
  harness refuses a margin that is not below measured headroom
  (`digital_twin/simulation/policy.py:403-425`), so headroom to hindsight exceeds the margin
  wherever that guard ran. False if a policy without foresight captures a material share of the
  hindsight regret on some cell.
- **H-04 A cold reviewer cannot say within five minutes what the system did and how they know.**
  Untested; needs the console running. False if a timed cold walk shows otherwise.
- **H-05 Red signals stand without a recorded response, and one of them was never a signal.**
  For: M-08 (six `sev1` issues open since July and two since November; a watchdog that has
  never reached the system). The first draft said "the apparatus detects and nothing responds";
  the fresh reviewer showed the watchdog detected nothing about the system at all. False if a
  record shows the alarms were triaged and deliberately parked.

## Review before the gate

One reviewer with fresh context (a subagent on a strong model, 14 tool calls) was given only
`OPENING.md` and this file. Dispositions:

| What it found | Disposition |
|---|---|
| M-01's command fails as typed | Corrected |
| M-02, M-03, M-05, M-09, M-10, M-11, M-13 and M-04's arithmetic reproduce | Recorded |
| The last deploy was 2026-06-14, not 2026-06-19; no scheduled deploy ever succeeded | Re-measured by the main session and corrected (M-08) |
| The watchdog never observed the system | Re-measured and corrected (M-08, H-05) |
| Two of eight alarms date from November, not July | Corrected |
| The console figure included its effectiveness harness; the core's tests omitted 7,594 lines | Corrected (M-04) |
| A percentage of a weighted objective was set beside a percentage of cost | Corrected in the scorecard row |
| The harness's `harness_mis_measuring` flag was omitted | Added (RD-06, scorecard row 3) |
| "Ten items" was measured only as the engine's default | Restated with M-16, which shows ten items in E5's traced world |
| The effort window is circular and five classing rules favour the contrast | Accepted; the whole-history figure now leads (M-05) |
| Question I ranked too low; the objective's weights belong in question C | Adopted |
| The operator was never asked whether the harness is the product | Added to the questions for the operator |
| One question to the operator was two; one was leading | Split and reworded |
| Question B ranked too high, since it reduces to a credential check | Not adopted: B also covers the rehearsal place and the time from clone to first decision. Its first step is now stated as the operator's one-minute check |

**The opposite case, as the reviewer put it.** The project's distinctive output is a harness
that produced a pre-registered, powered and controlled negative result about its own agents.
The agents are untrained by decision, and building them first would have produced
demonstrations nobody could falsify. The gates caught dead channels, a constant confidence and
a coverage figure that measured nothing. That is what a reviewer can verify, and it does not
need a live machine. What would decide between this and the reading in `OPENING.md`: what the
reviewers were promised (question A), and whether the falsification sweep shows gates that
actually fail (R-24).

## The second review (2026-11-17)

A second reviewer with fresh context (a subagent on a strong model, 20 tool calls, one probe
script of its own in a scratch folder) was asked to refute the direction and its most
consequential findings. Its claims were checked before use: the probe was re-run (M-32), and
the record's arithmetic was re-done by hand.

| What it found | Disposition |
|---|---|
| F-13a: "about two hours of demand" is wrong; the Sentinel plans over about 6.4 hours, at a run-average rate that ignores the day's shape | Verified (M-32) and corrected in F-13a, M-24 and DIRECTION |
| M-26 and F-31: F3 is not "close to the change that removes most of E5's loss"; it scales the plan by about 1.3 | Accepted and corrected |
| F-29: arm O is the only attainable arm on record and untuned; like for like, a win needs 7.0% over O, not 16% | Verified by arithmetic and corrected in F-29, FRONTIER and DIRECTION |
| DIRECTION section 2: "near what any policy without hindsight can reach" overstates | Accepted; replaced |
| DIRECTION section 2: "structural, not defects" is wrong for two of the four reasons | Accepted; rewritten |
| F-03: the Freshness Guardian's silence is a harness defect | Already found (M-30) and confirmed by its probe (72 of 72) |
| F-30: "every 80 minutes" holds for the primary cell only; delivery is nearly, not exactly, equal; an engine docstring contradicts the code | Accepted; the docstring added to the table of divergences |
| M-25: the "foresight heuristic" label is wrong | Accepted; relabelled from `uplift/foresight.py:13` |
| DIRECTION section 7: the slow-regime fallback does not fit 62 days and cuts the arbiter that defines the direction | Accepted; the pace is now a stated precondition with a tripwire, and the minimal release keeps the incumbent, one challenger and its map |
| DIRECTION section 7: session 5's "the sensor flags disruptions" would route decisions into debate and the language model, which the thin slice leaves out | Accepted; removed |
| DIRECTION section 4: shocked cells cannot run in full on the laptop | Accepted; screened at reduced replicates, full runs in CI |
| F-32: CI as the cause of the slowdown is inferred | Accepted; labelled |
| DECISIONS D-2 and D-10 state inferences as facts | Accepted; reworded |
| The strongest objection: the twin's lookahead is the least proven part and its test would be circular | Accepted as standing; DIRECTION section 9a now makes the lookahead earn its place by a test written in advance, and the first challenger no longer depends on it |

## Rejected so far

- An early reading that the positive control's 0.20 was the ceiling over the tuned rule, which
  would have made the 0.4 materiality margin unreachable. Rejected by reading `regret.py`: arm O
  is not the oracle (RD-06).
- Fetching from `origin` before the gate. Not needed (M-01) and it writes refs.
- Running the full stack before the gate. It is heavy for this laptop (M-12) and the operator
  should agree to it first.

## Open questions, in order

The ranked list and its reasons are in `OPENING.md`, section 4. First after approval: the
release path (does a cloud environment exist, can the stack be built and run anywhere, how long
from clone to a first decision), then headroom by cell, then one decision traced end to end.

## Lenses, first pass (each to be redone on evidence after the gate)

- **First principles.** Value in this domain needs a decision that changes a quantity ordered,
  moved, priced or discarded, and a way to tell the change helped. The measured system changes
  reorder quantities and is worse than a rule at it (RD-01).
- **Systems.** Two loops are open at a person: red signals stand unanswered, one of which never
  saw the system (M-08), and the newest results sit uncommitted (M-07). The build loop's verdict takes 20 to 60 minutes of CI
  per round (read, `HANDOFF.md`).
- **Inversion.** What would guarantee a failed release is present today: no deployable
  environment (H-01), no rehearsal place (M-12, EX-01), no single claim a reviewer can check.
- **Forward.** Hand-written coordination between agents loses value as models improve (read,
  T-001). A harness that can return an honest negative gains value.
- **Product.** Unmeasured until the console runs.
- **Taste.** Three message buses and stores, a mesh chart and two clouds for one store-day in a
  simulator: a practitioner would remove most of it (read, T-002).
- **Critical.** The strongest case against "apparatus over substance": the apparatus is what
  found the negative result, and it may be the product (T-004). To be argued by a fresh reviewer.
- **Judgment.** Recorded in `OPENING.md`, sections 5 and 9.
