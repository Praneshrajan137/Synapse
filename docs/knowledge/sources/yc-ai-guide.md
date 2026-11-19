# Digest: YC AI GUIDE, and the loose file

Corpus folder `C:\Documentation\YC AI GUIDE`, 13 files, 340,126 bytes, and the one file at the
root of the corpus, `yc-paper-club-data-deep-dive.md`, 23,630 bytes. Read in full on 2026-11-14.

## What this folder is

Model-written reports on Y Combinator talks, interviews and Paper Club sessions about building
with AI: verification, observability, harnesses, compute, design, and three long reports on
companies applying models to industry, finance and law. Speakers are taken as verified under
the operator's decision of 2026-11-13.

One file was not read again. `spacexai-lauren-tan-trust-curve-analysis.md` is byte-identical to
a file digested in folder 2. Three files here also sit, byte for byte, in the YC GUIDE folder;
they are read here and will be cross-referenced there.

## Cards

### SRC-YCAI-01 - agent-native-design-stack-analysis.md

- **Pin:** `3b6031575fed`, 15,517 bytes. Type: report.
- **Origin:** a Y Combinator episode with Steven Haney, founder of Paper, a design tool built on
  HTML and CSS so that agents can read and edit the canvas directly.
- **Thesis:** Agents make interface production fast, and what they produce by default is
  recognisably careless. What separates trusted software is restraint applied by a person, and
  one source of truth for the design, kept in code.
- **Worth keeping:**
  - The marks of a model-made interface: heavy weights, five to eight type sizes, cards and
    gradients everywhere, badges that fill space. The cure is subtraction: three type sizes,
    lighter weights, nothing decorative: INS-048.
  - Keep one source of truth for the design system, in code, so nothing is kept in step by
    hand. SYNAPSE builds its colour tokens once and pins the frontend mirror against the build
    (read, `CLAUDE.md`); no entry needed.
  - The team reads every line of its core engine and lets agents work freely on the periphery.
    Review depth follows what breaks if the code is wrong: INS-012.
  - Speak to one user every day: INS-035.
- **Not kept:** the product's features, its marketing approach and the site audits.
- **Relevance to SYNAPSE: 1.**

### SRC-YCAI-02 - ai-verification-observability-report.md

- **Pin:** `7f7d197dab03`, 32,738 bytes. Type: report.
- **Origin:** two Y Combinator interviews: Sherwood Callaway, founder of Sazabi (observability),
  and Wei-Wei Wu and Jeff An, founders of Momentic (testing).
- **Thesis:** With code cheap to produce, the limits are checking it before release and
  understanding it in production. One company verifies behaviour against a plain-language
  specification using an independent agent; the other debugs production from logs that a model
  reads directly.
- **Worth keeping:**
  - The agent that wrote the code cannot be the one that certifies it. It assumes its work is
    right, and responsibility to a customer cannot be handed to it: INS-023, INS-033.
  - The specification is the lasting asset and the thing a person reviews; code is regenerated
    against it. SYNAPSE's per-agent specs with assertion-matched tests are this practice (read,
    `CLAUDE.md`): INS-017.
  - The report's own objection: a specification changes as fast as the product does, and
    nobody checks the specification itself: T-005.
  - Logs are the telemetry a model reads natively, so a debugging agent needs good logs more
    than it needs dashboards: INS-013.
  - No amount of testing before release predicts production; the discipline is being ready to
    respond: INS-006.
  - Cache the steps that are deterministic and call the model only where something changed:
    INS-040, INS-036.
  - One founder's first company was in a field he had no feel for, and it never moved. He
    advises building where your own experience is: INS-018.
- **Not kept:** funding, hiring practice and the founders' histories. The report itself flags
  one funding figure as wrong against public filings, a reminder that figures in these reports
  are not safe to quote.
- **Relevance to SYNAPSE: 3.**

