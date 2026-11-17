# PLAN - SYNAPSE to the world: from session 2 to a five-day public release

**Status: 2026-11-17, end of session 2; version 2.** Written after the operator's reframe (LOG
OA-7): the release is for the whole world for five days. Version 1 of this file was attacked by a
reviewer with fresh context the same day; its main criticisms were checked and accepted, and this
version is rebuilt around them (section 16 lists what changed). This file supersedes the
audience, release architecture and session path in [`DIRECTION.md`](DIRECTION.md), whose analysis
of the evidence still stands.

Evidence identifiers resolve in [`LOG.md`](LOG.md) (M, V, RD, EX, OA) and
[`TRUTH-MAP.md`](TRUTH-MAP.md) (F). Labels: **measured**, **read**, **checked** (an outside page
opened by the main session), **reported** (a subagent's return), **inferred**, **judgment** (an
estimate with its basis), **dream** (a goal with no evidence yet that it is reachable).

## 0. The plan on one page

- **The real problem.** In fast grocery each order trades a lost sale against waste, demand peaks
  within the day and is hidden by stockouts, and fresh stock spoils in days. Large operators
  build their own systems; everyone else runs static min-max rules and has no way to know whether
  anything smarter would do better (section 1).
- **What SYNAPSE can uniquely offer.** Not a claim that AI wins, but an honest, verifiable answer
  to "where does a smarter policy beat a strong rule, by how much, and at what risk?" Its proof
  harness already does what the tools and benchmarks found do not (section 1.3).
- **The release: "SYNAPSE Open Dark Store".** Three things, in this order of importance:
  1. **Play.** Run a simulated dark store in your browser against a strong rule and against
     SYNAPSE, on the same demand; some players get SYNAPSE's advice, assigned at random.
  2. **The public contest.** SYNAPSE and the strong rule run identical simulated stores for five
     days, with demand drawn from a public randomness beacon as the days pass, so nobody,
     including us, can know or choose the outcome in advance, and anyone can recompute every step
     in their own browser.
  3. **The proof.** Every claim pre-registered before launch, the map of where each part helps and
     where it does not, the project's own negative results, and how to check all of it.
- **Architecture.** No server is needed for any of it: a static site on a free CDN, the twin and
  policies running in each visitor's browser, randomness from a public beacon. A visitor costs
  nothing, so a million cost nothing more than ten. The cloud accounts are reserved for a live
  mirror that shows the full governed system computing exactly what the browsers compute (the
  target tier), and for heavy verification (section 6).
- **What changes underneath.** A strong incumbent (tuned per item and per part of the day); a
  world with modelled shelf lives, many skewed items and an intraday demand shape fitted to real
  data; challengers that must detect trouble from what they observe; the economic weights and
  the margins fixed and sealed before any result on the new world exists (section 5).
- **Sessions.** Eleven (session 3 and ten execution sessions), 2026-11-18 to a launch on
  **Tuesday 2027-01-19**, each with one outcome, a test and a tripwire (section 9).
- **Odds (judgment, section 15).** An honest static release of what already exists: about 90%.
  The floor: about 55%. The target: about 30%. The dream: about 10%.

## 1. The real problem

### 1.1 What a dark store must get right

- A quick-commerce store carries thousands of items and serves 1,000 to 2,000 orders a day
  (secondary sources, reported). Demand peaks in the evening, jumps with weather and festivals,
  and is censored: a stockout hides the demand it turned away.
- Fresh items spoil in days, so every unit too many is waste and every unit too few is a lost
  order. Store ordering and replenishment were reported as the largest single cause of
  out-of-stocks in a 2002 industry study, about 47% (snippet); inventory distortion is put at
  about $1.7 trillion a year worldwide (IHL, 2025, snippet).
- Stock records drift from the shelf: 65% of records were wrong in the standard study of one
  retailer (EX-04).

### 1.2 Who decides today, and what they lack

- Large operators build planning in-house (reported). Everyone else runs static min-max rules;
  free tools such as Odoo's reordering rules are of this kind, and none found shows its user
  evidence that it beats a simple rule (reported, snippet-level).
