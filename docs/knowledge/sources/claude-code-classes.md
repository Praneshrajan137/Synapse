# Digest: Claude Code - Classes

Corpus folder `C:\Documentation\Claude Code - Classes`. Read in full on 2026-11-13 and
2026-11-14: 20 files, 430,469 bytes.

## What this folder is

Twenty model-written reports on talks and workshops about building and running agents, most
from Anthropic's own events and channels. Under the operator's decision of 2026-11-13 the
speakers are taken as verified, so no search was spent on who they are. Notes under
"File fidelity" concern the report, not the speaker: where a transcript was cut short, where
the summarising model added material of its own, or where it flags a transcription slip.

One file, `nebulock-mythos-intelligence-report.md`, has a byte-identical copy in the corpus
folder Sequoia Capital- AI. It is read here and not again there.

## Cards

### SRC-CLASSES-01 - agent-decomposition-report.md

- **Pin:** `39d644c8a4de`, 18,002 bytes. Type: report.
- **Origin:** an Anthropic Applied AI workshop in London on decomposing an agent that outgrew
  its prompt. The worked example is an inventory management agent for a mid-sized retailer:
  stock tracking, demand forecasting, supplier selection, purchase orders, reports.
- **Thesis:** An agent that grows by adding rules to its prompt and tools to its list starts to
  regress. The repair is to move procedures into skills loaded on demand, replace many special
  tools with a few general ones plus code execution, and keep sub-agents only where they are
  justified. In the example this took the eval pass rate from 62% to 92%.
- **Worth keeping:**
  - A sub-agent is justified by two things only: parallel work on independent pieces, or a
    fresh view kept apart from the main context, as a reviewer has. A sub-agent that wraps a
    tool should be folded back: INS-028.
  - The refactor was driven by a fixed eval suite and got better by removing parts: INS-030.
  - One failure in the example was context lost between a sub-agent and the orchestrator:
    INS-005.
  - The eval suite mixed regression tasks, known-failure tasks, deterministic graders (tokens,
    latency, turns) and a judged grader: INS-003.
  - With a long prompt the model read the right inputs and still computed with a wrong one.
    Long standing context causes errors, not just cost: INS-014.