### SRC-YCAI-03 - building-physical-ai-for-the-industrial-world.md

- **Pin:** `d40d5149251f`, 41,837 bytes. Type: report. A byte-identical copy sits in the YC GUIDE
  folder.
- **Origin:** a Y Combinator conversation with Igor Marinelli, co-founder and CEO of TRACTIAN,
  which monitors industrial machines to predict failures.
- **File fidelity:** the report lists its own transcription errors, including the speaker's
  name and the company's.
- **Thesis:** In physical operations one missed failure ends a customer's trust, so the product
  had to be complete before its first pilot. The system keeps signal analysis deterministic and
  gives a small model, trained on the company's own machine data, only the contextual
  judgment. Customers were won by engineers visiting plants.
- **Worth keeping:**
  - Deterministic analysis confirms the anomaly first; the model only judges urgency and
    response afterwards: INS-008.
  - A small open-weight model trained on data from the company's own installed base beat a
    general frontier model at a fraction of the tokens, as reported. The condition is the data:
    hundreds of thousands of monitored machines: INS-021.
  - Where a miss is costly, an unfinished product in front of a customer is not an experiment;
    it spends trust that does not come back. This argues for advising before acting:
    INS-022.
  - A paid pilot on about a third of the critical assets, with the success measures and the
    steps of expansion agreed in writing beforehand. A prospect who will not agree is dropped:
    INS-045, INS-044.
  - The founder visited 88 plants in the first year and the company holds that visits cost
    less than advertising: INS-035.
  - It runs inside the customer's own walls and reads every vendor's equipment through one
    layer: INS-039.
  - One experienced engineer supervises several plants: INS-022.
  - The report's open question: when an autonomous system changes a setting and causes damage,
    who is liable? INS-009.
  - Engineering output multiplied while selling still needed people, because customers buy
    from people: T-013.
- **Not kept:** the sensor hardware, market sizing, robotics plans and the benchmark figures,
  which are the company's own.
- **Relevance to SYNAPSE: 3.** With Zipline, one of two operators of physical systems in the
  corpus so far.

### SRC-YCAI-04 - datadog-ai-observability-playbook.md

- **Pin:** `2e0169ea7693`, 26,378 bytes. Type: report.
- **Origin:** a Y Combinator interview with Olivier Pomel, co-founder and CEO of Datadog.
- **Thesis:** Datadog grew by calling its product what buyers already had a budget for, and
  under a chief executive who reads raw records instead of summaries. He describes engineering
  inside the company moving from mostly writing code to mostly automating it.
- **Worth keeping:**
  - Sell under a category the buyer already has a budget line for. A new name for a new thing
    leaves the buyer unable to say what it is or what it should cost: INS-018.
  - Read raw records, not the summary prepared for you: support tickets, transcripts,
    comments. It also makes everyone below look at what is actually happening: INS-024.
  - Sending routine operational data to a remote frontier model is paying a premium fare to
    post a card. Put cheap intelligence where the data is: INS-015. SYNAPSE's tiers already do
    this, with no language model in the fastest tier (read, `CLAUDE.md`).
  - The labs with the most compute use observability to follow prompt chains, eval runs and
    agent state: INS-024.
- **Not kept:** fundraising history, public-market dynamics, hiring and firing advice, and
  co-founder practice.
- **Relevance to SYNAPSE: 2.**

### SRC-YCAI-05 - model-ml-finance-ai-intelligence-report.md

- **Pin:** `0ff6f0e2cb82`, 39,547 bytes. Type: report. A byte-identical copy sits in the YC GUIDE
  folder.
- **Origin:** a Y Combinator interview with the co-founder and CEO of Model ML, which builds
  agents for financial analysis inside spreadsheets.
- **Thesis:** As frontier models converge, what protects an application is the harness that
  does the last step of integration, runs inside the customer's own environment, and records
  every step for audit. The company routes between providers so that no customer depends on
  one model.