- What is missing is **evidence**: on demand like mine, would a smarter policy really beat a
  well-tuned rule, by how much, and where would it fail? Vendors claim uplift without a test
  anyone can run.

### 1.3 Why SYNAPSE, and the gap it can fill

- **Its harness answers that question honestly.** Paired seeds, controls, power analysis, a
  hindsight oracle, pre-registered claims, and negative results published twice (F-14, RD-01,
  RD-06). It runs on a laptop in seconds and repeats exactly, even across machines (M-18, M-23).
- **The nearest benchmark leaves the hard parts out.** InventoryBench (2026) tests single
  products on weekly demand; it finds OR heuristics plus a language model beat either alone, and
  human-AI teams beat either alone in a classroom (EX-07). None found combines a strong tuned
  rule, a hindsight oracle, perishability, intraday time and censored real demand (reported).
- **No public AI experiment found was verifiable by its audience.** Project Vend and its kind
  were watched, not checked, and had no classical rule beside them (reported).

## 2. What seven months built, read as a whole

| Phase | Months | What it built | What it left |
|---|---|---|---|
| Foundation | April | Infrastructure, eight agents, orchestrator, twin, API, console | Every layer of a platform exists in some form |
| Hardening and reach | May to June | Resilience, multi-city, supply-chain security, audit chain, GCP deploy, design system, an honest console | Strong habits; a topology one person cannot run (F-22) |
| Verification | June | Gates, coverage truth, deploy truth, substance mandate | 68 checks; a watchdog that never saw the system (F-25) |
| Agency | June to July | The closed loop: sensor, standing world, actuation | Autonomy in form, one heuristic in fact (F-01) |
| Proof | July to November | The uplift harness and E5 | An honest negative result and its cause (F-13, F-13a) |
| Truth | November | This session | The map of what is real |

**The lesson.** The project built breadth before evidence, then built the evidence and found the
breadth hollow at the core. The next phase reverses the first: **depth at the core, reach at the
edge.** Make the few decisions that matter better where the evidence says they can be, prove it
in a way anyone can check, and reach the world through something that costs nothing per visitor.

**Kept and reused:** the harness; its exact reproducibility, which becomes the release's trust
mechanism; the colour system and the console's honesty vocabulary (M-36); the audit chain; the
safety tests that caught five of five faults (F-31). **Frozen, not deleted:** the streaming,
graph and orchestration topology, the Helm chart, the deep-model code with no trained model
(M-35), the multi-city overlay.

**Keeping the legacy green.** The new world and the kernel are built in their own package. The
existing engine, the harness, E5's lineage and the 110 tests, audit scripts and workflows that
reference them (measured by `git grep`) stay as they are and keep passing. The new code gets its
own fast checks. Nothing old is retired except by the experiment rule of D-5.

## 3. The ladder: what we can be sure of, what we intend, what we dream

| Rung | What the world gets | Odds (judgment) |
|---|---|---|
| 0 | An honest static release of what exists: the proof page with E5's history and today's map; the contest and Play on the current world, labelled with its limits; recompute-in-your-browser | About 90% |
| 1 Floor | Rung 0 rebuilt on the truer world: strong incumbent, modelled shelf lives, skewed items, demand shape fitted to real data; the pre-registered map; Play with randomised advice; the beacon-seeded contest | About 55% |
| 2 Target | The floor plus: a live mirror on Google Cloud running the full governed system on the same beacon and matching the browsers decision for decision; trace-driven runs on real store histories from FreshRetailNet-50K; challengers that detect shocks from data; a phone mode; opt-in anonymous play traces | About 30% |
| 3 Dream | The target plus: an open benchmark with outside submissions; a backtest on a visitor's own file; a hub of stores where coordination is tested; language-model entrants; a released human-AI dataset; a preprint | About 10% |

Section 15 gives the basis and the signals that will move these odds.

## 4. The product the world meets

### 4.1 The first minute

