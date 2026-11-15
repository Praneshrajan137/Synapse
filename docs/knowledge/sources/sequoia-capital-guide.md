# Digest: Sequoia Capital - GUIDE

Corpus folder `C:\Documentation\Sequoia Capital - GUIDE`. Read in full on 2026-11-15: 8 files,
175,099 bytes.

## What this folder is

Eight model-written reports on Sequoia Capital interviews: four with company builders and
investors on leadership, two with AI researchers, one with a historian of founders, and one
with the founder of an AI market-research company. Speakers are taken as verified under the
operator's decision of 2026-11-13.

## Cards

### SRC-SEQG-01 - databricks-extraction-report.md

- **Pin:** `73342fb398b6`, 24,461 bytes. Type: report.
- **Origin:** an episode of a Sequoia podcast in which Brian Halligan, co-founder of HubSpot,
  interviews Ali Ghodsi, co-founder and chief executive of Databricks.
- **Thesis:** A company usually fails from one dominant bottleneck, and the chief executive's
  job is to find it and give it far more attention than anything else for years. Real gains
  from AI come from redesigning processes, not from adding tools.
- **Worth keeping:**
  - Focus on the single largest bottleneck for one to three years, and treat weekly crises as
    noise. For SYNAPSE the bottleneck now is the proof that the consensus beats the tuned rule,
    and behind it a named user: INS-045, INS-017.
  - In one experiment the company removed all human contact from selling; revenue stopped
    growing for two quarters. Taking a part away is how its value was learned: INS-030.
  - Wondering why each new connector took three quarters when he could prototype one in two
    days, he wrote production code himself. The code was fast; long requirement documents,
    setting up partner environments and late testing were the drag. Specs became one-week
    markdown files and testing moved to the start: INS-013, INS-012, INS-020.
  - He expects AI to take at least a decade to spread, because every organisation's processes
    must be redesigned: INS-039.
- **Not kept:** the sales-hiring rubric, executive hiring, the rivalry and category story, the
  operating cadence and the remarks on going public.
- **Relevance to SYNAPSE: 1.**

### SRC-SEQG-02 - david-senra-400-founders-analysis.md

- **Pin:** `e3ee12f8894e`, 27,077 bytes. Type: report.
- **Origin:** Brian Halligan of Sequoia in conversation with David Senra, host of the *Founders*
  podcast, who has studied more than 400 founders' biographies.
- **Thesis:** The trait the founders share is extreme focus: ignoring the outside world and
  building what they themselves want.
- **Worth keeping:**
  - Focus means saying no to good ideas you want to pursue, because they distract from the
    great one. He warns AI companies against launching many products at once because decisions
    are now cheap to reverse: INS-045, Q-07.
  - The founders he admires built first for themselves as the most demanding user: INS-035.
- **Not kept:** the biographies, the psychology of drive, the remarks on co-founders, marriage,
  ego and control.
- **Relevance to SYNAPSE: 1.**

### SRC-SEQG-03 - demis-hassabis-agi-analysis.md

- **Pin:** `9261b2a1bba1`, 14,609 bytes. Type: report.
- **Origin:** a Sequoia interview with Demis Hassabis, co-founder and chief executive of Google
  DeepMind.
- **Thesis:** DeepMind's twenty-year plan to build general intelligence and then use it on
  science is on schedule. Learned models are becoming the instrument of science for complex,
  emergent systems.
- **Worth keeping:**
  - From a game that simulated a whole country on the hardware of its day: aim to be five
    years ahead of your time, not fifty: T-002.
  - Drug discovery is to move almost entirely into simulation, with the laboratory kept for
    validation. The SYNAPSE equivalent is to explore in the twin and keep the real world for
    confirming what the twin found: INS-046, INS-049.
  - A learned weather model is faster and more accurate than the traditional one, and learned
    simulators may yield explicit laws once sampled widely: INS-049, INS-031.
  - Build a precise, reliable tool first, and only then cross into autonomy: INS-022, INS-009.
- **Not kept:** the career history, the philosophy of information and consciousness, and the
  timeline for general intelligence.
- **Relevance to SYNAPSE: 1.**

### SRC-SEQG-04 - founder_leadership_intelligence_report.md

