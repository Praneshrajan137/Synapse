# TRUTH-MAP - SYNAPSE as it is

**Status: 2026-11-17, after window 1 of five; F-33 and F-34 added by session 3, 2026-11-19.** Sections 1 to 3 cover the decision path, the
proof and the release path. The component table (section 5) has sizes and not yet a verdict on
what runs. Section 6 lists what has not been examined. Nothing here is final until the session
closes; every finding says how it is known and what would prove it false.

How each statement is known: **measured** (this session ran it; the command is in
[`LOG.md`](LOG.md) under the cited M-nn), **read in source** (the main session read the cited
lines; V-nn), **reported** (a mapping subagent read it; not yet re-read), **read** (a ledger or
document says it), **operator** (the operator said it; OA-n), **inferred**.

Which tree: `main` (`d4f985c`) still carries finding 112, so its agents read none of their
request. Unless a finding says otherwise it describes the repaired tree of pull requests #87
and #91 (`1c484fb`), which is not merged.

## 1. What one decision does

### The trace, expected against actual (R-17)

The expected column is the documented design (`CLAUDE.md`, ADR-052, ADR-053). The actual column
is what was measured or read.

| Stage | Documented | Actual | How known |
|---|---|---|---|
| Trigger | The sensor loop perceives the world and convenes consensus on a breach or a disruption | One trigger exists: an item below its reorder point. Nothing produces a disruption trigger. The request asks for a fixed quantity, four times the reorder point, for each low item | V-05; reported |
| Tier | Four tiers by difficulty; the upper two bring debate, an LLM and a simulation | The tier is set by four keys of the request. The sensor sends none, so every decision it convenes is tier 2 | V-01, V-05 |
| Proposals | Eight agents propose from the request and the state of the world | Six propose. Five of the six return the same score whatever the world holds. Two return nothing | M-19 |
| Debate | Agents debate and revise | Not run in tier 2. In tier 4: one round, which lowered the winner's score and changed no order | M-20, M-21 |
| Arbitration | A Pareto front; the knee point binds | Tier 2: the largest `utility_score`, which in most agents is the agent's own confidence. Tier 4: a weighted sum that picked the same agent every time | V-02, M-20; reported |
| Gate | Below a confidence floor a person decides | The floor tests the winner's own confidence. It never fired in 372 decisions. Had it fired, nothing would have executed, with or without a person's approval | M-19, M-20, V-04 |
| Execution | The consensus action is executed | Every proposer executes its own proposal, not the selected one | V-03 |
| World change | Agents' actions change the world | The Inventory Sentinel reorders. The forecaster scales customer demand. Others move policy levers or publish events | V-06; reported |
| Audit | A hash-chained row with the execution's confirmations | The row is written before execution and cannot be updated; the confirmations stay in memory | V-09 |
| Outcome | Each decision is scored confirmed, diverged or unknown, and confidence is calibrated against it | The scorer reads the stored confirmations, which are empty, and no twin signal is joined, so every outcome is `unknown` | V-09; inferred |
| Learning | The orchestrator learns from the realised world | A weight update of step 0.001 on weights held in memory, read only by tiers 3 and 4, from a system state that is three constants | V-10; reported |

### Findings

- **F-01 One agent makes every decision (measured, M-16, M-18, M-19, M-20).** In 372 traced
  decisions across five seeds, three ways of driving the world and both paths, the Inventory
  Sentinel bound 372. *False if* any traced decision is bound by another agent.
- **F-02 Five of six proposals carry no information about the world (measured, M-19).** Across
  360 states, including a store drained to zero, `demand_prophet`, `routing_navigator` and
  `sustainability_agent` returned utility 0.5, and `disruption_shield` and `supplier_trust`
  0.3, without one exception. Reported cause, with the lines to check: each returns a fallback
  or a configured default because the reorder request carries none of its inputs and no model
  or feature source is present (`agents/demand_prophet/inference/pipeline.py:38`,
  `agents/sustainability_agent/inference/pipeline.py:28`,
  `agents/disruption_shield/config.py:47`, `agents/supplier_trust/config.py:28`,
  `agents/routing_navigator/inference/pipeline.py:172`). The constants are thus a joint product
  of the request E5 builds and of the agents' fallbacks. On the live path the sensor's request
  carries even fewer fields (V-05), so the same fallbacks are expected there (inferred, not
  run). *False if* any of the five scores varies with the world on the E5 path.
