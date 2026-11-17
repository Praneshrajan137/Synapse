# FRONTIER - the standard SYNAPSE is judged against, and where it stands

**Status: 2026-11-17.** The calibration from `OPENING.md`, section 2, carried through with what
session 2 checked, corrected where it was wrong, and closed with the scorecard.

How each source was obtained, as the prompt requires:

| Mark | Meaning |
|---|---|
| **checked** | The main session opened the page and read the figure on 2026-11-16 or 17 (LOG EX-nn) |
| **fetched** | A research subagent reports opening the page and seeing the figure; not re-read by the main session |
| **snippet** | Seen only in search-result text |
| **recalled** | From model memory; not confirmed |

A verdict in the scorecard rests on a checked figure, on a measurement of SYNAPSE, or says that
it does not.

## 1. The six bodies of practice

### 1.1 Inventory-control theory and its learned successors

- **What it is.** Base-stock and (s, S) policies, with decades of results on when they are
  optimal, and the learned policies large retailers have published since 2022.
- **Where it leads, in numbers.** In 100,000 simulated lost-sales products, a learned policy
  beats base stock by 0.79% at lead time 2, rising to 5.68% at lead time 7, and beats vector
  base stock by 0.29% to 3.79%; the benchmarks were given the demand distribution
  (arXiv 2507.22040, Table 4, 2025; **checked**, EX-02). The best-known comparison of deep
  reinforcement learning with classical policies found it did not beat capped base stock in
  every lost-sales case (Gijsbrechts, Boute, Van Mieghem, Zhang, M&SOM 2022; **snippet**). An
  online retailer and a Chinese e-commerce company report learned replenishment beating their
  existing processes in the field, without percentages in the abstracts (Madeka et al. 2022,
  **fetched**; Qi et al., Management Science 2023, **snippet**).
- **What it gave up.** Generality: each result holds for the demand and lead-time process
  assumed. Learned policies cost heavy tuning and many failed runs (**snippet**).
- **Where it falls short.** Above a well-tuned rule the measured gains are single-digit percent
  in simulation, and field gains are reported against an incumbent process rather than a tuned
  rule.
- **Humans and the algorithm.** A randomised field experiment found that letting merchants
  override a data-driven tool cut profit by 5.77% on average (Kesavan and Kushwaha, Management
  Science 2020; **snippet**). Store managers shift orders to balance their own workload (van
  Donselaar et al., Management Science 2010; **snippet**).

### 1.2 Experimentation and simulator validation

- **What it is.** Switchback and field experiments for decisions that share stock or riders;
  validation of a simulator against history before trusting a comparison made in it.
- **Where it leads.** Switchback designs give exact randomisation tests where units interfere
  (Bojinov, Simchi-Levi, Zhao, Management Science 2023; **snippet**). Off-policy estimates
  degrade quickly with horizon and with distance from the logged policy (Voloshin et al. 2019;
  **snippet**).
- **What it gave up.** Speed and cost: a live system or real history is required.
- **Where it falls short.** Nothing in this body makes a comparison in an uncalibrated simulator
  transfer to a store. What such a comparison can support is a relative claim under stated
  assumptions, made stronger by sweeps over the assumptions and by stress cases (**recalled**).
- **Data.** FreshRetailNet-50K: hourly sales with hourly stock status for fresh products,
  licence tag CC BY 4.0, about 4.85 million rows, from a Chinese online grocer (**checked**,
  EX-03). Instacart's 2017 terms allow non-commercial use only and forbid redistribution
  (**fetched**, from a copy of the terms). The M5 and Favorita terms were not confirmed.

### 1.3 Indian quick-commerce operators

- **What it is.** The incumbent any product in this domain serves or must beat.
- **Where it leads (all secondary sources quoting filings; none read in a filing).** About
  2,751, 1,240 and 1,139 dark stores at the three largest operators in 2026; 1,192 to 2,140
  orders a store a day; items per store reported anywhere from 2,000 to over 40,000 depending
  on the source and definition (**fetched** from aggregators and press). The largest operator
  dropped its ten-minute branding in January 2026 after a meeting with the labour ministry
  (**snippet**, two press sources). Customers' one quantified complaint found is expiry dates
  they cannot see (**snippet**).
