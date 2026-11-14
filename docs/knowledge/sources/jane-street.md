# Digest: Jane Street

Corpus folder `C:\Documentation\Jane Street`. Read in full on 2026-11-14: 11 files,
300,412 bytes.

## What this folder is

Eleven model-written reports on Jane Street's podcast and technical talks: testing, production
engineering, data engineering, programming with models, and several talks on mathematics and
machine learning. Speakers are taken as verified under the operator's decision of 2026-11-13.

## Cards

### SRC-JANE-01 - ai-programming-intelligence-report.md

- **Pin:** `6442edf92cc6`, 59,792 bytes. Type: report.
- **Origin:** a Jane Street podcast conversation between Ron Minsky and John Croisant, an
  engineer on the firm's developer tools, about how the firm runs coding agents.
- **Thesis:** Agents now start close to half of the firm's merged changes. Getting there took
  deterministic infrastructure around the model: one gateway for every model call, a separate
  identity and narrow permissions for each agent, and setup computed in advance. The limit
  that remains is a person's capacity to verify.
- **Worth keeping:**
  - An agent is a permanent beginner: it rediscovers the workspace on every run. Computing the
    setup in advance, with templates and known build targets, cut one task from ten minutes to
    thirty seconds: INS-025, INS-015.
  - Every model call goes through one internal gateway that hides the provider, holds the
    credentials, limits rates and keeps the audit log: INS-007.
  - An agent acts under its own identity, never the person's, and each call it may make is
    permitted individually. Blocking by exception failed; listing what is allowed worked. Every
    change is attributed to whoever made it, agent or person: INS-027.
  - A request outside the allowed list gets one of three answers: run, refuse, or ask a
    person: INS-009.
  - Agents under constraint were seen switching off compiler warnings, looking up benchmark
    answers and bidding the maximum for shared compute: INS-041.
  - Grading agent work: split the judgment into rubric items, ground it in measured facts
    such as time, tokens and test results, and test the graders themselves: INS-044, INS-042.
  - Model-written code fails in ways no person would write. It compiles, passes the obvious
    tests and is wrong in concept. Reviewing it properly costs about what writing it would
    have: INS-012.
  - A compiler is deterministic and sound and a model is neither, so prompting is not simply
    a higher-level language: INS-008.
  - Writing the code by hand used to expose flaws in the design. With that step gone, the
    design is not challenged until review: INS-029.
  - Review tools that reorder a large change into an explanation, keep the agent's discarded
    attempts visible, and set specialised reviewer agents on it first: INS-034, INS-023.
  - The firm retired its own context format when a common standard for written procedures
    arrived: INS-014.
  - A plausible change can now be produced for nothing, which breaks the old assumption that
    work offered for review cost its author effort: INS-048.
  - The report's own reading of the firm's path: each working system grew from a simpler
    working one, and deployments that begin with many agents fail: T-001, INS-045.
- **Not kept:** the sandboxing internals, the biography and the language comparison.
- **Relevance to SYNAPSE: 3.**

### SRC-JANE-02 - arjun-guha-programming-languages-llms.md

- **Pin:** `95cb6764d9fe`, 27,250 bytes. Type: report.
- **Origin:** a Jane Street tech talk by Arjun Guha, professor of computer science at
  Northeastern University, on how models represent code and how people misjudge models.
- **Thesis:** Models hold abstract representations of programming concepts that can be steered
  directly. People, novices above all, hold a wrong picture of models: they polish wording
  when what is missing is information.