- **F-02a Every decision is bound by a self-declared degraded proposal, and the gate does not
  look (measured, LOG M-31).** In 24 of 24 E5 decisions the binding proposal's provenance says
  `degraded=True`, basis `fallback_floor`, while its confidence reads 0.85 to 0.97, so the 0.7
  confidence floor passes it. The honesty flag the project built (ADR-040, ADR-044) is
  recorded and never consulted where it matters. One agent's flag errs the other way: Supplier
  Trust reports `degraded=False` for a score that uses no data. *False if* the gate or the
  selection is shown to read `degraded`.
- **F-03 Two agents never propose in E5, both because of the request E5 builds (measured, M-19,
  M-30).** The Pricing Oracle refuses a request with no categories and no base prices, by its
  own precondition. The Freshness Guardian refuses a request with no `store_id`, and the
  harness's request has none: a gap of finding 112's class, in the harness rather than the
  agent. The sensor's live request carries `store_id`, so on the live path the Freshness
  Guardian would propose.
- **F-04 Selection is the largest self-reported confidence (read in source, V-02; reported).**
  The fast path takes `max(proposals, key=utility_score)`. Six of eight handlers set
  `utility_score` to their own confidence (reported). The confidence floor is then applied to
  that same number, so the gate asks the winner how sure it is.
- **F-05 The upper tiers are unreachable from autonomous operation (read in source, V-01,
  V-05).** Debate, arbitration, the LLM and the twin check need a request flagged as a
  disruption. The sensor never sets the flag. Whether a request posted through the API can set
  it is not yet read.
- **F-06 Where the full path does run, it chooses what the fast path chooses, at about a
  hundred times the cost (measured, M-20, M-21).** Twelve tier-4 decisions bound the same
  agent. Six states put through both paths gave identical orders in all six, at 1.3 to 1.9 s a
  decision against 0.013 s. The twin check, the step that takes most of that time, returned
  `twin_unavailable` on this machine. *False if* any paired state yields a different order.
- **F-07 On the live path, selection does not decide what is executed (read in source, V-03).**
  Each proposer is sent its own proposal to enact. The E5 harness applies only the selected
  action to its twin (reported). So E5 measures an execution rule the live system does not use.
- **F-08 A withheld decision is a dead end (read in source, V-04).** Nothing executes on
  timeout, and nothing executes when a person approves. An operator can neither release nor
  amend it. This answers R-32 and most of R-28.
- **F-09 The forecaster's `execute` changes the demand it forecasts (read in source, V-06).** It
  sets the world's arrival-rate multiplier from the ratio of its point forecast to its lower
  bound. In a real store no such lever exists.
- **F-10 No decision can be recorded as confirmed or diverged (read in source, V-09; the
  conclusion inferred).** The audit row precedes execution and is append-only; nothing else
  stores the confirmations; the scorer reads only that row. The calibration surface therefore
  has no scored decisions to draw on. *False if* a live decision is stored with any outcome
  other than `unknown`.
- **F-11 What learning amounts to (read in source, V-10; reported).** The meta-learner's
  "system state" is the hour and two constants. Its weights live in memory and are lost on
  restart. Tier 2 records them and does not use them.
- **F-12 The eight agents are components (reported; consistent with M-19).** None runs a loop,
  holds an objective it pursues between calls, or starts anything. Each is a function of the
  request it is handed. Initiative lives in one place, the sensor loop. Two have a training
  loop that takes gradient steps (`demand_prophet`, `pricing_oracle`); the others fit simple
  models on synthetic data or save calibration values (reported). This answers R-22 pending a
  sample re-read.