- **Not kept:** the vendor's hosted agent platform, and the advice to give an agent a shell
  (SYNAPSE's agents are services, not model loops).
- **Relevance to SYNAPSE: 3.** The example is SYNAPSE's own domain, built the opposite way.

### SRC-CLASSES-02 - agent-loops-mastery-report.md

- **Pin:** `77509e207875`, 19,748 bytes. Type: report.
- **Origin:** a talk by Sid Bidasaria of the Claude Code team on verification loops, skills and
  background routines.
- **File fidelity:** the report says its transcript ends at 29:57 and that its fifth chapter was
  filled in by the summarising model from outside reading. That chapter is not used.
- **Thesis:** Developers have become testers for their agents. The way out is to let the agent
  run the same check a person would (build, run, look at the effect, test), package that check
  as a reusable skill the agent keeps up to date, and only then run several agents at once.
- **Worth keeping:**
  - The question to ask of a codebase: what does an agent need that a person takes for granted?
    The usual answers are a way to start the app, a way to observe it, proof of success, and a
    way past login and empty state: INS-013.
  - A verification procedure belongs in a skill file that the agent amends when it hits a new
    blocker: INS-013.
  - A person can attend to four or five agent sessions at most: INS-026.
- **Not kept:** the product tour of session-management surfaces.
- **Relevance to SYNAPSE: 3.** It names what a verification skill for this repository must
  contain.

### SRC-CLASSES-03 - agents-that-remember-analysis.md

- **Pin:** `6363dd627af4`, 21,085 bytes. Type: report.
- **Origin:** an Anthropic engineer's workshop on memory stores and background consolidation
  ("dreaming") for hosted agents.
- **Thesis:** Memory for an agent works best as a plain file system it can search, plus a
  background pass that checks stored notes against what happened, merges duplicates and writes
  an index. The pass works on a copy and presents a diff for approval.
- **Worth keeping:**
  - Index first: a short index file that points at the right note saves a search of everything:
    INS-025.
  - Consolidation is non-destructive. It writes to a copy and a person approves the diff:
    INS-004 (compare against the original).
  - Reference material an agent must not change is mounted read-only: INS-027.
- **Not kept:** the hosted product's parameters and pricing notes.
- **Relevance to SYNAPSE: 2.** It describes how this knowledge base and the session memory
  should be kept, more than anything inside the product.

### SRC-CLASSES-04 - ai_engineering_and_agent_economy_report.md

- **Pin:** `6768c2563e0e`, 21,303 bytes. Type: report.
- **Origin:** two interviews on Anthropic's channel: Mikhail Parakhin, CTO of Shopify, and
  Patrick Collison, CEO of Stripe.
- **Thesis:** The large return from AI is in doing what could not be done before, not in doing
  routine work faster. Both companies pair unrestricted use of the strongest models in
  development with hard, deterministic limits on what agents may touch.
- **Worth keeping:**
  - Shopify models a merchant's business as a sequence of actions, learned from real data, and
    tests interventions on that model before acting in the world: INS-031.
  - Models are eager to agree, and an idea now becomes code without the argument that used to
    filter it. Technical judgment matters more, not less: INS-029.
  - Stripe holds its reliability with invariants and hard barriers, not with model behaviour,
    and exposes agent-written changes in stages: INS-014, INS-022.
  - The strongest model for development and research; small tuned models in production:
    INS-021.
  - Long planning with the model first, then many agents on independent parts: INS-017.
  - A codebase can now be rewritten from itself cheaply, which lowers the cost of slimming
    one: INS-019.
- **Not kept:** the agent-to-agent payments forecast and the firm-creation statistics (outside
  the planned sessions), and unlimited token budgets (see T-008).
- **Relevance to SYNAPSE: 3.** Shopify's twin is the nearest thing in the corpus so far to
  SYNAPSE's own, and it differs in the one way that matters: it is learned from real merchants.

### SRC-CLASSES-05 - airops-claude-enterprise-agents.md

- **Pin:** `951b49008b1a`, 23,077 bytes. Type: report.
- **Origin:** a talk by AirOps's product lead on moving a marketing-content product from
  node-based workflows to agents.
- **File fidelity:** the report flags one figure as a likely transcription slip (a token saving
  given as 8%). It is not used.
- **Thesis:** For non-technical users an agent product succeeds through its harness and its
  review surfaces, not through the model. Solving one point of friction moves the bottleneck to
  the next, and the work is to keep following it.
- **Worth keeping:**
  - Start with one agent loop and add a sub-agent only when a specific quality failure calls
    for it: INS-028.
  - Compile shared context once at the start of a run into a fixed artifact that every later
    step reads, so steps do not drift apart by querying live sources: INS-010.
  - Human review is placed inside the run at named steps, assigned to a person, and managed
    through an inbox and a batch grid: INS-009.
  - Replace an agent's repeated wandering through general tools with one deterministic tool
    that returns the structured answer: T-010.
  - Keep the product to its core user; versatile models invite sprawl: INS-018.
- **Not kept:** the marketing domain itself and the customer results.
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-06 - autonomous-coding-analysis.md

- **Pin:** `9dca5389c9f7`, 28,366 bytes. Type: report.
- **Origin:** an Anthropic product talk on how coding models changed over twelve months and
  what teams should do about it.
- **File fidelity:** the report's own review section doubts one anecdote in the talk (a runtime
  rewritten in a week). The anecdote's point, that an exhaustive test suite is what made a
  week-long unattended run possible, does not depend on the detail and is kept.
- **Thesis:** Models now plan before acting, recover from their own errors and stay coherent
  over very long runs. Teams benefit only if they keep evals that can still fail, cut the
  scaffolding written for weaker models, and give the model room and safe autonomy.
- **Worth keeping:**
  - An eval the system always passes has stopped measuring. Build evals from real failures and
    keep raising them: INS-033.
  - Remove legacy instructions one at a time, rerun the evals, and keep the removal if the score
    holds: INS-030, INS-014.
  - Classify each proposed action as safe to run or needing a person, by what it can damage:
    INS-009.
  - A long unattended run is only as good as the test suite that tells it when it is wrong:
    INS-013.
- **Not kept:** the benchmark history and model names.
- **Relevance to SYNAPSE: 3.**

### SRC-CLASSES-07 - autonomous-software-engineering-intelligence-report.md

- **Pin:** `d8aa2324f4ef`, 39,219 bytes. Type: report.
- **Origin:** two conversations on Anthropic's channel: the founder of Factory, and Salesforce's
  engineering leadership, on running autonomous engineering at enterprise scale.
