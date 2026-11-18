# docs/truth/log/session-03 - the running record of session 3 (Land, Ground and Seal)

Written so that a successor with none of this session's context can resume. Newest entries at the
bottom of each section. Labels as in [`../LOG.md`](../LOG.md): **measured** (a command run in this
session; the command is given), **read**, **checked** (an outside page opened by the main session
today), **reported** (a subagent's return, not re-checked), **inferred**, **hypothesis**,
**unknown**. Identifiers: S3-M-nn measurements, S3-D-nn decisions, F-nn findings (continuing
`TRUTH-MAP.md`).

## How to resume

1. Read "State" below, then the stage you are in under "Stages".
2. Re-check the preservation digests in S3-M-01 before changing anything.
3. Outside actions are approved only as listed in "The gate", section 7; every merge is asked for
   at the time (D-7).
4. Subagents: at most two or three at a time, each with a cap on calls, this file written first.

## State

- **2026-11-18, after the gate.** The operator approved the gate (below) through plan mode and
  added: "Do not need to worry and measure the usage, hereafter. Proceed as per your plan. We have
  to reach and achieve the highest frontier." Stage A is under way.

## Usage of the Claude plan

- At session start (2026-11-18, about 08:02 UTC), from the app: plan shown as **Pro** (the prompt
  and `PLAN.md` section 7 say Max, $150: a contradiction, unresolved); five-hour window 24% used;
  weekly window 51% used, resetting 2026-11-23; extra usage disabled.
- At the gate (about 08:17 UTC): five-hour 37%, weekly 52%. So reading, measuring and writing the
  gate cost about 13 points of one five-hour window and 1 point of the week.
- **Further measurement waived by the operator** at the gate. The ten execution sessions should be
  budgeted from the gate figure only as a lower bound: the gate is the cheap part of a session.

## The gate (approved 2026-11-18)

The full text approved is reproduced here in substance; the plan file itself lives outside the
repository.

### 1. What changed since session 2 (verified 2026-11-18)

- **S3-M-01 Nothing moved remotely (measured).** `git ls-remote origin | sha256sum` begins
  `33be221323372c56`; the digest of `git for-each-ref --format='%(objectname) %(refname)'` without
  `refs/codex/` and `refs/heads/docs/truth-session-2` begins `94c6a974bb7bb1ea` over 124 refs. Both
  equal session 2's (M-14, M-38). `origin/main` is `d4f985c`. One stash, as before.
- **S3-M-02 The open pull requests (measured, `gh pr list`, `gh pr checks`).** #87 at `4b659e6`,
  mergeable, 23 checks pass and 10 skip. #91 at `1c484fb`, a draft, the same. #90 at `860c62e`,
  17 pass and 3 skip. #89 at `9da8ceb`, a draft, 35 pass, 4 skip and one fails: "Playwright E2E +
  axe". All four are based on `d4f985c` and 0 commits behind it.
- **S3-M-03 The `ledger` files have not moved (measured, sha256).** The four prefixes equal M-07's:
  `tasks.md` `794b691a20fa8f1c`, `HANDOFF.md` `1180663b8aef0aaf`, `NEXT_SESSION_PROMPT.md`
  `cc60f0c100e32ac6`, `SESSION_PROTOCOL.md` `9acbb06f1c6b9fec`. Lines holding a placeholder:
  HANDOFF 15, NEXT_SESSION_PROMPT 9, tasks 6, SESSION_PROTOCOL 1.
- **S3-M-04 `main` is not protected (measured, `gh api .../branches/main/protection`: 404 "Branch
  not protected").** No required check and no review gate a merge; green before merge is enforced
  only by whoever merges.
- **S3-M-05 Every merge to `main` opens a sev1 issue (read in source, `cd-gcp.yml:39-61,612-652`;
  precedent measured).** CD-GCP runs on every push to `main`, fails at Workload Identity because
  the June account is gone (F-18), and its alert job opens one `sev1 deploy-failure` issue per
  commit. Issues #86 (`cd32c9d`) and #88 (`d4f985c`) were opened by the two merges of 2026-11-01.
  Eight auto-opened sev1 issues stand open (#75, #76, #78, #81, #82, #83, #86, #88).
- **S3-M-06 `main`'s Frontend CI is red on the supply-chain audit only (measured, run
  41332856903).** #89 passes that audit and fails its own E2E and accessibility check, which runs
  only on pull requests. Frontend CI runs on `main` only when `frontend/**` changes.
- **S3-M-07 The baselines reproduce exactly, and slower (measured, export of `1c484fb` in a
  scratch folder, the project's `.venv`).** The decision-core fast selection (the instrument's
  selection: `orchestrator/tests`, `agents/inventory_sentinel/tests` and four `tests/uplift`
  files, `-m "not slow"`, `test_internal_only_routes.py` ignored): 664 passed, 26 skipped, in
  45.8 s (session 2: 18.1 s). `mini_e5.py 12`: mean consensus 3.9073, tuned 2.5119, difference
  -1.3954, worse in 12 of 12, all 24 repeats identical, 103.8 s (session 2: 28.1 s). Per-seed
  costs equal session 2's to the printed digit.
- **S3-M-08 Why slower (measured, `powercfg`, `Win32_Battery`, processor counters).** The laptop
  was on battery (discharging, 75%) under the Balanced plan, with about 28% of the processors busy
  before any test ran (OneDrive, two other development tools, a chat client). Every timing in this
  file now states the machine's state.
- **S3-M-09 Runtime import closure (measured: a fresh interpreter imports one module and lists the
  third-party top-level packages it loads).** `digital_twin.simulation.engine`: 12 (among them
  `pydantic_core`, `pydantic_settings`, `dotenv`, `structlog`, `simpy`, `numpy`). `uplift.tuned_static`
  and `uplift.oracle_arm`: 19 each (adding `httpx`, `prometheus_client`, `yaml`, `click`,
  `pygments`), through `uplift/__init__.py`. `agents.inventory_sentinel.models.newsvendor`: numpy
  and structlog.
- **F-33 The twin's physics reads the environment (read in source; effect inferred, to be shown in
  stage C).** `digital_twin/simulation/engine.py:286` builds `TwinConfig()` when no config is
  passed, and `digital_twin/config.py` makes `TwinConfig` a pydantic `BaseSettings` with prefix
  `TW_`. So `TW_ORDER_ARRIVAL_RATE`, `TW_PICK_PACK_MEAN_MIN` and `TW_PICK_PACK_STD_MIN` change the
  demand rate and pick-pack times of every legacy twin run, E5 and B-prime included, while no
  sealed source digest changes. *False if* setting `TW_ORDER_ARRIVAL_RATE` leaves E5's per-seed
  cost unchanged.
- **S3-M-10 The sealed source sets (read, `uplift/power.py:130`, `uplift/bprime_record.py:91`).**
  `POWER_SOURCE_SET`: `uplift/*.py`, `uplift/metric_contract.yaml`, `digital_twin/simulation/*.py`
  and `policy.yaml`, `infrastructure/quality/comparator-tuning.yaml`, `uplift/baselines/*.py`,
  `digital_twin/config.py`. `BPRIME_PHYSICS_SET`: the same twin files and tuning file, plus
  `uplift/{foresight,harness,regret,tuning,tuned_static,oracle_arm}.py` and `uplift/baselines/*.py`.
  #87 changes seven `uplift/*.py` files (by design, with a re-measured Power_Report); #91's own
  commit, #90 and #89 change none; no pull request changes a file of `BPRIME_PHYSICS_SET`
  (measured, `git diff --name-only` against both patterns).
- **S3-M-11 Tools (measured).** Node 24.11.0 (Pyodide can run under Node); Docker Desktop
  installed and paused; no `sbx`, `py_ecc`, `pytest-xdist` or `python-jose` in the `.venv`.
- **Scope.** This session's prompt folds `PLAN.md` 9.1's session-4 row (kernel, seal, beacon) into
  session 3.

### 2. Frontier calibration for this session's properties

| Property | Leading practice and its number (how obtained) | SYNAPSE at the gate (measured) | Target this session |
|---|---|---|---|
| Time from a change to a trustworthy verdict | Predictive test selection at Facebook: over 99.9% of faulty changes reported at half the testing cost (Machalica et al., ICSE-SEIP 2019, arXiv 1810.05286 abstract; snippet). The ten-minute build of continuous integration (Fowler; recalled) | Safety: 18 to 46 s, five of five safety faults caught, no judgment of quality. Quality: E5 only, run in CI when a person applies a label, 53 minutes plus that person's latency | One command, at most 60 s on battery (30 s on mains), judging safety, quality and determinism, shown to fail on at least ten faults |
| Exactness of parity between runtimes | Box2D 3.1: bitwise-identical results across x64 and ARM and across MSVC, GCC and Clang, by owning its trigonometry and disabling fused multiply-add (box2d.org, 2024; snippet) | Trace byte-identical between a Linux runner and this laptop (M-18); 24 of 24 repeats identical; no kernel; browser parity unmeasured | The kernel equal to the harness to the bit on twelve seeds; parity under Pyodide measured if approved |
| Dependency weight of what must run in a browser | Pyodide's first load about 6.4 MB and a numpy wheel about 3 MB (Pyodide documentation and package index; snippet) | Twin 12 third-party packages; tuned rule 19 | Kernel at most 2 (numpy, simpy), measured at run time |
| Cost of keeping a legacy codebase green beside a new core | Strangler fig and parallel change, with characterization tests (Fowler; Feathers 2004; recalled): the legacy is left alone and equivalence is shown by tests | Any edit to the two sealed source sets voids recorded results (finding 122) and needs a labelled re-measure; 110 files name the twin or `uplift` | No legacy edit; parity checked in seconds inside the verdict |
| Strength of pre-registration | Registered reports and timestamped pre-registrations; commitment by hash; draws from public randomness (recalled; cited in stage D) | Claims pre-registered in the proof spec; weights are the measured agent's defaults (8:1:1); margin set by power; seeds known to the authors | A sealed file and its hash pushed before any result on the new world; confirmatory seeds from a future beacon round |
| Verifiable public randomness | drand quicknet: threshold BLS, a round every 3 s, scheme `bls-unchained-g1-rfc9380`, chain hash `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, genesis 1692803367 (chain information **checked** from the public relay, 2026-11-18) | None | A real round verified in a test by a pure-Python verifier, cross-checked by a second implementation |

The rows of `FRONTIER.md` (1 to 16, KB, U, W) and `PLAN.md`'s public-verifiability row are carried
into this session's closing scorecard with their definitions unchanged.

### 3. Questions, ranked by leverage

1. Does merging #87, #91 and #90 in order keep the proof's lineage valid on `main`: the
   Power_Report describing the tree, the B-prime physics digest unchanged, the truth gates green,
   the miniature unchanged? Answered by a local rehearsal of the merges before touching `origin`.
2. Is the false-alarm channel (CD-GCP and the watchdog) stopped before the merges? The operator's.
3. Is the whole consensus arm reproduced, bit for bit, by the Sentinel's newsvendor alone in a
   light kernel? If so, the browser can show SYNAPSE as measured without the eight-agent stack.
4. Can a one-minute verdict catch the quality faults the unit tests miss, with no false alarm on a
   clean tree?
5. Does F-33 hold: does a `TW_` variable change legacy results?
6. Which outside sources fix the economic weights and the margin, and over what band? Rule kept:
   no arm is priced under any candidate weight before the seal.
7. Does a pure-Python verifier accept a real quicknet round, and does an independent
   implementation agree?
8. Is the knowledge base safe to publish: no personal data (scan clean at the gate) and no long
   verbatim text from the reading corpus (to be checked mechanically)?
9. Can a Docker sandbox serve as the verification box? Depends on the operator's credit.

### 4. Assumptions carried

- Verified: everything in section 1; the beacon's chain information; `main` unprotected; one sev1
  issue per merge.
- Inferred: GitHub's merge commits will carry the same trees as a local `git merge` of the same
  parents (checked by tree hash afterwards); the slowness is the power state and background load;
  `py_ecc`'s `hash_to_G1`, documented against draft 09 of the hash-to-curve specification, matches
  RFC 9380 (to be checked against the RFC's test vectors before it is relied on).
- Unknown: Pro or Max; whether the Docker credit is claimed; whether the truth gates pass on the
  merged tree; whether the Sentinel alone equals the consensus arm.

### 5. What must be preserved, and the proof

| What | Proof |
|---|---|
| The `ledger` worktree's four files | Copied to a scratch folder with their sha256 before anything; after the commit, the committed blobs differ from the copies only on filled placeholder lines |
| `frontend-gates`' 20 uncommitted files, every other worktree, the stash | Porcelain status and file hashes before and after |
| Legacy behaviour | The fast selection and the miniature on the final `main` equal the `1c484fb` baseline (664 and 26 plus #90's tests; -1.3954, each seed to the bit) |
| The proof's lineage | `describes_revision` passes on the final `main`; the `BPRIME_PHYSICS_SET` digest is the same before and after |
| The sealed sets and the 110 legacy files during stages B to E | `git diff --name-only main...<branch>` shows no sealed file and no modified legacy file (additions, plus `CLAUDE.md`, the `Makefile` and one workflow) |
| `.kiro/settings/` and `C:\Documentation` | Never staged; the corpus is read, never copied |

### 6. The stages

The order is A, B, C, D, E; each is complete, verified and committed before the next begins. The
designs, acceptance conditions, rejected alternatives and pre-mortems are as approved; each stage's
section below records what was done against them.

- **A. Land the truth, losing nothing.** Record first; preservation snapshots; the ledger filled
  with verified facts only and committed; a local rehearsal of the three merges with the lineage
  checks; publication checks on the documents branches; then, with the operator's yes, the merges
  in order and the documents. **#89 is held**, decided on its evidence: its own E2E and
  accessibility check is red, its worktree holds 20 uncommitted files of unfinished work, and the
  console is frozen for the release (`PLAN.md` 13); its repairs are revisited in session 9.
- **B. A verdict in seconds that can be trusted.** `make verdict`: the fast selection in two
  process shards and the twelve-seed miniature in a process pool, judged against committed pins
  with distinct exit codes for a safety failure, a worse change, a change that is not worse, a
  nondeterminism and a moved control; refused when a `TW_` variable is set (F-33); shown to fail
  on at least ten faults; wired into CI; the three error patterns of D-13 and F-33 in `CLAUDE.md`;
  the sandbox measured only if the credit is claimed.
- **C. One decision kernel, exact everywhere.** `packages/synapse_kernel/`, numpy and simpy only,
  no environment reads; parity to the bit with the harness on E5's twelve seeds for arms E and O,
  and the Sentinel alone against the consensus arm reported either way; no legacy or sealed file
  changed.
- **D. The science, sealed.** `docs/truth/sealed/` with the incumbent (the best of three classical
  rules at equal tuning budgets), the economic weights from cited sources with a 27-point band,
  the margin in cost units from declared parameters, exploratory seeds from a public label,
  confirmatory seeds from a future beacon round, random shock onsets that policies cannot see,
  and an analysis valid for the data's structure; hashed, committed and pushed before any result
  on the new world.
- **E. The beacon.** A pure-Python verifier, the RFC's vectors, one real round, three tamperings,
  a second implementation, and the contest's commit-and-reveal protocol; or the failure, its
  reasons and the fallback.

### 7. Outside actions approved

Approval says yes to everything below except the lines marked **ask**, confirmed at the time.

| # | Action |
|---|---|
| G1 | Push `docs/dqp-session-13`; open its pull request |
| G2 | Mark #91 ready for review |
| G3 | **ask** - merge #87, then #91, then #90 |
| G4 | Push `docs/knowledge-base` and `docs/truth-session-2`; open their pull requests; **ask** - merge the ledger, then the knowledge base, then the truth record |
| G5 | Disable the "CD - GCP" and live-truth workflows until a deploy target exists; close the eight auto-opened sev1 issues with a pointer to F-18 and F-25 |
| G6 | Push the branches of stages B to E; open their pull requests; **ask** - merge each when green |
| G7 | Push `docs/truth-session-3`; open its pull request; **ask** - merge |
| W1 | Install `py_ecc` and its dependencies from PyPI into the `.venv`, pinned with upper bounds |
| W2 | Fetch one quicknet round and the chain information from the public relay |
| W3 | `@noble/curves` from npm into a scratch folder |
| W4 | `pyodide` from npm, with its numpy, into a scratch folder |
| X1 | A Docker sandbox measurement, only if the operator says the credit is claimed |

## Decisions of this session

- **S3-D-01 (2026-11-18). The session's record lands with the documents.** This file and the
  pointer in `LOG.md` are committed on `docs/truth-session-2` before it is pushed, so `main`
  receives them in stage A; later entries go on `docs/truth-session-3`, cut from `main` once the
  documents land, and merge at the session's close.
- **S3-D-02 (2026-11-18). #89 is held** (stage A above).
- **S3-D-03 (2026-11-18). Weights are chosen before they are used.** No arm, on the legacy world or
  any other, is priced under a candidate weight before the sealed file is committed. Pricing under
  candidate weights first would let the sign of a result choose the weights.
- **S3-D-04 (2026-11-18). The operator's standing approval for this session's merges.** Answer to
  G3: "Yes, and future green PRs too". The ledger, documents and stage PRs of this session are
  merged without a further question once each is green and its checks pass; anything else that
  changes an outside service still needs its own yes.

## Stages

### A. Land the truth

- **S3-M-12 Preservation snapshot (measured, 2026-11-18, before any change).** Copies of the four
  `ledger` files with their sha256 (equal to M-07's), the porcelain status digest and head of all
  eight worktrees, the sha256 of the 20 changed paths in `frontend-gates`, the stash list and the
  ref digest `94c6a974bb7bb1ea` are kept in the session's scratch folder (not in the repository).
- **S3-M-13 The ledger's census (measured).** `python -m scripts.audit.spec_ledger_census --files
  --next 40` on an export of `d4f985c` with the four `ledger` files laid over it: 28 parents, 200
  leaves, 162 done, 0 pending, 38 open (0 authorable, 12 CI-gated, 26 deferred), 0 unharvested,
  `complete: no`, exit 0. Its 34 `absent-artifact` lines name files of the unmerged PRs (#87's
  `request_state.py`, ADR-058 and others) or paths tasks name in order to reject them. HANDOFF
  records 130 done at session 12's close, so session 13 discharged 32 leaves by this count.
- **S3-M-14 The six closing checks of the spec's prompt, on the same export (measured).**
  `workflow_shape_truth` 0, `pin_extractor_truth --check` 0 (18 pins), `sweep_budget_truth
  --check` 0, `dataset_licence_truth --check` 2 (a skip by decision, as the prompt says),
  `task_claim_truth --check` 0, `gate_surface --check` 0, and the census `--check` 0.
- **The ledger committed (`d48903d` on `docs/dqp-session-13`).** All 48 placeholders were filled
  by a fact read today (the census; #90's number, head and CI runs; the push runs at `d4f985c`;
  #89's round-3 run 43575491177 and the runs after it; run C 43631919800; task 31.12's stated
  claim; round 1's `e2e` red as a miss, from the local file `.tmp/s13/pred_89_r2.md`) or marked
  "not recorded" (the closing date, core-seconds, CI critical path, agent batches, G7, G8, the
  levers, the other S13 options, the T0 to T5 reading, the F-F-1/F-F-2 coverage). **Proof nothing
  else moved:** a line-level comparison with the pre-fill copies finds no changed line outside the
  lines that held a placeholder (HANDOFF 17 of 17, NEXT_SESSION_PROMPT 12 of 12, SESSION_PROTOCOL
  1 of 1, tasks 9 of 9). The script is `fill_ledger.py` in the scratch folder; its fills are
  listed in the commit message.
- **S3-M-15 The knowledge base copies nothing verbatim (measured, and the check shown able to
  fail).** Every file the documents branches add under `docs/knowledge/` was tokenised into
  lowercase words and its word 10-grams looked up among the 820,091 10-grams of the 242 corpus
  files: 0.0% found in every file; the longest shared run is 0 words. Positive control: five
  60-word excerpts drawn at random from the corpus, padded with other words, were each found as a
  60-word run. The privacy scan of the added lines (e-mail addresses, IPv4 addresses, the
  operator's name, home-folder paths) found none; `C:\Documentation` is named as a location only.
- **S3-M-16 Scheduled workflows failing on `main` (measured, `gh run list --commit d4f985c`).**
  Besides CD-GCP and the watchdog: SYNAPSE Integration (daily), Publish daily audit anchor to
  Rekor (daily), Required checks reconcile and the scheduled Mutation sweep fail on schedule; the
  nightly LLM judge passes and fails. None of these opens an issue. They are recorded for the
  retirement-by-experiment work of D-5, not acted on here.
- **G5 done (2026-11-18).** Workflows "CD — GCP" (id 283570252) and "Live Truth (watchdog)"
  (292670274) disabled (`gh workflow disable`; reversed by `gh workflow enable`). Issues #75, #78,
  #81, #82, #83, #86 and #88 (deploy failures) and #76 (watchdog) closed, each with a comment
  giving the cause (F-18, F-25) and the way back. Open sev1 issues: 0.
- **G1, G2 done.** `docs/dqp-session-13` pushed; its pull request is #92. #91 marked ready for
  review.
- **S3-M-17 The merge rehearsal (measured; instrument `rehearse.sh` in the scratch folder).** A
  detached scratch worktree at `d4f985c`; `git merge --no-ff` of `4b659e6` (#87), `1c484fb`
  (#91) and `860c62e` (#90), in order: no conflict (the only file both #90 and #87/#91 change is
  `.github/workflows/uplift.yml`, merged cleanly). Trees: after #87 `2dc60fae`, after #91
  `08f53870`, after #90 `f7c75547`. On an export of the result:
  - the decision-core fast selection: 664 passed, 26 skipped (19.9 s on mains-equivalent load);
  - #90's five changed test files: 74 passed (see S3-M-18 for the first, failed attempt);
  - `mini_e5.py 12`: every seed's two costs equal the `1c484fb` baseline to the printed digit;
    mean difference -1.3954; worse in 12 of 12; all repeats identical;
  - lineage: `describes_revision` True; `BPRIME_PHYSICS_SET` digest `dbedae9d11ae1623`, the same
    as on `d4f985c` (measured there too) and the value the B-prime record carries since finding
    122's repair; `POWER_SOURCE_SET` digest `0dd399e2` on `d4f985c` and `c0cc006c` after the
    merges, each described by its own tree's Power_Report (True on both), as #87 intends;
  - the truth gates' first job: `registry_gate` 0, `doc_truth --check` 0 (20 of 20 claims),
    `gate_surface --check` 0 (691 rows), `workflow_shape_truth` 0, `required_checks_truth` 0,
    `sweep_budget_truth` 0; `ledger_gen --check` 1, on C71 only: the committed row says "200
    golden trace(s) from tests/eval/golden_traces", the local run "0 ... (unresolved)" (whether
    this also fails on `main` locally, which would make it environmental, is measured next).
- **S3-M-18 A local trap: `packages/` on `PYTHONPATH` shadows the repository's `tests` (measured).**
  `tests/` has no `__init__.py`; `packages/tests/` has one. With `PYTHONPATH=<tree>;<tree>/packages`
  (session 2's convention, D-07), `import tests` resolves to the regular package
  `packages/tests`, which wins over the namespace portion at the root, so
  `from tests.verify.strategies import ...` fails: "No module named 'tests.verify'". With
  `synapse_common` alone on the path (copied to a folder of its own), the same five files pass, 74
  of 74. Not a defect of #90; a trap for every local run of `tests/verify`. Candidate error
  pattern for `CLAUDE.md`.
- **S3-M-19 The C71 difference was the same trap (measured).** `ledger_gen --check` on the
  rehearsed tree with `synapse_common` alone on the path: exit 0, "57 PASS, 0 FAIL, 0 PARTIAL, 11
  SKIP", the 200 golden traces found. C71 loads them through `tests.eval`, which the shadowing
  hid. On `d4f985c` the same check also passes. So every truth gate passes on the rehearsed tree.
- **G3 asked and answered (2026-11-18).** The first question was dismissed when the app closed;
  asked again, the operator chose **"Yes, and future green PRs too"**: merge #87, #91 and #90
  now, and merge the ledger, documents and stage PRs of this session once each is green and its
  checks pass, without asking each time (recorded as S3-D-04).
- **G3 done: the three merges (measured, `gh pr merge --merge`, then `git fetch` and tree
  hashes).** #87 as `f31696d` (tree `2dc60fae`), #91 as `fb84caf` (tree `08f53870`), #90 as
  `8c48635` (tree `f7c75547`): each merge commit's tree is byte-identical to the rehearsal's at
  the same step, so everything S3-M-17 and S3-M-19 measured holds for `main` as merged.
- **The ledger merged.** Locally on top of `8c48635`, the census `--check`, `task_claim_truth
  --check` and `ledger_gen --check` pass; #92 (green in CI: 17 pass, 3 skip) merged as `eb446ed`,
  tree `eb53df58`, equal to the local merge. The `ledger` worktree's four files are now on `main`.
- **S3-M-20 CI's lint scope (read, `ci.yml:81-92`).** `ruff` and `mypy --strict` run on
  `packages/synapse_common/`, `agents/` and `orchestrator/` only, so the session-2 instruments
  under `docs/truth/instruments/` meet no lint gate when the documents land (D-08's concern was
  about `scripts/`).