## 2. The proof

- **F-13 The repaired arm loses to the tuned rule, and the loss reproduces here (read, RD-01;
  measured, M-23).** E5: -1.4463, interval [-1.4650, -1.4286]; fill rate 0.762 against 0.939
  at about the same stock. A twelve-replicate miniature on this laptop, at E5's own seeds and
  price, gives -1.3954, with the consensus arm worse in 12 of 12.
- **F-13a Most of the loss is one estimate in one heuristic: a demand rate that ignores the
  day's shape (measured, M-24, M-32; part inferred).** Until a supplier's first order lands
  the Sentinel plans against a 24-hour lead-time prior, which over-orders. Afterwards it plans
  over about 6.4 hours of lead time plus review (median of 503 readings, 3.3 to 11.5), at a
  demand rate averaged since the run began: about 8.5 units an hour per item, where the true
  average is 11.8, and with no account of the evening peak. Tripling only that later plan, in
  a what-if fitted to the same twelve seeds, takes the difference from -1.3954 to -0.1578,
  still behind. The factor that works is close to the ratio of the evening peak to the
  run-average so far (inferred by the second reviewer from the demand profile). So the result
  is a verdict on one rule's demand estimate, not on eight agents. The structure-aware arm O,
  which knows the day's shape, beats the tuned rule (F-29): the missing information is exactly
  what a forecaster could supply. *False if* a shape-aware rate, fitted on held-out seeds,
  leaves a gap of the original size.
- **F-14 The proof runs on the laptop and repeats exactly (measured, M-18, M-23).** The trace
  is byte-identical to the CI artifact. Every one of 24 replicate repeats was identical to the
  last digit. A replicate takes 0.6 s, so E5's 2,000 runs are about twenty minutes here against
  53 minutes as a labelled CI job, and a twelve-replicate check takes half a minute. This
  answers R-43 and changes what the implementation sessions can verify without CI.
- **F-14a The objective's weights have no source outside the project (read in source, V-11).**
  Unfilled demand is priced at 8, stock and spoilage at 1, from the default costs of the very
  agent E5 measures; the delivery weight is marked "chosen". Under these weights stock is
  cheap, so the tuned rule's high levels win. Whether a practitioner would rank outcomes this
  way is unasked (R-29).
- **F-15 E5 covers less of the system than its name suggests (read in source; measured).** It
  runs the unshocked cell, so tier 2 only (M-19, V-01); with the LLM replaced by an offline
  stand-in (reported); with execution replaced by the harness's own translation of the selected
  action (reported, F-07). Its verdict is about the Inventory Sentinel's reorder rule.
- **F-16 A shocked cell costs about a hundred times more per decision (measured, M-21).** At
  1.3 to 1.9 s, E5's 24,000 decisions would take roughly 9 to 13 hours of consensus time on
  this machine, and more wherever the twin check runs to its cap. Whether any shocked cell was
  run for the consensus arm is still to be read in the ledger (R-02). An earlier figure of
  24 s was this session's own instrument error and is retracted in the log (M-20).
- **F-17 One of the harness's own checks is open (read, RD-06).** The controls' agreement check
  reads `harness_mis_measuring` (finding 117), awaiting the operator.

- **F-29 On the cell E5 measures, no policy without hindsight on record clears the margin
  (measured from the committed record, LOG M-25; the conclusion inferred).** The tuned rule is
  0.630 above the hindsight oracle. A base-stock rule that knows the world's declared demand
  shape and lead times beats the tuned rule by 0.246, interval [0.214, 0.276], against a
  margin of 0.4. A material win would have to take nearly two thirds of the clairvoyant's
  advantage without its foresight. The record's verdict `room_to_win` tests the clairvoyant
  ceiling, not an attainable policy. Arm O is the only attainable arm on record, and it is
  analytic and untuned; its own module says it is not optimal here (`uplift/oracle_arm.py:10-27`,
  reported by the second reviewer), so the attainable bound is unmeasured. Compared as the
  literature compares (LOG EX-02: learned policies 0.8% to 5.7% better than base stock), a win
  by the margin needs a policy 7.0% better than the base-stock arm O: above the best published
  figure, not out of reach in principle. *False if* a policy without hindsight beats the tuned
  rule on this cell with the low end of its interval above 0.4.