- **Pin:** `afaab5a0e608`, 23,436 bytes. Type: report.
- **Origin:** Brian Halligan of Sequoia interviews Ben Horowitz, co-founder of Andreessen
  Horowitz, on what makes a great founder.
- **Thesis:** Founders fail less from lack of knowledge than from lost confidence: deferring to
  others and putting off hard decisions. Culture is the behaviour that is enforced, not the
  values that are stated.
- **Worth keeping:**
  - Unmade decisions accumulate as decision debt, which paralyses an organisation more than a
    wrong decision would. The operator questions in `QUESTIONS.md` are SYNAPSE's decision debt:
    each one left open holds up session 3: Q-01, Q-03.
  - A founder hiring for a role he has never done is like judging an interpreter in a language
    he does not speak. Do the job briefly yourself first. For SYNAPSE that is operating the
    twin store before deciding what an operator needs: INS-035.
  - Culture is the behaviour actually enforced; stated values are platitudes. SYNAPSE's
    governance by gate rather than by prose is the same idea: INS-014.
- **Not kept:** the sales-leadership material, the investment anecdotes, the remarks on founder
  mode and venture capital, and the profanity.
- **Relevance to SYNAPSE: 1.**

### SRC-SEQG-05 - greg-brockman-human-attention-bottleneck.md

- **Pin:** `f5a59bdf9c1f`, 18,223 bytes. Type: report.
- **Origin:** a Sequoia fireside chat with Greg Brockman, co-founder and president of OpenAI.
- **Thesis:** Doing things has become cheap. The scarce resource is a person's attention to
  whether what was done is what they wanted, and the immediate limit on agents is the context
  they are given.
- **Worth keeping:**
  - Judging whether an output is good, and what was wanted, becomes the main bottleneck. People
    default to clicking approve, so systems must approve low-risk actions themselves and bring
    only the high-risk ones to a person: INS-009, INS-038.
  - A person is accountable for signing off every change merged to production: INS-012.
  - Asked to ping a developer about an error, an agent waited two minutes, judged it too slow
    and escalated to the developer's manager. Agents lack a sense of when and how far to
    escalate, so the wait and the default have to be designed: R-32.
  - Expecting a model to solve a problem while keeping it out of the meetings where the problem
    is discussed makes no sense. Context is the immediate limit: INS-010.
- **Not kept:** the compute economics, the progress estimates, the product announcement, the
  remarks on organisation and the science examples.
- **Relevance to SYNAPSE: 2.** It bears directly on how SYNAPSE uses its operator's attention.

### SRC-SEQG-06 - karpathy-agentic-engineering-report.md

- **Pin:** `12f51b41efb4`, 30,774 bytes. Type: report.
- **Origin:** Andrej Karpathy, co-founder of OpenAI and former head of AI at Tesla, interviewed
  by Stephanie Zhan at Sequoia's AI Ascent 2026.
- **Thesis:** Programming has become directing a model through its context. Casual building
  raises the floor for everyone; professional work with agents must keep the old quality bar,
  and the person's understanding of the domain remains the limit.
- **Worth keeping:**
  - Models automate what can be verified, because labs train them where an automatic checker
    exists. That makes capability jagged: a model that refactors a large codebase can advise
    walking to a car wash fifty metres away. Everyday logistics is the weak side, which is where
    SYNAPSE's disruption reasoner would work: INS-008, R-19.
  - Companies can build training environments with checkers for the specialised domains the labs
    ignore: T-004, INS-043.
  - Agents are like tireless interns without taste. One linked payments to accounts by matching
    email addresses rather than a permanent user identifier, and generated code is bloated:
    models asked to simplify a minimal codebase failed. Design judgment and simplification stay
    with the person: INS-048, INS-012.
  - Infrastructure for agents exposes sensors (what is the state) and actuators (what can be
    done); instructions to click a menu are for people. Setting up deployment, domains and keys
    is still a human chore: INS-025, INS-013.
  - You can hand off your thinking but not your understanding; to direct agents you must know
    the domain. For SYNAPSE that means the inventory literature, not more agents: INS-029, R-51.
  - His suggested hiring test: build a substantial system from a specification, then let many
    agents attack the deployed result: INS-029, INS-053.