- **Thesis:** Autonomy is a function of evaluation, not of generation. Agents do best with
  large, well-specified goals they decompose themselves, and an organisation gains only if it
  demands objective proof of work and keeps tearing down the scaffolding the models outgrow.
- **Worth keeping:**
  - Autonomy with no empirical validation is theatre. Proof of work means objective evidence,
    including proof that what was not asked for did not change: INS-034.
  - Keep a benchmark of tasks the current system fails, and admit a new model or harness only
    when it passes some of them: INS-033.
  - Give agents large goals with stated success criteria; the person should not do the
    decomposition: T-011, INS-017.
  - Measure effective output per unit of compute, not volume, and match the model tier to the
    difficulty of the task: INS-020, INS-015.
  - When output is no longer scarce, the question becomes which outputs matter and what the
    organisation's core competency is: INS-018.
  - Skills are evaluated by running the same sessions with and without them: INS-030.
  - Model, harness and organisation are three nested layers, and the model keeps absorbing the
    harness: INS-014.
- **Not kept:** the legacy-migration case and the incident-triage story (no counterpart in
  SYNAPSE's planned work).
- **Relevance to SYNAPSE: 3.** It gives the name for the gap recorded as T-009.

### SRC-CLASSES-08 - base44-ai-scaling-intelligence-report.md

- **Pin:** `1e793c821a95`, 18,182 bytes. Type: report.
- **Origin:** a talk by base44's product and AI leads on growing from one engineer to eighty
  without losing speed.
- **Thesis:** Keep everything simple. A small team should not build heavy process or a heavy
  eval suite; it should mine what it already has (git history, past review comments, production
  traffic) and let the agent turn that into onboarding, review and evaluation.
- **Worth keeping:**
  - A team's standards can be compiled from its past actions, such as review comments and
    experiment decisions, into an automated reviewer: INS-032.
  - Ask the repository, not a manual. New engineers query the commit history and ask for a
    diagram of a component, because written documentation decays: INS-025.
  - Evaluate recovery, not only first output. Feed the failure back and measure whether the
    system corrects itself, and at what cost: INS-003.
  - A cheap signal from real use can stand in for a full eval suite early on: INS-033.
  - Give the testing agent a tool to force the system into a specific state, so edge cases can
    be reached on purpose: INS-013.
- **Not kept:** the experimentation bot and the company history.
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-09 - building-secure-agents-intelligence-report.md

- **Pin:** `c9b2d96adc4f`, 18,240 bytes. Type: report.
- **Origin:** a conversation on Anthropic's channel with Dan Shipper and a colleague from Every
  about a shared agent their company uses inside Slack.
- **Thesis:** Benchmarks say a model is competent; they do not say it can do your work. What
  compounds is company-specific taste, captured from daily corrections and turned into tests
  and skills.
- **Worth keeping:**
  - The difference between what the agent produced and what the expert finally accepted is
    recorded, turned into a rule and fed back. Every correction is a label: INS-032.
  - A benchmark is an entrance score; what matters is a trial on the real work: INS-033.
  - The agent acts under the identity and permissions of the person who asked: INS-027.
  - Agents arrived first where results can be verified mechanically. Work with delayed or
    subjective feedback needs its own way to check results: INS-031.
- **Not kept:** the chat-surface design questions and the cultural skills.
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-10 - claude-agents-memory-dreaming-report.md

- **Pin:** `86c3a8e256a6`, 15,301 bytes. Type: report.
- **Origin:** an Anthropic talk introducing memory and background consolidation for hosted
  agents. It overlaps SRC-CLASSES-03 and adds the reasoning behind the design.
- **Thesis:** Notes an agent writes while working are useful locally and messy globally. A
  separate pass, outside the working loop, sees patterns across sessions that no single run can
  see, and should be treated like code review for memory.
- **Worth keeping:**
  - Patterns across runs are invisible from inside one run; something has to look across them:
    INS-005.
  - Shared knowledge is versioned, attributable and reviewed like code, with stable policy
    read-only and working notes writable: INS-027, INS-025.
  - Writers to a shared store need a rule for concurrent writes: noted for session 2 under
    R-26, since several agents act on one world.
- **Not kept:** the partner results and the product timeline.
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-11 - claude-code-team-norms-report.md

- **Pin:** `9a708c77f44b`, 22,250 bytes. Type: report.
- **Origin:** a talk by Fiona Fung, who leads engineering for Claude Code and Cowork at
  Anthropic, on team norms once writing code is no longer the slow part.
- **Thesis:** Engineering process was built to protect scarce coding time. With coding cheap,
  the scarce things are verification, review and maintenance, and the old process becomes drag
  unless someone removes it on purpose.
- **Worth keeping:**
  - Processes pile up, because nobody deletes one unprompted. Leaders have to audit them and
    give explicit permission to remove: INS-030, T-005.
  - Settle a technical disagreement by building both options and comparing them; building now
    costs less than arguing: INS-030.
  - Product sense comes from using the product every day and sitting with users, not from
    dashboards: INS-035, INS-018.
  - When cycle time does not fall, look for the queue downstream in CI: INS-012.
  - The code is the source of truth, and newcomers learn the system by asking it: INS-025.
  - Specs and standards live in the repository beside the code so review can check against
    them. SYNAPSE already does this (a `spec.yaml` per agent); no entry needed.
- **Not kept:** hiring profiles and management practice.
- **Relevance to SYNAPSE: 3.**

### SRC-CLASSES-12 - elicit-dsl-analysis.md

- **Pin:** `1939638d1a1a`, 23,227 bytes. Type: report.
- **Origin:** a talk by James Brady, head of engineering at Elicit, on making agent workflows
  trustworthy with a small custom language.
- **Thesis:** How an answer was produced matters as much as the answer. Elicit makes the agent's
  plan an executable program in a deliberately restricted language, re-runs the whole program on
  every change, and keeps that affordable by caching each step under a hash of its content.
- **Worth keeping:**
  - Two systems with the same output do not deserve the same trust. The process has to be
    legible, and it has to be what actually ran: INS-034, T-004.
  - Re-run everything from the top each time, and cache each expensive step by content so only
    what changed is recomputed: INS-036.
  - Restrict what an agent can express, so that guarantees become possible. SYNAPSE's four
    typed action kinds are a small case of this (read): INS-027.
  - Model calls pass through a gateway that alone holds the credentials: INS-007.
  - Most of the work was ordinary engineering: an event log, session recovery, interrupts:
    INS-006.
- **Not kept:** the language design itself. The speaker says the approach suits only products
  where rigour outranks speed.
- **Relevance to SYNAPSE: 3.** It is the corpus's clearest argument that a legible, faithful
  decision process is worth building, which SYNAPSE has built.

### SRC-CLASSES-13 - evals-for-taste-analysis.md

- **Pin:** `5e10d5601aa4`, 16,863 bytes. Type: report.
- **Origin:** an Anthropic talk on evaluating a subjective task, slide generation, by repeated
  measured improvement.
- **Thesis:** Subjective quality can be measured by combining exact checks, calibrated model
  judges and people. A checker told to hunt for faults finds more than one asked to confirm,
  and a stronger model can make a carefully engineered prompt unnecessary.
- **Worth keeping:**
  - A reviewing stage must assume a fault exists and look for it. One that confirms adds
    nothing: INS-023.
  - Evals are living things and have bugs of their own: INS-033.
  - A stronger model with a bare prompt beat a weaker one with an engineered prompt: INS-014.
  - A model judge needs the worst and best case defined, and should write its reasoning before
    its score. This matters only if SYNAPSE's model judge goes live; in CI it is a stub (read,
    `CLAUDE.md` E-S9-12). No entry.