- **F-30 In the twin, waste is a clock (read in source; measured from the record, LOG M-25).**
  In the primary cell each item "spoils" one order about every 80 simulated minutes, whatever
  is held or ordered, and the spoiled order takes no stock away; the monsoon scenario doubles
  the clock's rate, and the cold-start scenario resets it so that cell records no spoilage
  (the last two reported by the second reviewer). Spoilage cost is 0.0589 in every arm,
  including one that never orders. Delivery cost is nearly the same in every arm (1.282 to
  1.287). So 55% of the tuned
  rule's cost answers to no decision, holding stock costs only its on-hand term, and the
  perishability that drives real dark-store waste is absent as a consequence of any decision.
  The Freshness Guardian has nothing in the twin to act on. *False if* a cell or world source
  makes spoilage depend on stock held or its age.

- **F-33 The twin's physics reads the environment (read in source; shown by test, session 3).**
  `digital_twin/simulation/engine.py:286` builds `TwinConfig()`, a pydantic `BaseSettings` with prefix
  `TW_`, so `TW_ORDER_ARRIVAL_RATE`, `TW_PICK_PACK_MEAN_MIN` and `TW_PICK_PACK_STD_MIN` change every
  legacy twin run, E5 and B-prime included, while no sealed source digest changes. Shown:
  `tests/kernel/test_legacy_parity.py::test_a_tw_variable_moves_the_legacy_twin_and_not_the_kernel_finding_f33`
  (the legacy cost moves at seed 0, the kernel's does not), and the verdict's fault proof case Q6b
  (the tuned control moves by +0.102). The kernel reads no environment; `python -m scripts.verdict`
  refuses to run while a `TW_` variable is set. *False if* setting `TW_ORDER_ARRIVAL_RATE` leaves
  E5's per-seed cost unchanged.

## 3. The release path

- **F-18 Nothing is deployed and nothing remains of the last deployment (measured, M-08;
  operator, OA-1).** The last run that deployed was 2026-06-14. All 22 scheduled deploys since
  failed. The account that held the machine has expired.
- **F-19 No documented command starts the whole system today (read in source, V-07).** The
  local compose file has neither the API, the twin nor any agent; its one-command target waits
  for a service the file does not define and then proceeds. The compose file that has all 23
  services pulls from a registry that no longer exists. Not yet run. *False if* `make demo-up`
  on a fresh clone yields a decision on the console.
- **F-20 The Terraform is untested as written (read in source, V-08; part inferred).** Its
  identity pool and provider carry different names from the ones the failing workflow asks
  for, so the June environment was not built from it. Its default repository name differs in
  case from the repository's real name, and the provider's condition is an exact comparison.
  The web server's configuration names the old machine's address and its certificate.
- **F-21 From an empty project to a console a reviewer can open: about eleven steps by hand
  (reported).** Among them: enabling cloud APIs the Terraform does not enable; a key pair;
  variables; `terraform apply`; a setup script run over SSH that installs the container engine
  and the LLM server; seven repository variables; one workflow dispatch; a host name and a
  certificate, without which the web server will not start.
- **F-22 Capacity (reported; checked; measured).** The 23 services declare memory limits
  summing to about 26.75 GB on a 32 GB machine, before the LLM server on the host, budgeted at
  4 to 5 GB. The CPU limits sum to about 15.7 on 8 cores. The trial allows 8 cores in all
  (EX-01). The laptop has 15.7 GB (M-12).
- **F-23 No GPU is part of the design, and five days cost about $40 (reported).** A search of
  the cloud configuration finds no accelerator. The price is from a third-party table and is
  not yet confirmed from a primary source. This differs from the operator's expectation (OA-5).
- **F-24 The LLM server is carried for a path that autonomous operation never reaches (reported
  with F-05).** The orchestrator's one call site is inside debate. The Disruption Shield has
  its own reasoner, which is not yet examined (R-19).

## 4. The apparatus, so far

- **F-25 The watchdog has never observed the system (measured, M-08).** 26 runs, 26 failures:
  first because the machine was not running in its window, then at authentication.
- **F-26 A gate passed on a category error (read in source, V-06; measured, M-11).** The agency
  audit reports eight of eight agents reaching an actuator. One of the eight does so by
  changing customer demand (F-09). The count went to its target and the meaning did not follow.
- **F-27 A gate passes over an empty loop (inferred from F-10).** The outcome gate forbids a
  fabricated "confirmed". It is satisfied because every outcome is `unknown`.
- **F-28 The gate surface (read, M-17).** 68 checks; the README reports 56 passing and 12
  skipped. Which can be made to fail is window 4's work (R-24).

- **F-31 The decision core's safety behaviour is well guarded; its quality is not unit-tested
  (measured, LOG M-26).** Five faults were introduced one at a time; every one failed at least
  one test, the confidence floor fifteen. Two were caught only by tests that pin the present
  design: tripling the Sentinel's review period, which scales its plan by about 1.3, fails the
  same test whatever its effect on cost. Judging a decision's quality is left to E5, which
  runs when a person labels a pull request.
- **F-32 The proof can now run where the work is done, and the pace may depend on it (measured,
  LOG M-23; read, LOG M-27; the cause inferred).** The last spec moved from about a day and a
  half a session to two weeks; its session rows describe waiting on labelled CI runs, so CI is
  the likely cause, inferred from the dates and the rows, not measured. A replicate takes 0.6 s here. Keeping
  verification local is the difference between four sessions before the release and eleven.

- **F-34 The pre-commit layer has never run (measured, session 3).** `.pre-commit-config.yaml` does not
  parse as YAML at any commit from its creation (`c8f1e3e`) to `main`: the `reward-isolation` hook's
  multi-line `entry` puts code at column 1. No `pre-commit` hook is installed in `.git/hooks`, and no
  workflow runs pre-commit. So no hook in it (`no-raw-hex`, `no-paid-apis`, `spec-validate`, ...)
  enforces anything, though `CLAUDE.md` cites `no-raw-hex` as the guard of INV-CLR-009. Parsed, the
  multi-line `python -c` entries would still be folded into one line by YAML. *False if*
  `pre-commit validate-config` accepts the file. Recorded as `CLAUDE.md` E-TP-08.
  **Repaired in session 5 (#107):** the file parses; nine hooks run their CI step's own text, four run
  in `hooks.yml`, each shown failing on a plant; gitleaks stays local-only (truth log S5-D-04).
- **F-35 The dataset's volume is recoverable (falsified, session 5).** Feared that FreshRetailNet-50K
  fixes only shapes; measured that units are 10 times the hourly value (99.56% of positive values lie
  on a 0.1 lattice; the noise floor of daily totals has slope near one), so the store's volume is
  fitted (truth log S5-M-18).
- **F-36 A world drawn with numpy's `Generator` cannot promise native-browser parity (checked,
  session 5).** numpy does not promise its distribution streams across versions or CPUs. The release
  world draws with counter-based Threefry-2x32-20 and exact samplers instead, and gives the same bits
  on Windows, Linux and Pyodide (S5-M-21, -37, -38).
- **F-37 FreshRetailNet's stock flag is an out-of-stock flag (measured and checked, session 5).**
  `hours_stock_status` = 1 means out of stock, the complement of the paper's censoring indicator.
- **F-38 PR #77 broke the colour spec's structure (measured, session 5).** It replaced the
  `preconditions:` header of `color-system.spec.yml` with seven invariants, leaving two preconditions
  inside the invariant list; the hook that validates the spec never ran (F-34). Restored in #107.
- **F-39 Two stale corners (measured, session 5).** `orchestrator/contracts/twin_simulation_contract.py`
  is collected by no job; `docs/state/MODULE_INVENTORY.md` is ungated and stale. Not repaired.
- **F-40 Claim C2 has room in S1 only (measured, session 5; revised after freeze W's attack).** Even
  an oracle told the shock clears `M_c` only in S1 (+34.0 against 16.0); in S2 and S3 the best
  informed oracle gains +0.1 and +8.0 against 14.5, and planning against a supply shock the gate's way
  loses -85 and -214 a store-day. C2 in S2 and S3 should be expected null (S5-M-40).
- **F-41 No job ran the seal's checker (measured, session 5).** An edit to PREREG-1 would have failed
  nothing, and each checker trusts its own sums file. Freeze W's pull request adds `seals.yml`: both
  checkers and an add-only rule for `docs/truth/sealed/`.

### Where the documents and the code part

| Document says | Found | How known |
|---|---|---|
| `CLAUDE.md`: six of eight `execute()` methods do not act | The project's own audit finds none a stub | M-11 |
| `CLAUDE.md:76`: the watchdog runs twice a day | Weekly | M-08 |
| `CLAUDE.md:163`: the repository is private under another owner | Public | measured |
| `CLAUDE.md`: a merge yields a verified live system or a red workflow and an issue | Red workflows and issues, yes; no live system since 2026-06-14 | M-08 |
| `CLAUDE.md`: the stop policy is a three-hour morning window | The Terraform sets a daily stop at 17:30 UTC; the morning window was attached by hand | reported |
| `CLAUDE.md`: arbitration binds through the knee of a Pareto front | True of tiers 3 and 4 only, which autonomous operation does not reach | V-01, V-02 |
| ADR-047 as summarised in `CLAUDE.md`: the outcome loop is closed | Every outcome is `unknown` by construction | F-10 |
| `Makefile:384`: one command from a fresh clone | The stack it starts has no agents, twin or API | V-07 |
| `engine.py:838-839`: a shock brings "more holding/spoilage" | Spoilage never depends on holding | F-30 |
| Finding 123: deploys fail since at least 2026-08-17 | Every scheduled deploy has failed, from the first on 2026-06-22; no run has deployed since 2026-06-14 | M-08 |
| `README.md:66`: 38 decision records | 58 files in `docs/adr` on `main`, two more on branches | M-04, M-22 |

## 5. Components

Sizes are from M-04. "Runs" will be filled in window 3 from the compose files, the workflows
and the import graph.

| Component | Source lines | Tests | Runs today |
|---|---|---|---|
| Eight agents | 14,092 | 10,792 | In-process in the harness: yes (M-19). As services: nowhere (F-19) |
| Orchestrator | 8,984 | 11,439 | In-process: yes. As a service: local compose only, without agents |
| Shared package | 6,753 | 9,917 | Imported by the above |
| Digital twin | 3,966 | 3,354 | In-process: yes. As a service: nowhere |
| API | 3,645 | 2,294 | Nowhere |
| Data fabric | 2,174 | none beside it | To be established |
| ML pipelines | 1,334 | 122 | To be established |
| Console | 24,278 | 14,726 | To be established |
| Proof harness | 18,375 | 66,574 with the gates' | In CI by label; locally in part (M-18) |
| Audit gates | 32,743 | counted above | In CI |

## 6. Not yet examined

Headroom in the shocked and adversarial cells, and what a practitioner would make of the
objective's weights (question C).
Leakage between arms, and the open agreement flag (F). The console, seen running (E). Which components
anything runs (G). Which gates can fail and how each named finding was caught (H). The
invariants, by fault injection. The data fabric, the ML pipelines and the training code beyond
what F-12 reports. Security beyond the list of published defaults. The live path with real
services: everything in section 1 marked "read in source" describes code that has not been
watched running outside the harness.