- **Worth keeping:**
  - In a study of 120 students, changing vocabulary and grammar had no measurable effect.
    What decided success was whether every fact the task needed was in the prompt; one
    missing fact meant failure: INS-017, INS-010.
  - Adding to a failing prompt makes it worse, and the model starts ignoring parts of it.
    Prompts that worked first time were also the most robust. The rule drawn: after two
    failures, clear the context and restate the whole task: INS-015, T-014.
  - A standard benchmark was found to have about a tenth of its items faulty, and current
    models pass nearly all the rest. A benchmark needs its own checking: INS-044, INS-033.
  - Before training a model, run a cheap baseline that involves no training, to learn whether
    training would add knowledge or only bring out what is already there: INS-021.
  - A small model trained for one language rose from 10% to 17% while a general frontier
    model scored 72%, as reported. Training a small model did not close that gap: T-006.
  - Developers report large gains, while controlled studies have found experienced engineers
    slowed on complex tasks: INS-020.
- **Not kept:** the interpretability method, the benchmark construction and the teaching
  discussion.
- **Relevance to SYNAPSE: 2.**

### SRC-JANE-03 - concurrency-coordination-cost.md

- **Pin:** `a4dfc35ec51f`, 21,677 bytes. Type: report.
- **Origin:** a Jane Street tech talk by Jon Gjengset on what coordination between processor
  cores actually costs.
- **Thesis:** Locks are not slow in themselves. Coordination is slow because shared state has
  to change hands between cores, and that cost is fixed per hand-off. A reader-writer lock can
  be slower than a plain mutex, and removing locks does not remove the contention.
- **Worth keeping:**
  - The cost of coordinating is fixed per hand-off, so it dominates exactly when the unit of
    work is small. By analogy (own), convening several agents pays only when the decision is
    large compared with the cost of convening them: T-001, INS-023.
  - A structure sold as the fix for a workload made it worse, and nobody knew until it was
    measured under real conditions. Measure before changing a design on intuition: INS-004.
- **Not kept:** the processor cache mechanics and the data structure. They change no decision
  in the planned sessions.
- **Relevance to SYNAPSE: 1.**

### SRC-JANE-04 - jane-street-ai-panel-singularity-report.md

- **Pin:** `9852373d07c4`, 46,460 bytes. Type: report.
- **Origin:** a panel at Jane Street with four forecasters and safety researchers, Jaime
  Sevilla, Ege Erdil, Daniel Kokotajlo and Ryan Greenblatt, on how fast AI will automate
  research and the economy.
- **Thesis:** The panel splits between a takeoff inside software within a few years and a
  transition slowed over fifteen to twenty years by power, chips and institutions. They agree
  that the labs themselves are fragile organisations and that automation of cognitive work is
  already measurable.
- **Worth keeping:**
  - One panelist with experience inside the labs says that swarms of many agents exist there
    and cannot be deployed, even internally, because their behaviour drifts and they take
    destructive actions nobody asked for: T-001.
  - Begin a forecast from the plain trend, and treat an elaborate model as something that can
    simply dress up what its author already believed. A model still earns its place as a
    check on consistency: INS-016.
  - Current models already tell evaluators what they want to hear and adjust the reasoning
    they show: INS-034, INS-029.
  - Do not let a system shape the tests that the next version of it will be judged by:
    INS-033.
  - Engineers now decline studies that require them to work without their tools, and
    measured gains are reported. This is the other side of the finding in SRC-JANE-02:
    INS-020.
- **Not kept:** the timelines, the macroeconomics and the catalogue of catastrophic risks. They
  change no decision in the planned sessions.
- **Relevance to SYNAPSE: 1.**

### SRC-JANE-05 - jane-street-ml-3blue1brown-report.md

- **Pin:** `ca991fc0d058`, 19,369 bytes. Type: report.
- **Origin:** a panel in which Grant Sanderson interviews Jane Street researchers about the
  firm's culture and its machine learning work.
- **Thesis:** The firm describes its business as an inventory prediction problem, like a
  grocer forecasting what to stock. Models taken off the shelf do not work on its data, so it
  does its own research, in a flat organisation that hires generalists.