- **Not kept:** the slide-design rules.
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-14 - how-we-claude-code-intelligence-report.md

- **Pin:** `24fe2064fc86`, 21,579 bytes. Type: report.
- **Origin:** an Anthropic workshop on development workflows built for agents.
- **Thesis:** Longer agent runs raise the cost of a wrong specification. So requirements are
  drawn out by having the model interview the person, designs are shown as dense interactive
  pages, and components publish machine-readable state so that verification checks state and
  not appearance.
- **Worth keeping:**
  - People recognise what they want when they see it. Let the model interview for requirements
    before anything long is written: INS-017.
  - One machine-readable contract, checked from three places: a person's view, an agent, and
    headless CI. SYNAPSE's single deploy oracle with three call sites is the same pattern
    (read, `CLAUDE.md`): INS-034.
  - Plant a check that must fail, to prove the verification reports failures: INS-033.
  - Markdown past a couple of hundred lines stops being read: T-005. This applies to the ledger
    in this folder as much as to anything else.
- **Not kept:** the frontend attribute pattern (the frontend is not being rebuilt) and video
  evidence.
- **Relevance to SYNAPSE: 3.**

### SRC-CLASSES-15 - nebulock-mythos-intelligence-report.md

- **Pin:** `0af90d76d87f`, 18,900 bytes. Type: report. Byte-identical copy in Sequoia Capital-
  AI.
