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

- **2026-11-19, about 07:05 UTC.** The seal's timestamp is confirmed in Bitcoin, blocks 976528,
  976529 and 976535, each checked against two block explorers (S3-M-35). The upgraded proof
  replaces the pending one (branch `docs/seal-timestamp-upgrade`); session 4's first item is done.
- **2026-11-19, after the close.** The operator approved anchoring the seal (S3-D-09):
  `docs/truth/sealed/SHA256SUMS.ots` is committed on #99 (`6b3a604`), accepted by four public
  calendars and awaiting a Bitcoin block (S3-M-34). Upgrading the proof is session 4's first item.
- **2026-11-19, at the close.** Stages A to E done. On `main`: #87, #91, #90, the ledger (#92), the
  knowledge base (#93), session 2's record (#94), the I-1 grep fix (#95), the verdict (#96) and the
  kernel (#97). Open with CI running and no failure at the close: the beacon (#98), the seal (#99)
  and this record; under the operator's standing approval each is merged once green. The seal's
  content was pushed on 2026-11-19 (commit `bdb64da`); its timestamp is #99's merge time. The
  final account, the panel, the scorecard and the work for session 4 are at the end of this file.
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
- **S3-M-21 A composition defect the merges exposed, repaired (measured; PR #95).** After the three
  merges, `main`'s quality gates failed at "No paid API imports (I-1 - BLOCKING)" on
  `uplift/cost_probe.py:459`, `from uplift.harness import replicate_seed`: #90 widened the grep to
  `uplift/` and added `replicate`, #87 added the import of a harness function whose name only begins
  with that client's, and each PR had been green alone. The rehearsal (S3-M-17) ran the Python gates
  and the tests but not `ci.yml`'s inline shell steps, so it could not see this (error pattern
  E-TP-07). Repair: every alternative of both greps (`ci.yml`, `security.yml`) ends in grep's word-end
  anchor `\>`; the parity test now requires the anchor, compares the pre-repair grep by (form,
  client) pairs, and runs the committed alternatives over real and lookalike lines; the pre-commit
  hook gets the same semantics. Measured: the anchored grep passes every CI tree on `main`; the old
  one reproduces the false positive; #95 green (17 checks), merged as `9aa2aad`.
- **F-34 The pre-commit layer has never run (measured).** `.pre-commit-config.yaml` fails to parse as
  YAML at every commit from its creation (`c8f1e3e`, 2026-04-06) to `main` (the `reward-isolation`
  hook's multi-line `entry` puts code at column 1); `.git/hooks` holds no `pre-commit`; no workflow runs
  pre-commit. So no hook in it (`no-raw-hex`, `no-paid-apis`, `spec-validate`, `reward-isolation`,
  `jitter-enforcement`, ...) has enforced anything, although `CLAUDE.md` cites `no-raw-hex` as the
  guard of INV-CLR-009. Even parsed, YAML would fold the multi-line `python -c` entries into one line.
  *False if* `pre-commit validate-config` accepts the file. Left to its own change (block scalars, then
  each hook run against the tree, then a CI job), recorded as E-TP-08.
- **The documents PRs re-tested.** Closed and reopened after #95, they re-ran on a stale test merge;
  both branches were then synced with `main` by merge commits (`0e55f22`, `8e0a8df`).

### B. A verdict in seconds that can be trusted (PR #96, branch `feat/verdict`)

- **What was built.** `python -m scripts.verdict` (`make verdict`): the decision core's fast
  selection in two pytest shards and the E5 miniature (E5's first twelve replicate seeds, consensus
  arm and tuned control) at the same time, judged exactly (`float.hex`) against committed pins
  (`infrastructure/quality/verdict-pins.json`, equal to session 2's printed costs). Exit codes:
  PASS 0, SAFETY 1, WORSE 2, CHANGED 3, NONDETERMINISTIC 4, CONTROL_MOVED 5, REFUSED_ENV 6 (any `TW_`
  variable: F-33), INCOMPLETE 7. `--repin` writes pins only from a safe, complete, deterministic run.
  CI: `.github/workflows/verdict.yml`. `CLAUDE.md`: E-TP-01 to E-TP-08.
- **S3-M-22 How the time was found (measured).** One consensus replicate: 0.45 s to build the arm and
  1.75 s to run it, after a one-time 12 s import of the agent stack per process; a tuned replicate
  0.5 s. A pool handing out single replicates got slower with more workers (3, 4, 6, 8 workers: 49.5,
  56.2, 71.2, 87.0 s), because each worker pays the import and they contend. Two processes, each
  pricing half the seeds and re-pricing one seed the other priced: about 45 s on mains power; three
  processes saved 1 s.
- **S3-M-23 The verdict's time (measured, three consecutive runs).** On battery (70%, Balanced plan,
  20 to 37% background CPU): 59.5, 59.9 and 52.3 s, median 59.5 s, PASS 3 of 3. On mains power
  earlier: 44.6 to 46.7 s. Both shards together are the session-2 baseline exactly (331 + 333 = 664
  passed, 8 + 18 = 26 skipped).
- **S3-M-24 The fault proof (measured; `scripts/verdict/fault_proof.py`; record
  `infrastructure/quality/verdict-fault-proof.json`).** 16 of 16 judged as expected. Clean copy, three
  times: PASS. F1 confidence floor never fails: SAFETY. F2 fast path binds the lowest score: SAFETY,
  consensus +2.911 dearer on 12 of 12. F3 review period tripled: SAFETY (a pinning test), consensus
  -0.433 cheaper on 12 of 12. F4 nothing executed: SAFETY, +2.911. F5 failed guardrail dispatches:
  SAFETY. Q1 Sentinel demand rate halved: SAFETY, +1.364 dearer. Q3 twin arrival rate, Q5 tuned-rule
  comparison flipped, Q7 objective weight: CONTROL_MOVED (the B-prime record refuses the moved
  physics by its digest). Q6 a `TW_` variable set: REFUSED_ENV; Q6b with `--allow-twin-env`:
  CONTROL_MOVED, the tuned control +0.102 (F-33 through the verdict). Q4 a stray `random.random()`:
  caught as a changed decision, not as nondeterminism, because the legacy engine seeds the GLOBAL
  `random` module with the replicate seed (`_init_env`); Q4b a string hash (process-dependent): the
  cross-process repeat lists the two seeds whose cost differed (`0x1.d3ec...` then `0x1.d3e4...`).
- **S3-M-25 Two traps met building it (measured).** A `synapse_common` copied outside the repository
  tree cannot start its schema registry (it walks up from its own file to `proto/domain/`), so the
  consensus arm refuses to assemble and every case read INCOMPLETE (E-TP-06); and the physics faults
  first read INCOMPLETE until a refusal by the record's physics digest was classed as a moved control.
- **Not done: X1.** The Docker sandbox was not measured: the operator did not confirm that the credit
  is claimed. The laptop held everything this session needed.
- *Rejected:* pytest-xdist (a new dependency for what two process shards give); pins alone (cannot
  say better or worse); a statistical bound alone (misses cost-neutral behaviour changes and
  nondeterminism); a pool of single-replicate workers (measured slower).

### C. One decision kernel, exact everywhere (PR #97, branch `feat/decision-kernel`)

- **What was built.** `synapse_kernel/`: `world.py`, `lead_time.py`, `engine.py` ported from the
  legacy files by asserted text replacement (every draw, event and line of arithmetic kept, in
  order); `drive.py` (E5's replicate loop), `objective.py` (the committed objective), `observation.py`
  (no shock field: policies must detect, never be told); `policies/tuned.py` (arm E) and
  `policies/base_stock.py` (arm O); `worlds/legacy_primary.json` exported from the legacy reader by
  `scripts/kernel/export_legacy_world.py`. `KernelConfig` reads no environment. CI:
  `.github/workflows/kernel.yml`, a light job with only numpy, simpy, pytest and hypothesis, and a
  parity job with the full closure.
- **S3-M-26 Light by measurement.** A fresh interpreter importing every kernel module adds only
  numpy and simpy (the legacy twin: 12 third-party packages; the legacy tuned rule: 19). No repository
  package outside the kernel is loaded; no kernel source reads the environment. Each check fails on a
  planted fault: a `yaml` import, an `uplift` import, an `os.environ` read.
- **S3-M-27 Exact (measured).** Arms E and O: the kernel's cost equals
  `uplift.e5_suite.production_arm_cost` as `float.hex` on all twelve of E5's first replicate seeds;
  the kernel repeats itself to the bit; the constants it inlined equal the legacy ones; and
  `TW_ORDER_ARRIVAL_RATE=2.2` moves the legacy twin's cost and not the kernel's (F-33 shown).
- **S3-M-28 Legacy untouched.** `git diff --name-only origin/main` on the kernel branch lists no file
  under `uplift/` or `digital_twin/`: the sealed source sets and the proof's records stand.
- **Deferred, with reason: the Sentinel alone against the consensus arm.** Porting the Sentinel's
  handler, pipeline, serving model and calibration data is about 600 lines with data dependencies.
  F-01 already shows the Sentinel binds every traced decision, and session 6 rebuilds the challengers
  inside the kernel, so the exact reduction of the eight-agent arm to one rule is the first item of
  session 4's kernel work, not a blocker for sealing.
- *Rejected:* a lazy `uplift/__init__.py` (voids the Power_Report's digest); an engine without SimPy
  (parity risk now); importing legacy files by path (pulls pydantic and YAML); a JavaScript kernel.

### D. The science, sealed (PR #99, branch `docs/sealed-science`)

- **What was sealed.** `docs/truth/sealed/PREREG-1.md` (governing) and `prereg-1.json`, with
  `check_prereg.py` and `SHA256SUMS`; `DEVIATIONS.md` starts empty; `.gitattributes` keeps the sealed
  bytes exact on every checkout (the rule the B-prime record and Power_Report already use). Sealed
  2026-11-19, before the release's world exists.
- **S3-M-31 Sources, as obtained.** IFPA, *Produce Department Benchmarks*, August 2023, read at the
  source: produce gross margin 38% (2023 and 2022), shrink 5.46% of sales, labour 7.42%, from 15
  chains with over 1,000 US stores (**checked**). Carrying cost 20% to 30% a year, and a realised
  benchmark median near 10% (**snippet**). Broekmeulen and van Donselaar 2009, existence and venue
  (**checked**). The quicknet chain information (**checked**).
- **S3-M-32 The attack before sealing.** A fresh-context reviewer (one subagent, 8 tool calls) found 6
  blockers, 8 major and 8 minor findings in the first draft. Checked before use: D-4(a)'s fill floor
  (read in `DECISIONS.md`), the round and the seed vectors (the reviewer's own arithmetic, re-done).
  One claim did not hold (that `CONTEST-PROTOCOL.md` exists nowhere: it is on #98). All findings were
  adopted or adapted; PREREG-1 section 12 lists them. The most consequential: parity of information
  and action between the arms; an incumbent that follows the weekly shape and is re-tuned for short
  shelf lives and on pooled shocks; tuning run to convergence with a defined evaluation unit; two
  freezes, W before any challenger runs on the world; `J_k` as a per-store-day mean; R_C never
  redrawn for our own failure and the first complete run primary; C1 with the fill floor; one Holm
  family for C2 and C3 at one-sided 0.025; shocks lengthened from hours to days, since one point of
  fill over a week was out of reach for a few-hour surge.
- **S3-M-33 The seal (measured).** `SHA256SUMS` sha256 `00a28844ee45e8537a0b5f7ebe3f53703d0bbad7a76a9b8af9a99646cb830f1f`;
  PREREG-1.md `68e538e2...`, prereg-1.json `fbcb0a85...`, check_prereg.py `1dd86e6b...`, equal in the
  committed blobs (`bdb64da`). `python docs/truth/sealed/check_prereg.py` prints "OK the seal agrees
  with itself"; on a scratch copy it fails when the margin's `0.38` becomes `0.39` and when the round
  moves by one.
- **The confirmatory round** is quicknet **34714612**, emitted **2026-12-11T00:00:00Z**; freeze C must
  be pushed before then.
- **Timestamp.** The pull request's server-side merge time on GitHub proves when the seal existed.
  An OpenTimestamps proof (a download and a submission to public calendars) was not in the approved
  outside actions; it is offered to the operator. Approved after the close (S3-D-09): S3-M-34.
- **Rule kept.** No arm was priced under any candidate weight before the seal (S3-D-03).
- **S3-M-34 The seal anchored in Bitcoin (measured, after the close).** `SHA256SUMS` was stamped
  through OpenTimestamps at 2026-11-19T04:00:27Z. The proof is `docs/truth/sealed/SHA256SUMS.ots`
  (770 bytes, sha256 `1780fb3aca6f59d18dc97b6ed3f1b3644464ea87d461e73e9330fba370b1162a`, commit
  `6b3a604` on #99); it commits to the file digest `00a28844...`. All four default aggregators
  accepted it, so the proof holds pending attestations from `alice` and `bob`
  (`calendar.opentimestamps.org`), `finney` (`calendar.eternitywall.com`) and
  `btc.calendar.catallaxy.com`; the times the calendars prepended read 04:00:29Z and 04:00:30Z.
  Only a nonce-blinded digest left the machine. The `ots` 0.7.2 command does not start on Windows
  (E-TP-09), so the stamp was made through the `opentimestamps` 0.4.5 library, step for step as
  `ots stamp` does it (sha256, a 16-byte random nonce, sha256, four calendars, at least two replies
  required), and read back as `ots info` does: the digest matches and all four calendars are listed.
  Both packages are LGPL-3, outside the allowed licences: they stayed in a scratch environment and
  are no dependency of the repository. The proof is not sealed (`SHA256SUMS` lists only PREREG-1.md,
  prereg-1.json and check_prereg.py), so upgrading it changes no sealed hash, and `check_prereg.py`
  still prints "OK". Until a block confirms the calendars' aggregates, the proof rests on the
  calendars' word.
- **S3-M-35 The seal confirmed in Bitcoin (measured, about 07:05 UTC).** One pass of `ots upgrade`,
  made through the library as in S3-M-34 and asking only whitelisted calendars, found Bitcoin
  attestations from three of the four calendars; `finney` still answered "Pending confirmation in
  Bitcoin blockchain". The upgraded proof (3,704 bytes, sha256
  `47036482f79e330d2622337ed78364e36f12a0fe7897570b36ea7658372c1e0b`) still commits to `00a28844...`
  and keeps the four pending entries, as the client does. The blocks:
  - `bob`: block 976528, `000000000000000000019286be73c9885c865686462fb0a0823937991c72fc28`, 04:09:53Z;
  - `alice`: block 976529, `00000000000000000001bfb85615a1fb7963becf842ea35599352e2313b042eb`, 04:14:13Z;
  - catallaxy: block 976535, `0000000000000000000045ecca1887e6050256aa69355c201f220692917a1a43`, 05:31:10Z.

  Each block was checked against mempool.space and blockstream.info, two operators: both name the
  same block at each height, its 80-byte header hashes to that block's hash, the header's merkle
  root is the proof's attested message byte for byte, and its work meets the header's own target.
  At the check the blocks had 18, 17 and 11 confirmations. So `SHA256SUMS`, and with it the sealed
  files it hashes, existed when block 976528 was mined, nine minutes after the stamp (Bitcoin's
  rules keep a block's time within about two hours of the true time). No node of our own was used:
  the explorers' agreement and the work in each header stand in for one. Anyone can re-check with
  `ots verify` and a Bitcoin node, or with the two files at opentimestamps.org.

### E. The beacon, proven (PR #98, branch `feat/beacon-verify`)

- **S3-M-29 A verified round, two ways (measured).** `synapse_beacon` (pure Python, `py_ecc` 8.0.0,
  MIT): RFC 9380 Appendix J.9.1's two hash-to-G1 vectors match (read from rfc-editor.org); quicknet
  round 34052212 (2026-11-18T00:00:00Z; three relays byte-identical, Cloudflare's formatted
  differently) verifies in 0.9 s and its randomness is `sha256(signature)`; a flipped bit, the
  neighbouring rounds, another public key and malformed input are rejected. `@noble/curves` 1.9.7
  under Node gives the same verdicts. `round_at(2026-12-11T00:00:00Z) = 34714612`.
- **S3-M-30 An error of mine, caught by the network.** The first fixture round was computed by hand
  and was 2026-11-19 00:00 UTC; the relays answered "Requested future beacon". The latest round,
  34070649, matched the relay's own clock (15:21:51 UTC), confirming the formula; the error was the
  hand arithmetic. Rounds are now always computed by `round_at`.
- **The protocol.** `docs/truth/sealed/CONTEST-PROTOCOL.md`: commit 72 hours ahead (code hash, claims'
  hashes, launch round); the seed mixes the launch round's signature and the code hash; hourly reveal
  with a chained digest; anyone recomputes; what it protects and what it does not; the recorded
  fallback (a hash commitment, weaker and labelled).

## Decisions of this session (continued)

- **S3-D-05 (2026-11-18). The Sentinel-alone port is deferred to session 4.** About 600 lines with
  data dependencies; F-01 already shows the Sentinel binds every traced decision; arms E and O, the
  twin and the objective were the kernel's acceptance.
- **S3-D-06 (2026-11-18). The pre-registration was attacked before it was sealed, and every finding
  was adopted or adapted** (S3-M-32): once sealed, a change is a deviation.
- **S3-D-07 (2026-11-19). The seal's date is the commit's**, 2026-11-19 (UTC), not the day the draft
  was written.
- **S3-D-08 (2026-11-18). The pre-commit layer (F-34) is recorded, not repaired here.** Repairing it
  re-enables every hook at once; each must first be run against the tree (session 4's work).
- **S3-D-09 (2026-11-19). The seal is anchored in Bitcoin through OpenTimestamps**, on the
  operator's answer "Yes, anchor it" to the offer in stage D: a timestamp that does not depend on
  GitHub, for the cost of sending a nonce-blinded digest to four public calendars. The proof sits
  beside the seal on #99 and is not sealed itself, so its later upgrade is no deviation.

## The panel at the close

| Reviewer | Verdict | Evidence or condition |
|---|---|---|
| Domain expert | Passes, with a condition | The objective is in money with cited weights; the incumbent is the strongest classical family a planner would run, tuned to convergence and per cell. Condition: the new world must make waste depend on stock and age (F-30), or the weights still do not bite |
| Architect | Passes | One light kernel beside an untouched legacy, bound by bit-parity tests; the verifier and the verdict are separate tools; three workflows, each proving one claim |
| Adversary | Passes, with notes | Seeds from a round that does not exist yet; the code's hash inside the contest's seed; no redraw for our own failure. Open: F-34 (the hook layer never ran) |
| Verifier | Passes | Verdict 16 of 16; closure tests fail on three planted faults; beacon on RFC vectors, a real round, three tamperings and a second implementation; the seal's checker fails on a changed value; the merge rehearsal's trees equal `main`'s. Gap: the Sentinel-alone parity |
| Operator at 3 a.m. | Passes | The false sev1 stream is stopped and the way back recorded; the verdict's exit code names the failure class |
| Release engineer | Passes, with a lesson | Small PRs merged in order with trees equal to the rehearsal; but a composition defect reached `main` for hours (E-TP-07), and the generated gate surface had to be regenerated after each merge |
| Maintainer | Passes, with a note | Two code lines, legacy and kernel, held together by tests; the kernel is a mechanical port and carries legacy idioms; ADRs for the kernel and the verdict are owed |
| User | Not yet | Nothing a visitor sees changed |
| Performance engineer | Partly | Verdict measured (25 s on CI, about 45 s on mains, median 59.5 s on battery); kernel speed against the legacy not measured separately; browser unmeasured (W4 not done) |
| Craftsman | Passes | Eight unused reader constants removed from the kernel; no dependency beyond numpy and simpy in the kernel; `py_ecc` stays in the verifier |
| Store manager | Not yet | The sealed incumbent and objective are the first parts that speak to a store's day; nothing runs a store |
| A stranger | Not yet | The beacon and the contest protocol are the mechanism that will let a stranger check; the page that shows it is session 9's |

The user, the store manager and the stranger are not satisfied, each for a reason this session's
scope could not remove (nothing visitor-facing was due); each is a later session's first item.

## Scorecard (session 3 close)

"Beyond" only where both values are verified and measured the same way. Rows 1 to 16, PV, KB, U and
W carry `FRONTIER.md`'s definitions; P1 to P6 are this session's engineering properties (gate,
section 2). The calibration was not found wrong; P1's mains-power target (30 s) was missed and is
graded as such, not lowered.

| # | Frontier property | Frontier reference and its value | At session start | At session end | Evidence and how to reproduce it | Status | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Cost against a tuned rule | Learned policies 0.79% to 5.68% better than base stock (EX-02, checked) | Consensus 3.9073 vs tuned 2.5119, worse 12 of 12 (miniature, unmerged tree) | The same on `main`, to the bit, on Windows and Linux | `make verdict`; S3-M-17, CI verdict job | Verified | Behind |
| 2 | Knowing where the rule loses | Long lead times, shifting or censored demand, perishability | Primary cell only | The cells and tests that will map it are sealed | PREREG-1 sections 6, 7 | Verified (document) | Behind |
| 3 | Internal validity | Pre-registration, paired seeds, power, controls, negatives published | Weights from the measured agent; margin statistical; seeds known | Weights, margin, incumbent, parity, freezes, seeds from a future beacon round, analysis: sealed before the world exists | `check_prereg.py`; PR #99's merge time; `SHA256SUMS.ots` (S3-M-34, -35) | Verified (sealed, not executed) | Level in design |
| 4 | External validity | Simulator validated on history | Declared twin | Unchanged; a calibration target named | PREREG-1 section 2 | Verified | Behind |
| 5 | Reproduction by a stranger | Results reproduced by another team (snippet) | Minutes, heavy stack, exported tree | One command; arms E and O reproduce with numpy and simpy only, on Windows and Linux | `tests/kernel`, `kernel.yml` | Verified (native) | Behind (browser not yet) |
| 6 | Assortment and demand | 2,000 to 40,000+ items (fetched) | 10 equal items | Unchanged | - | Verified | Behind |
| 7 | Operational structure | Hub and spoke; 65% of records wrong (checked) | Waste a clock | Unchanged; batches, shelf lives and shocks sealed as cells | PREREG-1 section 6 | Verified | Behind |
| 8 | A user | Anyone who plays | None | Unchanged | - | Verified | Behind |
| 9 | Architecture earns its complexity | Ablation evidence | One agent bound 372 of 372 | Unchanged; ablations now pre-registered | PREREG-1 section 7 | Verified | Behind |
| 10 | Agents that act | Appropriate, recorded actions | Category errors | Unchanged | - | Verified | Behind |
| 11 | Path to production | Merge to a verified live system | No deploy since June; every merge opened a false sev1 | No deploy target; the dead workflows disabled; 8 stale sev1 closed | G5 | Verified | Behind |
| 12 | Reliability | 99.9% over five days (target) | Nothing | Unchanged | - | Unverified | Behind |
| 13 | Cost | $0 floor | ~$70 estimated | $0 spent; no cloud | - | Verified | Level |
| 14 | First minute | A cold reader can say what happened | Not seen | Unchanged | - | Unverified | Behind |
| 15 | Checks able to fail | Every load-bearing check shown failing | Safety 5 of 5; no quality check below E5 | Verdict 16 of 16; closure 3 of 3; beacon tamperings and RFC vectors; the seal's checker; the I-1 parity test on the real false positive | S3-M-21, -24, -26, -29, -33 | Verified | Level |
| 16 | No exposure | No default credential; no open control | Defaults published | Unchanged; F-34 found | F-34 | Verified | Behind |
| PV | Public verifiability | drand quicknet, threshold BLS (checked) | None | A real round verified by two independent implementations; the contest protocol written | S3-M-29 | Verified | Level |
| P1 | Time from a change to a trustworthy verdict | >99.9% of faulty changes caught at half the cost (Machalica 2019, snippet) | Safety 18 to 46 s, no quality; quality only via labelled E5 (53 min + latency) | 25.2 s on CI; about 45 s on mains; median 59.5 s on battery; safety, quality, determinism and environment | S3-M-23, CI verdict job | Verified | Level (the 30 s mains target missed) |
| P2 | Exactness of parity between runtimes | Box2D 3.1 bitwise across platforms (snippet) | Trace identical Linux and Windows; no kernel | The E5 miniature's 24 costs identical on Windows and Linux (CI); kernel equal to the harness to the bit on 12 seeds, arms E and O, on both | CI verdict and kernel jobs | Verified (native) | Level natively; browser unmeasured |
| P3 | Dependency weight in a browser | Pyodide ~6.4 MB + numpy ~3 MB (snippet) | Twin 12 packages; tuned rule 19 | Kernel: numpy and simpy, measured at run time | S3-M-26 | Verified | Level |
| P4 | Keeping the legacy green | Characterization tests beside an untouched legacy (recalled) | Any edit voids sealed records | Zero legacy edits; parity in seconds (light job) and a minute (parity job) | S3-M-28 | Verified | Level |
| P5 | Pre-registration strength | Timestamped registration; public randomness for draws (recalled) | Choices open | Sealed with hashes before results, attacked before sealing, seeds from a round that does not exist yet; the seal's hash in Bitcoin blocks 976528, 976529 and 976535, each checked against two explorers | S3-M-32 to -35 | Verified | Level (no reference measured the same way) |
| P6 | Verifiable public randomness | drand verification libraries | None | Verified natively and cross-checked; protocol written | S3-M-29 | Verified | Level |
| KB | Readings of SYNAPSE | Each confirmed, corrected or refuted | Local branch only | On `main` (#93), verbatim overlap 0 | S3-M-15 | Verified | - |
| U | Preserved behaviour | - | - | Fast selection and miniature identical on `main`; physics digest unchanged; ledger files changed only on placeholder lines; `frontend-gates`' 20 files, other worktrees, the stash and `.kiro/settings/` untouched | S3-M-12, S3-M-17, the close's re-hash | Verified | - |
| W | Made worse or less certain | - | - | `main`'s quality gates red for hours (`8c48635` to `9aa2aad`) from a composition defect; two workflows disabled by decision; the Sentinel-alone parity, Pyodide parity and the sandbox not measured | S3-M-21 | Verified | - |

## Final account

**Built and proven.** The work in flight landed with nothing lost: #87, #91 and #90 merged in order
with trees byte-identical to a local rehearsal, the ledger committed with verified facts only, and the
knowledge base and the truth record on `main`. A one-command verdict judges the decision core's
safety, decision quality, determinism and environment in about a minute (25 s on CI), shown to fail
on 16 of 16 known faults and to pass clean three times. A light decision kernel (numpy and simpy only)
reproduces the legacy harness to the last bit for the twin, the objective and arms E and O, on
Windows and Linux. The release's scientific choices are sealed, after a fresh-context attack, with
confirmatory seeds bound to a beacon round that will not exist until 2026-12-11. The beacon is
verified by two independent implementations against the standard's vectors and a real round.
After the close, with the operator's approval, the seal's hash was stamped through OpenTimestamps
and stood in three Bitcoin blocks within about ninety minutes, the first mined nine minutes after
the stamp: anyone can check the seal's date against Bitcoin without trusting GitHub (S3-M-34, -35).

**Found.** A composition defect two green PRs created together (the I-1 grep), repaired the same day
(#95). F-33: the legacy twin's physics reads `TW_*` environment variables, invisible to every sealed
digest. F-34: the pre-commit layer has never run. And the legacy engine seeds the global `random`
module with the replicate seed, which makes stray stdlib randomness deterministic.

**Not achieved, and why.** The Sentinel-alone parity (deferred, S3-D-05); Pyodide parity (W4 approved,
not reached); the Docker sandbox (the credit was never confirmed claimed); the 30 s mains-power target
for the verdict (45 s: the agent stack's import and the consensus arm's run set the floor).

**Uncertain.** Whether the new world (session 5) can make waste respond to stock and age while staying
calibrated; whether any challenger can clear one point of fill in money in the shock cells; whether
the browser reproduces the kernel's bits.

## Work for session 4, in order

1. **Done in session 3: the seal's timestamp upgraded and checked** (S3-M-35). A later `upgrade` may
   add the `finney` calendar's attestation; nothing depends on it.
2. **The Sentinel alone against the consensus arm, in the kernel** (S3-D-05), bit parity on E5's twelve
   seeds, recorded either way.
3. **The truer world in the kernel** (session 5's row, begun early): batches that age, skewed items, the
   fitted intraday shape with its masking check, the cells exactly as sealed; legacy mode kept.
4. **The incumbent tuned exactly as sealed**, its evaluation counts published.
5. **F-34**: repair the pre-commit YAML, run each hook over the tree, wire or retire by D-5; correct
   `CLAUDE.md`'s claim about `no-raw-hex` until then.
6. **Pyodide parity** (W4): the kernel's digests under Pyodide and a simulated day's time there.
7. **ADRs** for the kernel and the verdict.
8. **Freeze W** at the end of the world's work; **freeze C before 2026-12-11T00:00:00Z.**