- **What it gave up.** Little is published on method: replenishment cadence, lead times,
  wastage and demand concentration were not found.
- **Record accuracy, the general retail standard.** Of nearly 370,000 records in 37 stores of
  one retailer, 65% did not match the shelf (DeHoratius and Raman, Management Science 2008;
  **checked**, EX-04).

### 1.4 The measured science of agent systems

- **What it is.** Controlled comparisons of several agents with one, and long-running agents
  operating a small business.
- **Where it leads.** Across 260 configurations, the change from one agent to several ranges
  from +80.8% on decomposable financial reasoning to -70.0% on sequential planning, and returns
  diminish once a single agent is strong (arXiv 2512.08296, abstract **checked**, EX-05).
  Token overheads of 285% to 515% for coordinated designs (same paper, **fetched**). A
  vendor's multi-agent research system gained 90.2% on its own evaluation at about fifteen
  times the tokens of a chat (**fetched**). A shop run by one model did not make money in its
  first phase; its second phase cut losses with better tools and process (**fetched**).
- **What it gave up.** Cost and predictability.
- **Where it falls short.** Business-agent benchmarks report no rule baseline (**fetched**).
- **Correction to the opening.** These studies concern language-model agents. SYNAPSE's eight
  are numeric components, and its only language-model call sits in the debate stage, which the
  measured path never reaches (MAP F-05, F-24). The evidence bears on that stage, and on the
  design question of when to split a decision among components; it says nothing direct about
  forecasters and heuristics under an arbiter. Row 9 below is judged by SYNAPSE's own ablation
  evidence, not by analogy.

### 1.5 Reliability for small deployments, and reviewable artifacts

- **What it is.** The practice of keeping one machine up and observable for a short event, and
  the standards a stranger applies to a computational claim.
- **Where it leads.** The free trial gives $300 for three months, ending at the earliest of the
  credit spent, three months, or an upgrade; Compute Engine is limited to "eight cores of
  concurrent usage"; there is no SLA; Google may end or change the trial at any time; after an
  upgrade the credit stays until the same date and the trial's terms stop applying (terms last
  modified 2026-02-12; **checked**, EX-01). At the end of a trial, resources stop and Compute
  Engine data is marked for deletion after 30 days (**fetched**). An e2-standard-8 in Mumbai is
  about $0.32 an hour (third-party table, **fetched**; the official page could not be read by
  fetch). Artifact badges distinguish available, functional, reusable, and results replicated
  or reproduced by another team (ACM; **snippet**).
- **Where it falls short.** Nothing standard covers a five-day showcase; the bar in row 12 is
  proposed, not cited.

### 1.6 The reviewer's first five minutes

Defined here, because no standard exists: within five minutes a reviewer can say what the
system did, how they know, and why it matters, each claim one step from its evidence.

## 2. Where the calibration was wrong, said openly

- **Row 9** compared SYNAPSE with language-model multi-agent studies; the comparison is weaker
  than the opening implied (section 1.4). The row is now judged by SYNAPSE's own evidence.
- **Row 13** treated cost as level. It is, but the opening understated the binding limits: one
  eight-core machine at a time, a trial that can be ended without notice, and a credit that
  lapses three months from the account's start, near the release's last day.
- **Row 2** had no numbers at the gate. It has them now, from the committed record (LOG M-25),
  and they change the reading of row 1: on the cell measured, even a perfect version of the
  current design would probably not clear the margin.
- Nothing was dropped or merged. Three rows are added at the end, as the prompt requires.

## 3. The scorecard

"Sessions to close" counts implementation sessions in the path proposed in `DIRECTION.md`, and
says what closing the row unlocks. "Beyond" is used nowhere: no SYNAPSE value was measured the
same way as an outside reference.