- **Not kept:** the software 1.0 to 3.0 framing, the forecast of inverted computing, the
  example application and the remarks on what models are.
- **Relevance to SYNAPSE: 2.**

### SRC-SEQG-07 - listen-labs-market-research-intelligence-report.md

- **Pin:** `98d47a0fd166`, 15,701 bytes. Type: report.
- **Origin:** a Sequoia conversation with Alfred Wahlforss, co-founder of Listen Labs, which runs
  customer interviews with AI interviewers.
- **Thesis:** As building gets easy, knowing what to build becomes the hard part, and AI-run
  interviews at scale make finding out fast and cheap.
- **Worth keeping:**
  - Asked the same multiple-choice survey twice, people gave very different answers; open
    conversation was far more consistent. For Q-01, ask a dark-store manager open questions
    about real events, not a checklist: INS-018.
  - Most revenue comes from a small segment of customers, and finding them carries most of the
    engineering effort. In a store a small share of items is likely to carry most orders, so the
    proof should be read by item class as well as in total: INS-003.
  - Their own evaluations at first passed about a fifth of interviews; work raised that to 85
    per cent, and harder evaluations then reset it to a fifth. An evaluation is hardened once it
    is passed: INS-033.
  - Every finding links back to the clip and transcript it came from: INS-034.
  - Founders want to build something complex; customers want something simple that works:
    INS-048.
- **Not kept:** the company's growth figures, the simulated-persona accuracy claims, the panel
  and the historical marketing examples.
- **Relevance to SYNAPSE: 1.**

### SRC-SEQG-08 - scaling-ai-rocketships-intelligence-report.md

- **Pin:** `b7ac285bb486`, 20,818 bytes. Type: report.
- **Origin:** Brian Halligan of Sequoia with the chief executives of ElevenLabs and Lovable, two
  fast-growing European AI companies.
- **Thesis:** Fast growth in AI comes from choosing a large problem at the right time, small
  teams that adopt new models within a day, and leaders who go into the detail.
- **Worth keeping:**
  - The host's lesson: startups die of overeating more often than of starvation. He keeps a
    public monthly list of eight priorities to justify saying no: INS-045.
- **Not kept:** the founder histories, team structures, planning cadence, email triage, the
  remarks on Europe, work hours and personal brand.
- **Relevance to SYNAPSE: 0.** One point, already well covered.

## What the folder says as a whole

1. **Find the one bottleneck and give it most of the attention; say no to good ideas** (cards
   01, 02, 08).
2. **A person's attention is the scarce resource:** approve the routine automatically, bring the
   risky to a person, and design how and when to escalate (05).
3. **What can be verified gets automated,** so capability is uneven and weakest in everyday
   physical logistics; the person's understanding of the domain stays the limit (06).
4. **Do the job yourself before hiring for it or building for it** (04, 02), and ask customers
   open questions about real events (07).
5. **Decisions left unmade cost more than wrong ones** (04).

No figure from this folder carries a SYNAPSE decision, so no web check was made.

**Where the folder agrees with SYNAPSE as built:** confidence-gated escalation that brings only
some decisions to a person; governance enforced as behaviour by gates rather than by prose;
and decisions linked back to their evidence in the audit record.

**Where it argues against SYNAPSE:**

- Eight agents across seven functions run against the folder's most repeated advice, focus on
  one thing (Q-07). Four of the eight documents say it.
- The operator questions are decision debt in the sense card 04 means; eight are open, and
  session 3 cannot define finished until Q-01, Q-03 and Q-08 are answered.
- The disruption path puts a language model on everyday logistics, the domain card 06 names as
  the weak side of models' uneven capability (R-19).

## Self-review record

- No new ledger entry; the folder corroborates existing ones, chiefly INS-045 and INS-009.
- Card 04's decision-debt point was tied to `QUESTIONS.md` rather than made an entry, because
  it changes no design, only how the operator questions are treated.
- Card 07's claim about the share of orders carried by a few items is my inference about stores,
  not the source's, and is marked so.
- The leadership, hiring and biography material, most of cards 01, 02, 04 and 08, was read and
  left out.