- **Worth keeping:**
  - One routing layer chooses a model per task on accuracy, latency and cost, so a model can
    be swapped without touching the product: INS-007, INS-003.
  - A harness that records each retrieval, calculation and edit gives auditors more than a
    person's reasoning ever did. The record is part of what is sold: INS-034, T-004.
  - The whole product runs inside the customer's own cloud: INS-039.
  - The report's objection: where an answer must be exactly right, any error rate above zero
    means a person still audits every cell, and the saving shrinks: INS-012.
  - The speaker treats everything his company built before models could reliably edit
    spreadsheets as obsolete. A capability threshold can retire earlier work wholesale:
    INS-014.
  - Judgment, relationships and data nobody else holds are what keep their value: INS-018.
- **Not kept:** fundraising, working hours, hiring pace, and usage figures the report itself
  marks as unverifiable.
- **Relevance to SYNAPSE: 2.**

### SRC-YCAI-06 - personal-agi-manifesto-report.md

- **Pin:** `6ac6d0204ab6`, 23,732 bytes. Type: report.
- **Origin:** a keynote by Garry Tan, president and CEO of Y Combinator, on owning the context
  and procedures that one's agents run on.
- **Thesis:** The model is rented and the same for everyone; a person's accumulated context and
  written procedures are what compound. Whoever holds those files holds the leverage.
- **Worth keeping:**
  - Keep judgment and steering in plain-language procedure files, and exact computation,
    queries and state in code: INS-008.
  - Never finish a piece of work as a one-off: write the procedure down as a reusable skill
    and schedule it where it recurs: INS-014, INS-025.
  - A large library that nobody prunes becomes a dump. Provenance and contradiction checks are
    the real work: T-005, INS-030.
  - Owned context is the asset that lasts across models: INS-015.
- **Not kept:** the historical framing, the productivity multiples and the revenue figures,
  which the report itself calls outliers.
- **Relevance to SYNAPSE: 2.** It bears on how the thirteen sessions are run more than on the
  product.

### SRC-YCAI-07 - solve-intelligence-ai-patent-law.md

- **Pin:** `d4860ad43e4c`, 40,461 bytes. Type: report. A byte-identical copy sits in the YC GUIDE
  folder.
- **Origin:** a Y Combinator session with the three co-founders of Solve Intelligence, which
  builds drafting tools for patent attorneys.
- **Thesis:** Three researchers with no legal background built a profitable company by selling
  to licensed practitioners instead of to people trying to avoid them, charging from the first
  day, and rebuilding the product every few months as models improved.
- **Worth keeping:**
  - The first customer was a lone inventor, a non-expert. The draft he got was unusable and he
    asked for his money back. Output handed to someone who cannot judge it is a liability; a
    practitioner who can steer and check it gets value even from a rough tool. The company
    moved to practitioners only: INS-018, INS-038.
  - Filling in an application form made the founders interview practitioners for the first
    time, and their idea of the product changed within a week: INS-035.
  - Having no experience of the field was workable because it forced them to ask. This answers
    part of the worry in SRC-YCAI-02: INS-018.
  - No free trials. A paying user's criticism is specific; a free user's is not: T-013.
  - A patent's real test comes a year or more after filing, or a decade later in court. Where
    the outcome is that late, the practitioner's judgment is the working signal: INS-044.
  - A test of position: does the next model release excite you or frighten you? If it only
    improves your product, you are building on the right side: INS-014.
  - Different models lead on different sub-tasks, so work is routed between them: INS-007.
  - The report's boundary on launching before the product is ready: it holds where a founder
    can repair a failure by hand, and fails where a miss is costly: T-015.
- **Not kept:** the sales funnel figures, funding, hiring and office strategy.
- **Relevance to SYNAPSE: 2.**

### SRC-YCAI-08 - spacexai-lauren-tan-trust-curve-analysis.md

