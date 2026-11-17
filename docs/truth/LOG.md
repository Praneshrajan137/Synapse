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
    scheduled runs on record failed. The 28 newest runs all failed, including the scheduled run
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