One page says, in plain words: two simulated dark stores are running, one by a strong rule and
one by SYNAPSE; here is what each has sold, wasted and missed so far; here is what we said we
would prove before it started; the demand comes from a public randomness source nobody controls;
and you can recompute every step yourself. Then: **play the store yourself.**

### 4.2 Play (first door)

- The visitor runs a store for one simulated day or week, ordering at each delivery slot, on the
  same demand the rule and SYNAPSE face, and sees fill, waste and money side by side.
- **Randomised advice.** Half of the sessions, chosen at random before play, show SYNAPSE's
  recommended order, which the player may take or amend. That makes the human-with-AI comparison
  a fair one (the reviewer's point: letting players choose would confound it).
- Runs entirely in the browser through Pyodide. Nothing is sent anywhere in the floor.

### 4.3 The public contest (second door)

- Two identical simulated stores, strong rule and SYNAPSE, on an accelerated clock (default one
  simulated day per real hour, D-14), for 120 hours.
- **Floor form: committed and revealed.** Before launch the code, the claims and the analysis are
  published with their hashes. At launch a round of the public drand beacon (reported: League of
  Entropy relays, HTTP API, signed rounds) seeds the run. The run is revealed hour by hour. Anyone
  can recompute it in the browser and compare digests.
- **Target form: live from the beacon.** Each simulated day's randomness comes from that hour's
  beacon round, so even the future is unknown to us, and each browser computes the current state
  itself. The design is a bet (B3), proven or dropped in session 4.
- **Why the two stores differ.** The contest compares the strong rule with SYNAPSE's governed
  composition, which uses a challenger wherever the pre-registered map trusts one. If the map
  trusts none in a regime, the stores behave the same there, and the page says so: that is the
  honest result, not a failure to show.

### 4.4 The proof (third door)

What was claimed and sealed before launch; the map of where each part helps, with intervals;
the negative results and their causes (E5 at -4.40, then -1.45 after the repair, F-13); the
limits of the world; and the instructions and code to check all of it.

### 4.5 What stays after the five days

Everything: the site is static. The contest's full record and analysis stay; Play and the proof
keep running on the free CDN (inferred from the CDN's free terms, reported).

### 4.6 What the visitor cannot do

Change the contest, or send anything anywhere, in the floor. Opt-in trace sharing (target) is the
only write path, and it comes with a privacy notice, consent and rate limits (section 11).

## 5. The science underneath

### 5.1 The decision kernel

- A small package extracted from code that exists: the twin, the tuned rule, the structure-aware
  base-stock arm, the Sentinel's newsvendor, the objective. Pure Python and NumPy. The engine
  already needs only six light packages (M-33), and the light policies drag in the heavy stack
  only through an eager package import (M-37).
- One kernel runs in the harness, the browser and the live mirror. **Parity is tested, not
  assumed:** the same seed must give byte-identical results natively and in the browser (session
  8), as it already does across two native machines (M-18).

### 5.2 The scientific choices, sealed first (session 4)

The reviewer's strongest objection was that the public verdict depends on three choices not yet
made, and that loose choices would make any "win" cheap. They are therefore fixed and sealed, with
their hashes published, before any result on the new world exists:

| Choice | Sealed as | Why |
|---|---|---|
| The incumbent | A rule tuned per item and per part of the day, on normal conditions only, as a good planner would | Today's tuned rule shares one (s, S) across all items (`uplift/tuned_static.py:1-13`); against skewed items that is a strawman |
| The economic weights | Lost-sale cost from gross margin, waste cost from unit cost, holding cost per unit-day, each from a stated, cited retail economics assumption, with a sensitivity band reported | Today's 8:1:1 is the measured agent's own default (F-14a), and once waste takes stock the weights decide the sign |
| The material margin | In cost units, tied to effects a practitioner would act on (for example one point of fill at equal waste, or a tenth less waste at equal fill) | Statistical power is not practical importance |
| The seeds | Exploratory seeds for development; confirmatory seeds sealed by hash and opened only for the final run | So nothing is tuned to the seeds it is judged on (M-24 shows how fast that happens) |
| Shocks | Onsets at random times, unannounced; challengers must detect them from what they observe | Today's shocks are constant multipliers with no onset, and a challenger that reads the declared shock is seeing the answer |
| The analysis | Paired comparisons with a block bootstrap or another method valid under autocorrelation; for the contest, a pre-specified final test, with interim numbers labelled descriptive | Daily differences in one run are not independent |

### 5.3 A truer world (narrowed)

| Change | Why | Evidence |
|---|---|---|
| Stock held in batches that age and are discarded at their modelled shelf life, first in first out | Without it over-ordering costs nothing | F-30 |
| Many items with skewed demand and an intraday profile | Equal items hide fast and slow movers and the evening peak behind the measured loss | F-13a, M-09 |
| The intraday shape and item mix fitted to FreshRetailNet-50K, with stockout-hidden demand recovered by one named method, checked by masking hours that were in stock | Real hourly sales with stock status for 863 perishable products (CC BY 4.0); it has no waste, cost or lead-time fields, so those stay modelled and declared | EX-03, LOG reported block |
| Shocks with random onsets | Where a rule tuned on normal conditions should struggle | 5.2 |

A hub of stores is moved to the dream: it is the fair test of coordination, but it is not needed
for the release's claims.

### 5.4 The agents, given jobs where they can matter

| Agent | Job in the release | Mechanism | Today |
|---|---|---|---|
| Demand Prophet | The day's demand shape per item, fitted on real data | Information | A fallback constant (F-02) |
| Inventory Sentinel | Order quantities from forecast, lead time and shelf life | Information | Binds every decision; mis-estimates the rate (F-13a) |
| Freshness Guardian | Batch ages and expected waste | Information | Refused by the harness request (F-03) |
| Supplier Trust | Lead-time distribution per supplier | Information | A configured prior (F-02) |
| Disruption Shield | Detects a shock from demand and lead-time signals, without being told | Adaptation | Given no features (F-02) |
| Orchestrator | Incumbent-first arbiter, quantity guard, record of outcomes | Governance | Argmax of self-reported confidence (F-04) |
| Pricing Oracle, Routing Navigator, Sustainability | Not used in this release's decisions: markdowns, riders and emissions are deferred or reported only | - | Shown as such |

Each part earns its place by ablation under the rule written before the run (D-5). The honest
expectation, from F-29 and the literature (EX-02): in calm conditions a strong rule leaves little
room, and the map may show none; the room, if any, is in shocks and short shelf lives.

### 5.5 Governance

- **Incumbent first.** The strong rule decides unless the map trusts a challenger for the regime
  the store is detected to be in, and a deterministic guard passes the quantity (D-2, D-4).
- **No dead ends.** Below the confidence floor the incumbent acts (fixes F-08).
- **Outcomes recorded** for every decision, hash-chained (fixes F-10; reuses ADR-033).
- **The degraded flag read**, not only stored (fixes F-02a).
- A loss is not ruled out: the map can be wrong in a regime it did not see, which is why the
  claims below state it in cost units.

### 5.6 The claims, sealed before launch

The numbers in this table are written in session 4 (section 5.2) and published with their hash.

| Claim | Cell | Stated as | False if |
|---|---|---|---|
| C1 SYNAPSE is never materially worse than the strong rule | Every cell | Upper bound of the paired cost difference below the material margin, in cost units | The bound exceeds the margin in any cell |
| C2 SYNAPSE is materially better where shocks arrive unannounced | Shock cells | Lower bound of the paired cost advantage above the margin | The lower bound at or below the margin |
| C3 SYNAPSE wastes less at equal fill where shelf lives are short | Short-shelf-life cell | Waste and fill differences with their intervals | Waste not lower, or fill lower by more than the margin |
| C4 The contest's result is reproducible by anyone | The public contest | Digests from any browser equal the published ones | Any honest recomputation differs |
| C5 The live mirror computes what the browsers compute (target) | The contest | Every decision of the mirror equals the kernel's for the same beacon rounds | Any mismatch |
| C6 Players with SYNAPSE's advice do better than players without it (exploratory, target) | Play | Difference in cost between randomly assigned groups | Reported either way, as exploratory |

A negative result is published as prominently as a positive one, as the project has done twice.

## 6. Architecture

| Layer | What | Where | Scales to | Cost |
|---|---|---|---|---|
| Site | Play, the contest, the proof | Cloudflare Pages, free plan | Any audience; static requests reportedly unlimited (snippet) | $0 |
| Engine | Pyodide and the kernel in a Web Worker | The visitor's machine | Each visitor computes for themselves | $0 |
| Randomness | drand public beacon rounds, verified in the browser (a WebAssembly verifier exists, reported) | Public relays | Built for public use (reported) | $0 |
| Live mirror (target) | The full governed system, in-process, on the same beacon rounds, publishing hourly snapshots and its hash-chained log | One small VM on the Google Cloud account whose trial ends later | One process | About $12 for six days at third-party e2-standard-2 rates (reported prices) |
| Verification | Full suites, sealed confirmatory runs, browser matrix | The laptop first; Docker sandboxes for what does not fit | 8 to 16 vCPU, 16 to 32 GB | From the Docker credits |
| Calibration fits | Demand shape and censoring on FreshRetailNet-50K | Colab or a sandbox | One-off | From the units |

**Speed (judgment from M-34 and the reported slowdown).** A simulated day takes 0.44 s natively
for ten items, an estimated 1.3 to 2.2 s in a browser, and more with more items. Session 8 sets
the item count to fit a budget of 3 s per simulated day on a mid laptop, and a phone mode with
fewer items.

**What does not ship:** Kafka, Neo4j, Redis, Feast, MLflow, Prometheus, Grafana, the Helm chart,
any language model in the decision path.

## 7. Resources, mapped

| Resource | Stated | Use | Planned spend | Caution |
|---|---|---|---|---|
| Google Cloud, two accounts | $300 trial each | Target only: the live mirror on the later-ending trial; rehearsal on the other | Under $40 in all | Trials are for customers who never had one (reported, quoted from Google's page); eight cores at a time; three months from start (EX-01). The floor needs neither account |
| Docker Sandboxes, three accounts | $250 each | Sealed confirmatory runs, browser matrix, load and parity tests | $50 to $200 | "Limit one per user and account"; claim by 2027-01-31; expires six months after claiming; a card is required (EX-06) |
| Claude Code | Max plan ($150, held); about $120 of use for the ten execution sessions | The sessions | All of it | The binding resource (section 9.2) |
| Colab | 200 units | Calibration fits | Under 50 units | Expiry not stated |
| Cloudflare | Free plan | Site and CDN | $0 | Nothing visitors poll may pass through a Worker (100,000 requests a day, reported) |

**On the terms, plainly.** If several of these accounts belong to one person, a provider may end
a trial or void a credit. The floor depends on none of them: it is a static site.

## 8. The calculated risks

| Bet | Upside | Downside | Odds (judgment) | Fallback |
|---|---|---|---|---|
| B1 The kernel runs in the browser at 3 s a simulated day | Zero marginal cost; recompute-it-yourself | Slow or heavy, worst on phones | 70% | Fewer items; a phone mode; precomputed days labelled as such |
| B2 Demand shape fitted to FreshRetailNet-50K | Real demand, honestly labelled | Chinese fresh retail is not Indian quick commerce; censoring is hard | 70% | Declare the gap; keep the declared world as a cell |
| B3 Live randomness from a public beacon, verified in the browser | A contest no one can rig or predict, checkable by anyone | Beacon availability, verification in WebAssembly, rate limits | 60% for the live form; 90% for the commit-and-reveal floor form | Commit and reveal from one launch round |
| B4 A strong incumbent leaves SYNAPSE no material win | None; it is the honest risk | The headline is "a strong rule is hard to beat" | 50% that no cell shows a material win | Published as found; the map and the verifiability are the contribution either way |
| B5 Randomised advice in Play | A fair human-with-AI comparison at a scale classrooms cannot reach | Few players or noisy data | 50% for a usable sample | Reported as exploratory |
| B6 No write path in the floor | Safety and privacy by construction | Less data | 95% | - |
| B7 The live mirror matches the browsers decision for decision | Shows the full governed system is what was tested | Floating-point or ordering differences | 60% | Report the first mismatch and its cause |

## 9. The sessions

### 9.1 The path

Session 3 and ten execution sessions, 2026-11-18 to 2027-01-19. Dates allow for 25 December and
1 January. "Verified" means on the laptop or in a Docker sandbox first.

| # | Dates | Outcome | Acceptance test | Rung |
|---|---|---|---|---|
| 3 | Nov 18 to 21 | Decide and land: D-14 to D-20; #87, #91 and #90 merged in order with your yes; #89 decided separately; the ledger worktree committed; one Docker sandbox proven as a verification box | `main` green; the decision-core suite and the twelve-replicate proof run in the sandbox, timed; whether Docker runs inside it known | 0 |
| 4 | Nov 22 to 27 | The kernel extracted with native parity; the scientific choices of 5.2 sealed with their hashes; the beacon bet tested | Byte-identical results to the harness on twelve seeds; the sealed file's hash published in the repository; a beacon round fetched and verified in a test | 0 and 1 |
| 5 | Nov 28 to Dec 4 | The narrowed truer world in the kernel: batches and shelf lives, skewed items, intraday shape fitted with the named censoring method | Spoilage rises with stock held (fails today); the masking check of the censoring method reported; the strong incumbent tuned | 1 |
| 6 | Dec 5 to 10 | Challengers and governance in the kernel: shape-aware, shelf-life-aware, shock-detecting; incumbent-first arbiter and guard | Each change preceded by a test that fails; ablation arms run on exploratory seeds | 1 |
| 7 | Dec 11 to 16 | The confirmatory run on the sealed seeds; the map; the proof page's content | Controls pass; one command reproduces the map | 1 |
| 8 | Dec 17 to 22 | The browser: kernel in Pyodide, browser-native parity, Play with randomised advice, the contest's commit-and-reveal | Byte-identical digests in browser and native; a simulated day under 3 s on a mid laptop; no network request in Play | 0 and 1 |
| 9 | Dec 23 to 30 | The public site, Play first, from the design system; the phone mode | Works offline after first load; three cold readers say what happened and how to check it within one minute | 0 and 1 |
| 10 | Dec 31 to Jan 6 | Distribution and duties: a short write-up, a two-minute video, the launch text; accessibility of Play; privacy notice; licence attribution | WCAG AA checks pass; the write-up read cold by two people | 0 and 1 |
| 11 | Jan 7 to 11 | Target: the live mirror on Google Cloud and the live-beacon form; or a buffer | 24 hours of the mirror matching the browsers; else the session goes to whatever slipped | 2 |
| 12 | Jan 12 to 15 | Dress rehearsal on the production site; claims, code and analysis frozen with their hashes | The release bar of section 12 met | 0 to 2 |
| 13 | Jan 16 to 19 | Launch on Tuesday 2027-01-19; the five days; the final analysis | Published within 24 hours of the end | 0 to 2 |

### 9.2 Making ten sessions fit the Claude budget

- One outcome a session, its acceptance test written first.
- A small reading set: this plan's row, the log's "How to resume", and the files the outcome
  touches.
- Verification where it is cheap: the laptop or a sandbox, not a wait on a labelled CI run.
- At most two subagents at a time, three only when a session's outcome needs it (LOG D-03), each
  with a cap on calls.
- Commit at each verified step.
- **Measure the cost.** Session 3 records its own usage, so the budget of the rest is set from a
  number and not a guess; no session has been measured yet.

### 9.3 Tripwires, in order

| When | Check | If it fails |
|---|---|---|
| End of session 5 | Sessions 3 to 5 done by 2026-12-06 | Drop the target rung; session 11 becomes a buffer |
| End of session 7 | The confirmatory map exists | Release rung 0 with the narrowed world as it stands, labelled |
| End of session 8 | B1's budget and parity met | Phone mode and precomputed days; parity mismatches published |
| Session 12 | The release bar met | Release rung 0, labelled; the rest follows after the five days |

## 10. The launch week

- **Before launch (Jan 16 to 18).** Code, claims and analysis frozen and their hashes published;
  the launch beacon round announced in advance.
- **Days 1 to 5 (Jan 19 to 23).** The contest reveals; a short note each day labels interim
  numbers as descriptive; nothing in the contest changes, by pre-registration. With no server in
  the floor there is nothing to restore at night.
- **After (Jan 24).** The final, pre-specified analysis published; the site stays up. Any cloud
  machine from the target tier stopped before its trial ends.

## 11. Pre-mortem: it is 2027-01-26 and the release failed

| Cause, most likely first | How the plan answers it |
|---|---|
| Nobody came | Session 10 is given to distribution; the site keeps working after the five days |
| The sessions ran slow | Rung 0 is reachable from sessions 3, 4, 8 and 9 alone; the tripwires cut in a fixed order |
| An operations researcher dismissed the comparison | A strong incumbent, sealed weights, margins in cost units and random shock onsets, all published before launch |
| SYNAPSE showed no material win | Bet B4: published as found; the contribution is the honest map and a contest anyone can verify |
| The browser lab was too slow on phones | Fewer items, a phone mode, precomputed days labelled as such |
| A trace or a file leaked | No write path in the floor; traces only with opt-in, consent and a notice, as India's DPDP Act and the GDPR would expect |
| A provider ended an account | The floor uses none |
| The launch day fell on a holiday | Tuesday 2027-01-19, after the US holiday on Monday 18 January |

## 12. The release bar and the scorecard targets

| Frontier row | Today | At release (floor unless marked) | Measured by |
|---|---|---|---|
| 1 Cost against a tuned rule | 56% worse (M-23) | Against a strong rule: C1 holds in every cell | The sealed confirmatory run |
| 2 Where the rule loses | One cell, untuned bound | A map over every cell, with intervals | Session 7 |
| 3 Internal validity | Level in design | Sealed choices and seeds, published before launch | The hashes |
| 4 External validity | Declared world | Demand shape fitted to real data; trace-driven runs (target) | The calibration report |
| 5 Reproduction by a stranger | Minutes, from an export | Anyone, in a browser, byte for byte | C4 |
| 6 Assortment and demand | Ten equal items | Skewed items with an intraday shape from data | Session 5 |
| 7 Operational structure | Waste a clock | Batches with shelf lives; shocks with random onsets | Tests that fail today |
| 8 A user | None | Anyone who plays; students; researchers | Visits, plays, recomputations |
| 9 Architecture earns its complexity | One heuristic | Each part's contribution by ablation | The map |
| 10 Agents that act | Category errors | Actions appropriate and recorded with outcomes | Session 6 |
| 11 Path to production | None since June | Static release; the live mirror rehearsed (target) | Sessions 11 and 12 |
| 12 Reliability | Nothing | The site up 99.9% over the five days | An uptime check |
| 13 Cost | About $70 estimated before | $0 for the floor; under $60 of credit for the target | Billing pages |
| 14 First minute | Not seen with data | A cold reader can say what happened and how to check it | Sessions 9 and 12 |
| 15 Checks able to fail | Safety yes, quality no | A thirty-second quality check on every change | Session 4 |
| 16 No exposure | Defaults published | No secret in the client; no write path in the floor | Session 12 |
| Public verifiability (new) | Audit chain unused publicly | Every contest step recomputable; the beacon verified | C4, C5 |

## 13. Frozen, cut or deferred

- **Frozen, documented as the production topology:** Kafka, Neo4j, Redis, Feast, MLflow,
  Prometheus, Grafana, Helm, Linkerd, KEDA, Flagger, k3s, the Oracle path, the Mumbai overlay, the
  console's operator surfaces.
- **Moved to the dream:** the open benchmark with submissions; the backtest on a visitor's own
  file (sales exports rarely carry stock status, records are often wrong, and costs and shelf
  lives are unknown, so its advice would be unvalidated); the hub; language-model entrants.
- **Deferred:** routing and riders; multi-city; the deep models (none trained, M-35).

## 14. Decisions owed now

| # | Decision | Default assumed |
|---|---|---|
| D-14 | The contest's clock and form | One simulated day per real hour; commit-and-reveal from one beacon round in the floor, live beacon rounds in the target |
| D-15 | Play traces | None in the floor; opt-in, anonymous, with consent and a notice in the target |
| D-16 | Account eligibility, and each trial's start date | You confirm; nothing in the floor depends on it |
| D-17 | A domain | Not needed; the free `pages.dev` address serves the floor |
| D-18 | Launch timing and channels | Tuesday 2027-01-19; the write-up and video of session 10 |
| D-19 | Licences | Code Apache-2.0 as now; derived data CC BY 4.0 with FreshRetailNet-50K attributed |
| D-20 | Language models | None in the decisions; explanations generated from the computed numbers |

## 15. The odds, their basis, and what will move them

| Rung | Odds (judgment) | Basis |
|---|---|---|
| 0 | About 90% | Needs sessions 3, 4, 8 and 9 only, on code whose behaviour is measured (M-18, M-23, M-33, M-34); no server |
| 1 Floor | About 55% | Adds sessions 5 to 7, each with real technical risk (a new data model, a fitted demand shape, a sealed run), and B1 at 70%; the fresh reviewer put the earlier, larger floor at 25% to 35% |
| 2 Target | About 30% | Adds the live mirror, B3's live form and B7, on a calendar with no slack after the tripwire at session 5 |
| 3 Dream | About 10% | Depends on an audience and on people outside the project |

**Up:** session 3 recording a cost per session that fits the budget; session 4 finishing inside
five days; parity in the browser on the first attempt. **Down:** any session over ten days; the
beacon unusable from a browser; the censoring method failing its masking check.

**The single sentence the release should earn.** "SYNAPSE ran two simulated dark stores in public
for five days, a strong rule against its own system, on randomness nobody controlled, said in
advance what it would prove, and let anyone recompute every step and play the store themselves."

## 16. What the fresh review of version 1 changed

| Criticism | Disposition |
|---|---|
| The floor's odds of 80% were not credible: ten of eleven sessions and two bets in series | Accepted; restated as a ladder with rung 0 at about 90% and the floor at about 55% |
| The incumbent was a strawman: one (s, S) for all items | Verified (`uplift/tuned_static.py:1-13`); the incumbent is now tuned per item and part of the day |
| The weights, the margin and the seeds were open, so any win could be cheap | Accepted; sealed in session 4 before the world changes (5.2) |
| Shocks had no onset; a challenger reading the declared shock sees the answer | Accepted; random onsets, detection from observations |
| A live server, a standby, a domain and failover served a simulation the harness computes in a minute | Accepted; replaced by commit-and-reveal from a public beacon, the live server kept only as a target-tier mirror |
| Under incumbent-first, the two live stores may be identical | Accepted and stated on the page as an honest outcome (4.3) |
| "Prove" on a visitor's file gives unvalidated advice | Accepted; moved to the dream |
| Five offerings in five days were too many; lead with Play | Accepted |
| C1 compared a cost with a quantity; C5 checked the simulator against itself; C6 was confounded | Accepted; claims rewritten (5.6), advice randomised |
| The twin's data model change would break about 110 legacy references | Verified by `git grep`; the new world lives in its own package and the legacy stays green |
| "Running right now", "real perishability", "bounds any loss" | Corrected to "simulated", "modelled shelf lives", and "a loss is not ruled out" |
| Holidays, distribution, privacy, accessibility and the operator's sleep were missing | Added: dates allow for 25 December and 1 January; session 10; the notice and consent; WCAG; no night restore needed |
| 2027-01-18 is a US holiday | Launch moved to Tuesday 2027-01-19 |
| Docker's sandboxes were untested as a verification box | Session 3's acceptance test |