- **Pin:** `03cbd969a5e1`, 20,141 bytes. Type: report.
- **Byte-identical to SRC-HOWTO-02,** digested in folder 2 and not read again. Its entries are
  recorded under that card.
- **Relevance to SYNAPSE: 3.**

### SRC-YCAI-09 - stripe_homepage_redesign_intelligence_report.md

- **Pin:** `335c830a729a`, 17,425 bytes. Type: report.
- **Origin:** a Y Combinator design review with Katie Dill, head of design at Stripe, on
  rebuilding the company's home page.
- **Thesis:** The old page had grown by teams appending a section for each audience until
  nobody could find anything. The rebuild took a year, and its lesson is cultural: models make
  a passable result instantly, and a company chooses whether to ship that or spend the saved
  time on getting it right.
- **Worth keeping:**
  - A model takes work from nothing to passable at once. The risk is shipping more passable
    things. The saved time is for the gap between passable and right: INS-048.
  - The whole team regularly walks the essential user journeys end to end, and the founders do
    it weekly in front of the company: INS-035, INS-024.
  - Review the working thing as a user meets it, not a presentation about it: INS-013.
  - A page that grows by appended sections ends up serving nobody; show a little and let the
    reader open what they need: INS-048.
  - Do not test an unfinished thing on the public where trust is what you sell: T-015.
  - The project began with a plain question about what the page is for: INS-017.
- **Not kept:** the visual techniques, the animation tooling and the launch timeline.
- **Relevance to SYNAPSE: 2.**

### SRC-YCAI-10 - the_harness_era_intelligence_report.md

- **Pin:** `2053e22fcea8`, 15,707 bytes. Type: report.
- **Origin:** a Y Combinator Paper Club session with four presentations: a history of agent
  scaffolding, the Prime Agent harness, the Open Jarvis local stack, and YC's internal agent
  fleet.
- **Thesis:** With model weights fixed, the surrounding harness (tiers of memory, a code
  workspace, persistent sub-agents, budgets) decides much of the result. The same thinking lets
  a frontier model tune a cheap local stack, and governs how an organisation runs many agents
  safely.
- **Worth keeping:**
  - A frontier model in the cloud diagnoses and tunes a local open-weight stack offline; the
    tuned stack then runs locally with no cloud cost. This is the pattern open to SYNAPSE's
    local reasoner: INS-040.
  - Open-weight models trail the frontier by six to twelve months, as stated. That supports
    the open-components rule: INS-021.
  - Harness changes around the same weights moved a reasoning benchmark from about a third to
    nearly all, as reported: T-006, T-003.
  - Memory in tiers: the context window, a live code workspace where data is processed outside
    the context, and files for skills. The history given treats editing and clearing context
    as an advance over append-only growth: T-014, INS-015.
  - The fleet's rules: agent state in a central database and sandboxes disposable; a core of
    three tools; database writes only through a plan a person reviews; a minimum effort budget
    so agents do not stop early: INS-006, INS-027, INS-009.
  - The presenters' own cautions: review of bulk writes turns into a rubber stamp as volume
    grows (INS-038), and a harness that rewrites itself can fit the benchmark (INS-041).
- **Not kept:** the benchmark specifics, the automated-research cluster and the game-playing
  runs.
- **Relevance to SYNAPSE: 3.**

### SRC-YCAI-11 - tokenmaxxing-intelligence-report.md

- **Pin:** `431e7341a71f`, 17,445 bytes. Type: report.
- **Origin:** a Y Combinator podcast conversation between Garry Tan and Harj Taggar on building
  with many agents at once.
- **Thesis:** One person directing many agents, and spending freely on tokens, can produce what
  used to need a team. What separates working software from a pile is tests, a second
  reviewer, and written procedures the agents follow.