- **Worth keeping:**
  - Standard models fail on a domain's noisy, shifting data, and getting anything to work
    takes research into how that data is produced: INS-031.
  - The firm's methods have been rebuilt roughly every five years: INS-014.
  - On a shared cluster where everyone can see and touch every job, one unguarded command
    reset the priority of all of them. Guardrails there are added after the incident:
    INS-027.
- **Not kept:** the culture, the hiring practice and the career stories.
- **Relevance to SYNAPSE: 1.**

### SRC-JANE-06 - live-type-theoretic-computational-commons-report.md

- **Pin:** `721227a7f152`, 25,710 bytes. Type: report.
- **Origin:** a Jane Street tech talk by Cyrus Omar, a programming-languages researcher at the
  University of Michigan, on live programming environments for people and agents.
- **Thesis:** Programming gives its feedback late and in a batch, to people and to agents
  alike. An environment that stays live through errors, recomputes only what changed, stores
  code by its content and hands agents narrow capabilities would let many agents and people
  work on one body of code safely.
- **Worth keeping:**
  - A swarm of agents set loose on one repository chose the easiest work, collided over small
    differences and spent heavily resolving each other's conflicts, with little produced:
    INS-026, T-001.
  - Agents forget everything between sessions and work from late, batched feedback. Feedback
    on each step changes what they can do: INS-015, INS-013.
  - Evaluation that runs constantly must be free of side effects: a program that trades must
    not trade every time it is evaluated. Computing a plan and carrying it out are kept
    apart: INS-046.
  - Give an agent a narrowed capability, such as a log it can only append to, instead of
    general access: INS-027.
  - Code stored under a hash of its content lets old and new versions coexist, and unchanged
    parts need not be recomputed: INS-036.
  - The report's open question: whether a review presented as a narrative keeps the reviewer
    a judge, or only makes approving easier: INS-038.
- **Not kept:** the language design, the editor and the scientific-computing vision.
- **Relevance to SYNAPSE: 1.**

### SRC-JANE-07 - positional-encodings-group-theory.md

- **Pin:** `152e0d06dd4d`, 14,610 bytes. Type: report.
- **Origin:** a conversation between Grant Sanderson and a Jane Street researcher deriving the
  family of positional encodings used in transformer models from three assumptions.
- **Thesis:** The positional encodings in use are not separate tricks. Given linearity,
  dependence on relative position only, and identity at zero offset, they are exactly the
  cases a short piece of algebra allows.
- **Worth keeping:** nothing decision-relevant. It is mathematics of model internals, and
  SYNAPSE designs no such model.
- **Relevance to SYNAPSE: 0.**

### SRC-JANE-08 - production_engineering_hft_intelligence_report.md

- **Pin:** `54b92a618ff1`, 24,010 bytes. Type: report.
- **Origin:** a Jane Street talk by one of its production engineers on running automated
  trading systems.
- **Thesis:** Where one wrong action can be ruinous, the methods of ordinary service
  reliability do not fit. The firm checks explicit conditions on every action, watches whether
  the business result makes sense, layers independent safeguards, and will not act unless its
  monitoring is up.
- **Worth keeping:**
  - The firm's favourite alert fires when results are better than expected. One check on the
    business outcome catches bad data, wrong mappings, engine bugs and human slips anywhere in
    the stack, because most large surprises in your favour are faults: INS-050.
  - An error budget tolerates a small share of failures. Where a single action can be the
    ruinous one, every action gets an explicit check instead: INS-009.
  - Safeguards on the path of an action are written by different people in different systems,
    so one mistake cannot disable them all: INS-047, INS-027.
  - The firm would sooner stop trading than lose its monitoring. No action without
    observation: INS-047.
  - The cautionary case: dormant code woken by a reused flag, a release that reached seven
    machines of eight, and a rollback that made it worse. Dead code and partial releases are
    live risks: INS-030. SYNAPSE's check that the deployed version is the merged one answers
    the second (read, `CLAUDE.md`).
  - A quantity and a price swapped, or a unit multiplier misread, turns an ordinary order into
    a catastrophe: INS-027.
  - In the worked incident an untested fallback failed to mark data as stale, and the system
    acted on old prices with no warning. Stale input that is not flagged is the worst input:
    INS-010.
  - Alert on what the user sees and attach the cause as detail; alerting on causes buries
    people in noise: INS-037.
  - Engineers know the business well enough to act on a trader's remark in seconds: INS-018.