- **Origin:** an interview with Damien Lewke, founder of Nebulock, on AI and cyber defence.
- **Thesis:** Attackers now work with valid credentials, so each security tool sees normal
  activity and the breach shows only in the sequence across tools. Defence has to hunt on the
  assumption that something is already wrong.
- **Worth keeping:**
  - Activity that is green in every layer can be red in sequence. SYNAPSE's seam defects had
    this shape: INS-005.
  - Hunt before the alarm. Assume a fault exists and go and look: INS-024.
  - Hold on to the problem, and confirm that people have it before building: INS-018.
- **Not kept:** the threat landscape and the security product.
- **Relevance to SYNAPSE: 1.**

### SRC-CLASSES-16 - omni-ai-analytics-intelligence-report.md

- **Pin:** `e229d9d0b426`, 21,907 bytes. Type: report.
- **Origin:** a talk by Chris Merrick, co-founder and CTO of Omni, on building an analytics
  agent.
- **Thesis:** The agent became reliable through three things: a curated layer of business
  meaning between the model and the data, a bounded budget to recover from descriptive errors,
  and the removal of a two-level agent design whose outer agent did not know what the inner one
  could do.
- **Worth keeping:**
  - An orchestrator that does not know the limits of the agent it directs produces silent
    failures. They merged the two into one: INS-028, INS-005.
  - Reading individual session traces exposed that cause where automated scoring had not:
    INS-024.
  - A failing step should return a descriptive error, and the caller should have a bounded
    budget to recover: INS-006.
  - The model generates; a person validates and adjusts in a proper interface: INS-034.
  - The most demanding user was the company's own CEO, and that pressure drove the fixes:
    INS-035.
- **Not kept:** the semantic-layer design and the choice of query format.
- **Relevance to SYNAPSE: 3.** A third production team in this folder that removed a layer of
  agents.

### SRC-CLASSES-17 - self-healing-software-analysis.md

- **Pin:** `80e3ef5530b0`, 22,862 bytes. Type: report.
- **Origin:** a talk from Lovable on how its app-building platform repairs itself.
- **Thesis:** For users who never see the code, being stuck is fatal. So the platform measures
  being stuck, injects known fixes matched to the user's stack, and lets its agent report
  platform faults into a pipeline that drafts repairs for people to approve.
- **Worth keeping:**
  - An agent's report of what obstructs it is a telemetry stream. Aggregated, it surfaced
    outages before monitoring did and fed a steady flow of merged fixes: INS-037.
  - Stored know-how has a half-life. Track how often each item helps, prune what stops helping,
    and expect model upgrades to make workarounds redundant: INS-014.
  - People approve the agent-drafted repairs; about half are merged: INS-009.
- **Not kept as an entry:** a classifier for user friction. It needs users first.
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-18 - spotify-ai-transition-analysis.md

- **Pin:** `132485dec9cf`, 22,692 bytes. Type: report.
- **Origin:** a talk by Niklas Gustavsson, VP of engineering and chief architect at Spotify.
- **Thesis:** Agents are only as good as the codebase and platform they work in. Fifteen years
  of standardisation, a machine-readable catalogue of systems and owners, and checks that give
  immediate feedback are what let Spotify run agents across thousands of repositories.
- **Worth keeping:**
  - Fewer technologies means faster work, for people and for agents. Fragmented code degrades
    what an agent produces: INS-019, T-002.
  - Deterministic code schedules, orchestrates and merges; the model does the part that varies:
    INS-008, INS-023.
  - A catalogue of systems and owners is exposed to agents as a tool: INS-025.
  - Lint and build feedback inside the agent's own run lets it correct itself before review:
    INS-013.
  - As change volume rose, review was tiered by risk: INS-009, INS-012.
- **Not kept:** the internal tool names and the migration statistics.
- **Relevance to SYNAPSE: 3.**

### SRC-CLASSES-19 - the-thinking-lever-intelligence-report.md

- **Pin:** `b1bb06b1df8f`, 15,974 bytes. Type: report.
- **Origin:** a talk by Alexander Bricken of Anthropic's applied research team on compute spent
  at inference time.