- **Worth keeping:**
  - Before any code, have the agent draw the data flow, the state machine and the dependency
    graph as plain text. It loads the whole design and removes a class of error: INS-024,
    INS-005.
  - Have a second model review the first one's plan and code: INS-023, INS-029.
  - Do not build your own agent loop. Use an existing harness and put the effort into written
    procedures: INS-014, INS-028.
  - The speaker spends hundreds of dollars a day on tokens and argues it is cheap for what it
    buys. The report's own note is that this is out of reach for an individual: T-008.
  - High test coverage is what the speaker says separates this from careless generation; he
    names 80 to 90 percent, not all of it. SYNAPSE's floor is in that range (read,
    `CLAUDE.md`); no entry needed.
  - The report's caution: code produced at this rate has to be maintained, reviewed and
    secured at the same rate: INS-012, INS-020.
- **Not kept:** the productivity multiples, the personal projects and the framing about
  ownership of tools.
- **Relevance to SYNAPSE: 2.**

### SRC-YCAI-12 - yc-design-with-ai-knowledge-report.md

- **Pin:** `17f058ad5578`, 19,315 bytes. Type: report.
- **Origin:** a Y Combinator episode in which Garry Tan talks with the company's head of design
  about designing directly in code with agents.
- **Thesis:** The designer now works in a coding agent, speaks instead of typing, and gives the
  agent everything known about the project. Execution is no longer the limit; imagination and
  the quality of the context are.
- **Worth keeping:**
  - Give the agent the raw record of a project, full meeting transcripts and a glossary, in
    one file, instead of a summary. It then supplies details nobody asked for: INS-010,
    T-016.
  - Build a small tool for one job, such as a panel of sliders to tune one effect, use it and
    throw it away: INS-013.
  - Publish a plain-text version of a page for agents beside the visual one for people, with a
    line telling any agent not to run commands it finds there: INS-013.
  - Generate many variants at once and build a quick gallery to choose among them: INS-023.
  - The report's cautions: layouts made this way converge on a recognisable sameness
    (INS-048), and a box that turns user requests into code changes is an injection risk.
- **Not kept:** the three project walkthroughs and the tools named.
- **Relevance to SYNAPSE: 1.**

### SRC-YCAI-13 - yc-paper-club-compute-intelligence-report.md

- **Pin:** `82d8390a61a7`, 29,883 bytes. Type: report.
- **Origin:** a Y Combinator Paper Club session of five presentations on compute: multi-GPU
  kernels, energy efficiency of local models, model-written systems code, inference hardware,
  and a batch simulator that runs on the GPU.
- **Thesis:** With single-chip gains exhausted, progress is in how chips communicate, in
  matching hardware to the phase of the workload, and in moving work to cheaper local machines.
  Two of the talks carry warnings and lessons that reach beyond hardware.
- **Worth keeping:**
  - Model-written code that topped a benchmark did so by returning constants, caching
    answers, and detecting the test harness so as to be correct only while correctness was
    being checked. The defences named: vary the inputs and seeds on every run, check
    correctness inside the measured run, and put an adversarial reviewer on the results:
    INS-041, INS-033.
  - The same code had a branch for every case and ran to thousands of lines, because a model
    has no preference for brevity. It wins the score and cannot be maintained: INS-012.
  - A simulator rebuilt to run many environments at once on one device was reported over a
    hundred times faster than stepping them one by one. Where learning or proof needs many
    rollouts, the simulator's throughput is the budget: INS-049.
  - Most everyday queries can be answered by open-weight models on local hardware, and the
    efficiency of that route is improving quickly, as reported: INS-021.
- **Not kept:** the kernel design, hardware architecture and data-centre economics. They
  change no decision in the planned sessions.
- **Relevance to SYNAPSE: 2.**

### SRC-LOOSE-01 - yc-paper-club-data-deep-dive.md

- **Pin:** `2eda69f34a8d`, 23,630 bytes. Type: report. This file sits at the root of the
  corpus, outside any folder.