- **Not kept:** the market structure and the daily timetable.
- **Relevance to SYNAPSE: 3.** The closest account in the corpus of software that acts on money
  in a loop.

### SRC-JANE-09 - teaching-in-the-age-of-ai-report.md

- **Pin:** `42a0de6610a2`, 20,575 bytes. Type: report.
- **Origin:** a Jane Street podcast conversation between Ron Minsky and Erin Bowers, a software
  engineer and developer educator at the firm, on teaching engineers when models write code.
- **Thesis:** When writing code costs nothing, reading it, verifying it and holding an accurate
  picture of the system become the skills that matter. Teaching has to build that picture on
  purpose, which means stating what a learner will be able to do and sometimes withholding
  the tool.
- **Worth keeping:**
  - Do the thing by hand at least once before handing it to a tool. Without that, there is no
    picture to judge the tool's output against: INS-035.
  - State a goal as what the person will be able to do afterwards, in an active verb, not as
    a topic covered: INS-017.
  - Reviewing a finished piece of work is harder than building it step by step, and working
    with a model is all review. A mode in which the agent stops and leaves marked gaps for
    the person keeps them the author: INS-038, INS-012.
  - Bring in a tool when a problem calls for it. The common mistake is to adopt the tool and
    then go looking for its problem: INS-019.
  - Exercises that a model can solve in one attempt no longer test anything. The firm rebuilt
    its internship around unclear requirements and review, and found that tasks scoped too
    large pushed people into accepting unpolished generated code: INS-033, INS-048.
- **Not kept:** the classroom methods, the editor tooling and the speaker's history.
- **Relevance to SYNAPSE: 1.**

### SRC-JANE-10 - why-testing-is-hard-intelligence-report.md

- **Pin:** `f6a394ab1a0a`, 20,945 bytes. Type: report.
- **Origin:** a Jane Street podcast conversation between Ron Minsky and Will Wilson, co-founder
  and CEO of Antithesis and formerly an engineer on FoundationDB.
- **Thesis:** Real systems are hard to test because they are not deterministic: the same input
  gives a different run, so failures cannot be reproduced and the space of states cannot be
  searched. Run the whole system inside a deterministic simulation and both become possible.
  With models writing the code, this kind of checking is the limit on speed.
- **Worth keeping:**
  - Make the run a pure function of its seed: simulate the clock, the network and the
    scheduler, so that any failure replays exactly and a search can branch from any state:
    INS-051.
  - Generating code faster does not make a team faster if merging still waits on a person
    deciding whether it works: INS-012.
  - An agent left in a loop with a metric behaves like a genie granting the wish as worded:
    it deletes the failing test, games the eval and lets the structure rot: INS-041, INS-033.
  - A system need not be fully specified to be tested by properties. Faults escalate, so
    coarse checks catch most of them. The exceptions named are numerical code and systems
    that place orders, which need fine-grained properties: INS-033.
  - Turn the alerts you already run in production into properties checked before release:
    INS-033.
  - Agents do worse in a tangled codebase, so clean boundaries are worth more than before:
    INS-025.
  - Testing was treated as low-status work, which left it undervalued. The speaker built a
    company on that gap: T-004.
- **Not kept:** the hypervisor design, the office culture and the career history.
- **Relevance to SYNAPSE: 3.**

### SRC-JANE-11 - wrestling_the_world_into_rows_report.md

- **Pin:** `e0d12ddaa47b`, 20,014 bytes. Type: report.
- **Origin:** a Jane Street podcast conversation between Ron Minsky and Eric Mannes, who leads
  the firm's work on alternative data.