| # | Frontier property | Frontier reference and its value | SYNAPSE now | Evidence and how to reproduce it | Status | Verdict | Sessions to close, and what it unlocks |
|---|---|---|---|---|---|---|---|
| 1 | Cost against a tuned classical rule | Learned policies 0.79% to 5.68% better than base stock in simulated lost sales (EX-02, checked) | Repaired consensus 3.927 against the tuned rule's 2.480 in E5; 3.907 against 2.512 in a local miniature, worse in 12 of 12 | LOG M-23: `mini_e5.py 12` on an export of `1c484fb`; RD-01 | Verified (miniature measured; E5 read) | Behind | 1 (fit the Sentinel's levels on held-out seeds; M-24 suggests near-parity). Unlocks the claim "matches the incumbent" |
| 2 | Knowing where the tuned rule loses | Long lead times, shifting or censored demand, perishability, shared limits, substitution, transfers (fetched and snippet) | Primary cell: tuned rule 0.630 above hindsight (0.390 stock held, 0.240 unfilled); a better-informed rule gains 0.246 against a 0.4 margin; no item or store slice exists | LOG M-25: the committed record `docs/state/bprime/twin-regret-primary.json` | Verified from the record | Behind | 2 (a truer twin; pre-registration by cell). Unlocks a claim that can be true |
| 3 | Internal validity of the comparison | Pre-registration, paired seeds, interval, power, controls, negatives published | All present; 24 of 24 repeats identical; trace identical across machines. Open: `harness_mis_measuring` (finding 117), and `room_to_win` tested against a clairvoyant ceiling | LOG M-18, M-23, M-25, RD-06 | Verified in part | Level, estimated | 1 (settle finding 117; restate room to win against an attainable arm). Unlocks a proof a stranger can cite |
| 4 | External validity | A field or switchback test, or a simulator validated on history | Declared twin, fidelity unknown; waste is a clock; a CC BY 4.0 dataset with hourly stock status is unused | MAP F-30; LOG EX-03 | Verified | Behind | 1 for calibrating demand shape; full validation needs real store data, after the release. Unlocks answering "is the world real?" in part |
| 5 | Reproduction by a stranger | Results reproduced by another team (snippet) | The proof reproduces locally in minutes from an exported tree; no command starts a system that decides | LOG M-18, M-23, V-07 | Verified | Behind | 1 (one command, timed). Unlocks reviewers re-running the proof |
| 6 | Assortment and demand realism | 2,000 to 40,000+ items a store (fetched, conflicting) | 10 items, uniform | LOG M-09, M-16 | Verified here; estimated outside | Behind | Part of row 2's work. Unlocks fast and slow movers |
| 7 | Operational structure | Hub and spoke; 65% of records wrong in the standard study (EX-04, checked) | One store; record equals shelf; lost sales; no transfer or substitution; waste takes no stock | MAP F-30; LOG M-25 | Verified | Behind | 1 for waste that takes stock; record error as a stress cell. Transfers after the release |
| 8 | A named user and workflow | Products of this kind are built with a named practitioner | None named; the reviewers judge the work as a whole | LOG OA-4 | Verified | Behind | 0 build sessions; a decision in session 3. Unlocks the console's first five minutes |
| 9 | The architecture earns its complexity | Several agents help on separable work and hurt on sequential work (EX-05, checked); SYNAPSE's own ablations are the real test | One agent bound 372 of 372; five proposers constant; the full path changed no order at about a hundred times the cost; no ablation arm exists | LOG M-19, M-20, M-21: `scan_binding.py`, `scan_paired.py` | Verified | Behind | 1 (ablation arms in the harness). Unlocks a per-agent contribution table |
| 10 | Agents that act | Each acting part has an observed, appropriate effect (defined here) | Eight of eight reach an actuator by static audit; the forecaster acts by scaling demand; the live path enacts every proposer's own proposal | LOG M-11, V-03, V-06 | Verified | Behind | 1. Unlocks "what ran is what is shown" |
| 11 | A working path to production | Merge to a verified live system in minutes; withdrawal exercised | Last deploy 2026-06-14; 22 of 22 scheduled runs failed; the account is gone | LOG M-08, OA-1 | Verified | Behind | 2 (thin slice; first cloud rehearsal). Unlocks the release |
| 12 | Showcase reliability | Proposed: 99.5% over 120 hours (36 minutes down); outage known in 2 minutes; restore rehearsed under 30 minutes; fresh machine to working system under 45 minutes | Nothing measured; no environment | - | Unverified | Behind | 3 (rehearsal, hardening, dress rehearsal). Unlocks five days without embarrassment |
| 13 | Cost inside the credit | Under $300, inside the expiry, inside eight cores | About $70 for eight machine-days, from a third-party price | LOG EX-01 | Estimated | Level, estimated | 0; a decision on upgrading the account. Unlocks a release that outlives the trial's last day |
| 14 | A cold reviewer's first five minutes | Defined in 1.6 | First screen leads with the system's own state; honest degradation labels; fourteen routes; never seen with data | LOG M-28, M-13 | Verified (no-backend view only) | Behind, estimated | 1, then a cold-reader test in the dress rehearsal. Unlocks the reviewers' "why should I care" |
| 15 | Checks shown able to fail | Every load-bearing check has a demonstrated failing case (defined here) | Five of five faults in the decision core caught; two only by tests that pin the design; no check below E5 judges decision quality; the 68-check sweep not read | LOG M-26: `fault_injection.sh` | Verified (sample) | Level on safety; behind on quality | 1 (a miniature E5 as a fast check). Unlocks catching the next loss in minutes, not by label |
| 16 | No exposure in a public repository | No published default credential; no open control | Defaults in compose files (reported); the open-admin defect fixed on `main` and never deployed | reported; LOG RD-05 | Reported | Behind | 1. Unlocks a public link |
| KB | Readings of SYNAPSE in `docs/knowledge/` | Each confirmed, corrected or refuted with evidence | Of 60 ledger entries: 16 confirmed, 16 corrected, 10 answered, 2 strengthened, 8 open, 8 make no reading; none refuted outright. Of the ten in the synthesis: 5 confirmed, 4 corrected, 1 open. Of 61 research items: 47 answered or confirmed, 14 open with owners | `docs/knowledge/VERDICTS.md` | Verified | - | - |
| U | What was to stay unchanged | Section 7 of the opening | Ref digest unchanged apart from this session's branch; remote unchanged; no file changed outside `docs/truth/` and `docs/knowledge/`; worktrees, stash and `.kiro/settings/` as found | LOG M-14 against M-29 | Verified | - | - |
| W | What this session made worse or less certain | - | One figure this session published was wrong and was retracted within the hour (LOG M-20). Running the console created no file. The log has grown long | LOG M-20 | Verified | - | - |