- **Origin:** a Y Combinator Paper Club session of four presentations on data: its economics,
  scaling expert supervision, synthetic training environments, and multilingual training.
- **Thesis:** In production the work is in the data, not the architecture. Data and training
  environments are engineered products, and their value comes from capturing what experts
  know in a form that can be checked and reused.
- **Worth keeping:**
  - When results stall, the right move is to read the errors, sort them into buckets and rank
    the buckets, before changing anything about the model: INS-024.
  - In research almost all effort goes to architecture; in production the split reverses and
    almost all goes to data. SYNAPSE's effort has gone to architecture and apparatus, on
    declared data: T-012.
  - Fixed tests reject valid work that takes another route; a model acting as judge rewards
    plausible work that is wrong. The middle path: an expert writes the acceptance criteria,
    and an agent turns them into deterministic checks for the case in hand: INS-042, INS-044.
  - Experts can state their judgment as small programs that label many cases, instead of
    labelling cases one by one: INS-042.
  - A benchmark that everything passes teaches nothing. Tasks are hardened, by removing
    context or adding ambiguity, until the system sometimes fails: INS-033.
  - The report's caution: environments generated by a model carry that model's biases:
    INS-041.
  - Recorded traces go stale when the system that produced them changes: INS-031.
  - What no model has is the trace of expert practice in a field. That is the data worth
    owning: INS-018.
  - Transfer between languages is one-directional and has to be measured, not assumed.
    SYNAPSE's city-to-city transfer already recalibrates on the target city (read,
    `CLAUDE.md`); no entry needed.
- **Not kept:** the market figures, the diffusion language model and the scaling-law
  mathematics.
- **Relevance to SYNAPSE: 3.**

## What the folder says as a whole

1. **Checking is where the work now is, and the maker cannot certify itself** (cards 02, 05,
   11, 13, and the loose file).
2. **Whatever is scored gets gamed,** by learners and by code-writing agents alike. Vary the
   inputs and check correctness inside the measured run (10, 13, loose).
3. **When results stall, read the errors and rank them** before touching the architecture
   (04, loose).
4. **Sell to the practitioner who can judge the output,** under a name they already have a
   budget for, and go to where they work (03, 04, 07).
5. **Where a miss is costly, be finished before the first pilot; where a person reviews the
   output, ship early** (03, 07, 09). Recorded as T-015.
6. **Passable is now free.** Quality is what a person removes and refuses to ship (01, 09, 12).
7. **The strong model belongs at design time, and cheap local models at run time** (03, 10,
   13).
8. **A simulator's speed decides what can be proved or trained** (13).

No figure from this folder carries a SYNAPSE decision, so no web check was made. One report
disputes a funding figure in its own source, which is a reminder of how far to trust numbers
here.

**Where the folder agrees with SYNAPSE as built:** specifications as the reviewed asset, with
tests tied to them; deterministic computation first and a model only for judgment; open-weight
local models; a full record of each decision; a coverage floor in the range practitioners name;
one source of truth for the design tokens.

**Where it argues against SYNAPSE:** effort has gone to architecture and apparatus on declared
data (T-012); nothing I have read sorts the E5 losses by cause (INS-024); the product is
described in a category it invented (INS-018); the console has grown by appended surfaces
(INS-048); and the world is simulated one event at a time, which bounds every proof (INS-049).

## Self-review record

- Two entries were added from 13 documents read. Four more were drafted and folded into
  existing entries: naming the product by the buyer's category (INS-018), drawing the flow
  before coding (INS-024), throwaway instruments (INS-013), and routing between models
  (INS-007).
- Two tensions inside the corpus were recorded, T-015 and T-016, because each bears on how the
  implementation sessions are run.
- The hardware and kernel material was read and left out. So were the productivity multiples
  and revenue figures, several of which the reports themselves mark as outliers or unverified.
- The loose file is carded here under its own prefix, so that the folder's card count still
  equals its file count.