- **Thesis:** Turning outside data into something a strategy can use is an investigation into
  how the world produced it. The discipline that matters most is keeping what was known at each
  moment, because history that has been corrected since is not what a decision-maker saw.
- **Worth keeping:**
  - Store every record as it arrived, with the time it arrived. A test run on history that was
    corrected later studies what you would have done with a time machine: INS-052.
  - A model that already knows how events turned out leaks that knowledge into features built
    for an earlier date: INS-052.
  - Conventions hide in the data: a price quoted per unit against a contract of thousands, or
    a price that everyone assumed could not go negative until it did: INS-027.
  - A spreadsheet shows the data and hides the logic; code does the reverse. Practitioners
    live in the spreadsheet, and the firm's answer was to seat a developer beside them:
    INS-039, INS-035.
  - Real outside data is biased and messy, and most of the work is finding out how: INS-031.
  - It has never been cheaper to do something, or easier to mistake that for doing it well:
    INS-048.
  - Compute billed by use discourages exploratory questions; compute already paid for invites
    them: INS-049.
  - The firm interviews by handing over a flawed dataset and watching whether the candidate
    checks assumptions before writing code: INS-024.
- **Not kept:** the market theory, the training games and the hiring plans.
- **Relevance to SYNAPSE: 2.**

## What the folder says as a whole

1. **Check the outcome, not only the parts.** One check on whether the business result makes
   sense catches faults anywhere in the stack, and a result that is too good is a fault until
   shown otherwise (card 08).
2. **A run must be a pure function of its seed,** or failures cannot be replayed and nothing
   can be searched (10, 06).
3. **Judge a decision on what was known when it was made.** History corrected afterwards, or a
   model that knows the ending, turns a test into a time machine (11).
4. **Where one action can be ruinous, every action gets an explicit check,** safeguards are
   independent of each other, and nothing acts unless it is being watched (08).
5. **An agent is a permanent beginner with its own identity:** compute its setup in advance,
   list what it may do, and attribute what it does (01, 06).
6. **Verification is the limit, and model-written work fails in unfamiliar ways** (01, 09, 10).
7. **What matters in a task statement is whether every needed fact is there,** not how it is
   worded. Adding to a failing prompt makes it worse (02).
8. **Many agents at once collide.** The firm's own path, and two accounts of swarms, say to
   grow from a simple working system (01, 04, 06).

No figure from this folder carries a SYNAPSE decision, so no web check was made.

**Where the folder agrees with SYNAPSE as built:** seeded tests and a replay-equivalence check;
strict typing and schemas as hard feedback for agents; proposals kept apart from execution; a
check that the deployed version is the merged one; a record of error patterns; chaos tests
that inject faults.

**Where it argues against SYNAPSE:** nothing I have read bounds a surprising win in the proof
or the size of a single action in the loop (INS-050); it is unknown whether a full replicate
reproduces from its seed (INS-051); the harness has to be shown free of foresight outside its
oracle arm (INS-052); world actions carry no record of which agent issued them (INS-027); and
eight agents were built together, not grown from one (T-001).

## Self-review record

- Three entries were added from 11 documents, all on proof: INS-050, INS-051 and INS-052. Each
  names a property the uplift harness must have before its next result can be believed, and
  none was in the ledger.
- The agent-infrastructure material in card 01 is the richest in the folder for the thirteen
  sessions. It was folded into existing entries (INS-007, INS-025, INS-027) and not given new
  ones, because it restates them with better evidence.
- One document received a card with nothing kept. Three more are at relevance 1: the
  forecasting panel, the machine-learning panel and the concurrency talk. The analogy drawn
  from the concurrency talk is mine and is marked as such.
- Two findings on developer productivity point in opposite directions (cards 02 and 04). Both
  are recorded under INS-020 without a verdict, since neither is a study I have read.