- **Thesis:** A model's results improve with the reasoning it is allowed at run time, with
  diminishing returns at the top. Where a task needs real understanding, a larger model at low
  effort beats a smaller one at high effort.
- **Worth keeping:**
  - Match effort to the task. The top setting can double cost for a marginal gain, and
    extraction or classification needs little: INS-015.
  - Spending more compute on harder decisions is the idea behind SYNAPSE's four decision tiers
    (read, `CLAUDE.md`). Nothing to change; no entry.
- **Not kept:** the benchmark material and the observation that a tightly budgeted model takes
  shortcuts (interesting for decisions made under brownout, but speculative here).
- **Relevance to SYNAPSE: 2.**

### SRC-CLASSES-20 - video-intelligence-report.md

- **Pin:** `3aa9c137c0ac`, 21,692 bytes. Type: report.
- **Origin:** a talk on governing agent skills in systematic trading, given by Man Group's head
  of data and AI, Tashara Fernando.
- **Thesis:** The model is a commodity and the firm's own context is the advantage. That context
  reaches the model through skills, which must be owned, tested and retired like production
  code. Signals researched by agents run real capital because each one passes the same long
  historical backtest.
- **Worth keeping:**
  - The proof standard: every strategy is run against fifteen or more years of real history,
    through different regimes and stresses, and judged on return, worst loss and risk-adjusted
    return together: INS-031, INS-003.
  - A decision is the visible tip. The data preparation underneath has to be standard or
    results cannot be compared: INS-031.
  - Skills written by enthusiasts encode one person's habits. Ownership, tests and retirement
    are decided before the first one ships: INS-030, INS-032.
  - Context that exists nowhere public is the moat: INS-018.
- **Not kept:** the trading example and the adoption figures.
- **Relevance to SYNAPSE: 3.** Systematic trading is the closest analogue in the corpus to what
  SYNAPSE's uplift harness is trying to do: prove a decision policy before it acts.

## What the folder says as a whole

1. **Evaluation decides everything.** Autonomy is a function of evaluation, not of generation.
   An eval has to be able to fail, be built from real failures, carry a planted fault, and be
   kept alive (cards 06, 07, 08, 09, 13, 14).
2. **Simplify, and prove the simplification.** Fewer agents, fewer tools, shorter prompts,
   fewer technologies. Remove a part, rerun the fixed eval, keep the removal if the score
   holds. Processes pile up unless someone is allowed to delete them (01, 05, 06, 07, 11, 18).
3. **Separate agents need a reason.** Parallel breadth or a fresh view. Three production teams
   in this folder removed a layer of agents and got better results (01, 05, 16).
4. **The agent must be able to verify by itself.** Said again by five documents here, after
   six in the first two folders (02, 06, 08, 14, 18).
5. **The process must be legible and must be what ran.** Identical outputs do not earn
   identical trust (07, 12, 14, 16).
6. **Standards compound from past actions,** and stored know-how decays unless pruned (08, 09,
   17, 20).
7. **Where feedback is delayed, the proof is a model of the world fitted to real history**
   (04, 20).

No figure from this folder is load-bearing for a SYNAPSE decision, so no web check was made,
in line with the operator's decision that the speakers are verified.

**Where the folder agrees with SYNAPSE as built:** decision tiers that spend more compute on
harder decisions; a legible decision anatomy and audit chain; positive and negative controls
and a gate-falsification sweep; agents that report when they are degraded; typed action kinds;
one deploy oracle called from three places.

**Where it argues against SYNAPSE:** it is the strongest folder yet on T-001 (the example
closest to SYNAPSE's domain was improved by removing sub-agents), it sharpens T-002 (fewer
technologies) and T-005 (process and know-how that nobody prunes), and it adds T-012: the twin
is declared, where the corpus's comparable systems are fitted to real history.

## Self-review record

- Skill governance, codebase standardisation and inference effort were each drafted as entries
  and folded into INS-030, INS-019 and INS-015, which they extend.
- Model-judge calibration and the frontend state-contract pattern were left out: SYNAPSE's
  judge is a stub and its frontend is not being rebuilt.
- One report's final chapter was written by the summarising model from outside reading, by its
  own account; it was excluded.
- Reading this folder showed that the ledger is already past the length one of these talks
  gives as the limit of what gets read. A one-page synthesis is now a planned last step of
  session 1 (see README).