## 4. Sources

| # | Source | Date | How obtained |
|---|---|---|---|
| EX-01 | Google Cloud, Supplemental Terms for the Free Trial | modified 2026-02-12 | checked |
| EX-02 | Maggiar et al., "Structure-Informed Deep Reinforcement Learning for Inventory Management", arXiv 2507.22040 | 2025-07-29 | checked (Table 4) |
| EX-03 | FreshRetailNet-50K dataset page, Hugging Face | read 2026-11-16 | checked |
| EX-04 | DeHoratius and Raman, "Inventory Record Inaccuracy: An Empirical Analysis", Management Science 54(4) | 2008 | checked (abstract) |
| EX-05 | Kim, Gu, Park et al., "Towards a Science of Scaling Agent Systems", arXiv 2512.08296 | 2025-12-09, v3 2026-04-08 | checked (abstract) |
| - | Gijsbrechts et al., M&SOM | 2022 | snippet |
| - | Madeka et al., "Deep Inventory Management", arXiv 2210.03137 | 2022 | fetched (abstract) |
| - | Qi et al., Management Science | 2023 | snippet |
| - | Kesavan and Kushwaha, Management Science | 2020 | snippet |
| - | van Donselaar et al., Management Science | 2010 | snippet |
| - | Bojinov, Simchi-Levi, Zhao, Management Science | 2023 | snippet |
| - | Voloshin et al., arXiv 1911.06854 | 2019 | snippet |
| - | Anthropic, multi-agent research system; Project Vend phases 1 and 2 | 2025 | fetched |
| - | Andon Labs, Vending-Bench and Vending-Bench 2 | 2025-2026 | fetched |
| - | Quick-commerce figures: aggregators and press quoting company filings | 2025-2026 | fetched or snippet, as each states |
| - | Google Cloud, free-trial features page; a third-party Compute Engine price table | read 2026-11-16 | fetched |
