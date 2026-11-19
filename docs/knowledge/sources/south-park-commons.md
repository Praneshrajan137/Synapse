# Digest: South Park Commons

Corpus folder `C:\Documentation\South Park Commons`. Read in full on 2026-11-15: 13 files,
336,772 bytes.

## What this folder is

Thirteen model-written reports on talks, interviews and panels hosted by South Park Commons, a
San Francisco community for technical founders. Speakers are taken as verified under the
operator's decision of 2026-11-13.

## Cards

### SRC-SPC-01 - ai-cybersecurity-crisis-report.md

- **Pin:** `a5fe9d5e31f6`, 18,240 bytes. Type: report.
- **Origin:** an interview at South Park Commons with Nikesh Arora, chief executive of Palo Alto
  Networks.
- **Thesis:** Models that write code well find its flaws even better, so a decade of
  undiscovered vulnerabilities will surface in months. Patching at that rate needs generated
  fixes, tested in the real environment and checked by a person, and agent traffic needs the
  same authentication and inspection as any other.
- **Worth keeping:**
  - Patch load grows with everything a system carries: vendor software, custom code and open
    source. Each dependency and service SYNAPSE keeps is a future stream of patches, which
    counts for the cut list in session 3: INS-019, T-002.
  - Most companies cannot say how many models and agents they run, and agent protocols and
    agent-to-agent traffic were built without authentication. For SYNAPSE: what stops one agent
    calling another, or the world, outside its function: INS-027, R-18.
  - A generated fix is tested in its environment and reviewed before it ships: INS-012.
  - Specialised companies win through domain data, connections to the systems that do the work,
    and fulfilment, not by building their own base models: INS-039.
- **Not kept:** the career history, the leadership and risk-taking advice, the market figures,
  and the forecast of experts directing fleets of agents.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-02 - ai-startups-gokul-rajaram-intelligence-report.md

- **Pin:** `cfebd7a29cfc`, 18,374 bytes. Type: report.
- **Origin:** an episode of South Park Commons' podcast in which Aditya Agarwal interviews Gokul
  Rajaram, an investor and board member who held product roles at Google, Facebook and Square.
- **Thesis:** A company started for its own sake drifts with every trend, so start from a
  problem you know deeply. Learn it by working inside the customer's operation, and by asking
  people to recount their last experience rather than what they want.
- **Worth keeping:**
  - Asking users what they want produces requests for a faster version of what they have.
    Asking them to walk through the last time it happened, step by step, shows the real
    friction. For Q-01, the question to a dark-store manager is how the last stockout went, from
    first sign to resolution: INS-018.
  - Before building for a trade, work inside one of its businesses for a week or two: INS-035.
  - The best founders know the history of their problem in depth; one pair read decades-old
    books on the payments industry. For SYNAPSE that history is the operations-research
    literature on inventory control, which is already queued: R-51.
- **Not kept:** the founder archetypes, team shapes, the career advice and the remarks on
  India's startup ecosystem.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-03 - Anthropic's Head of Design on AGI-Maximalist Product Design.md

- **Pin:** `df4dcdf0a2df`, 39,475 bytes. Type: report.
- **Origin:** a South Park Commons conversation with Joel Lewenstein, head of design at
  Anthropic.
- **Thesis:** At a research-led lab the model creates most of the value, so product work opens
  ways for people to reach what the model can already do rather than planning features far
  ahead. The team keeps working close to the production code, because every abstraction above
  it decayed.
- **Worth keeping:**
  - Each attempt to work through something other than the code itself ended with the team back
    in the code, because a production codebase is the source of truth that stays current. Design
    files and documents decay: T-005, INS-014.
  - Tools are built freely inside the company, and the ones that colleagues keep using are the
    ones taken further: INS-035, INS-030.
  - A model summarises threads and spots overlapping projects well, but the hard trade-offs stay
    with people. Only problems with no obvious answer should reach the person at the top. For
    SYNAPSE, an escalation should carry a real trade-off, not a routine call: INS-038.
  - App submissions have risen with generated code while ratings and the number of apps in
    real use have not. Volume is not quality: INS-048.
  - Before asking the model, write down your own guess, why, and the alternatives. The SYNAPSE
    analogue is writing down the predicted result before a measurement runs: INS-002, INS-029.
  - He reports that a customer said Anthropic changes its interface so often that users no
    longer notice, and he took it as criticism. For SYNAPSE, the console was restyled several
    times in a few sprints; for an operator, a stable screen is part of the product: R-39.
- **Not kept:** the lab's history and structure, the wind-farm metaphor, the internal tooling
  and the remarks on personal apps.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-04 - claude-code-intelligence-report.md

- **Pin:** `c6978a9e0831`, 22,767 bytes. Type: report.
- **Origin:** a South Park Commons question-and-answer session with Thariq Shihipar of the
  Claude Code team at Anthropic.
- **Thesis:** Models can already do more than the tools around them let people use. Let the
  model gather its own context with search, and delete scaffolding that a newer model no longer
  needs.
- **Worth keeping:**
  - The expected route to coding on a whole codebase was ever larger context windows. What
    worked was a model that searches for and reads the files it needs: T-016, INS-015.
  - Plan mode was built for an older model, and the team stopped using it once newer models
    planned without it. Memory and retrieval systems built for older models now get in the way.
    Delete scaffolding when the model has caught up: INS-014, INS-030.
  - Evaluations do little for a product's first version, where fast iteration and intuition
    lead. They matter at scale, to make quality visible across teams, and some failures (a model
    stopping early) are seen in use before anyone can write a test for them: T-019, INS-033.
  - Let the agent interview you to surface what you did not know to say, and try ideas as cheap
    isolated prototypes before wiring them in: INS-017.
  - A large rewrite into another language was carried by a thorough test suite: INS-012.
  - More code shipped is not more business. Giving a 1990s car dealer email sped up its staff;
    letting customers buy online changed the business: INS-020.
  - The team builds the tool with the tool: INS-035.
- **Not kept:** the career history, the remarks on politeness to models, model version
  details, and the startup-strategy advice.
- **Relevance to SYNAPSE: 2.** It bears on how the implementation sessions use the agent.

### SRC-SPC-05 - doordash_ai_intelligence_report_v2_FINAL.md

- **Pin:** `7228a8bf8c12`, 24,735 bytes. Type: report.
- **Origin:** a fireside chat at South Park Commons with Tony Xu, co-founder and chief executive
  of DoorDash, hosted by Aditya Agarwal.
- **Thesis:** The lasting value lies in coordinating physical goods, not in winning digital
  attention, and that work is learned by doing it. A local-delivery company stays ahead by
  measuring what its customers feel and by grinding at its core business.
- **Worth keeping:**
  - Analysing the database suggests sending the nearest courier to a restaurant. Anyone who has
    made a delivery knows the courier then waits if the food is not ready. Doing the job shows
    what the data hides. For SYNAPSE: the twin does model picking and packing, and R-54 asks
    where its timing came from and whether the router knows when an order will be ready. The
    founders delivered every early order themselves; the chief executive still answers support
    every day; every employee makes deliveries several times a year: INS-035, INS-031.
  - Run the business on measures only a customer would care about (speed, accuracy, cost,
    selection, support), not on revenue or user counts: INS-056.
  - Debates are settled by shipping something or calling a customer, not by the best memo or
    the most senior title: T-005.
  - Once a year leadership asks what it would do differently if starting the company today:
    INS-030, Q-06.
  - The edges teach most: new sign-ups (he deletes his own account to repeat onboarding) and the
    most active couriers' detailed feedback. Quality drops sharply a short drive out of the city
    centre: INS-003.
  - Write down the one or two problems that matter now and ignore the rest: INS-045, INS-017.
  - Thin margins mean a mistake in physical operations is paid for directly, unlike in
    software: INS-009.
  - The test of whether ambition has become delusion is whether customers keep using the
    product, not whether investors agree: T-013.
- **Not kept:** the biography, the bits-and-atoms framing of competitors, the data-partnership
  speculation, parenting and the investor history.
- **Relevance to SYNAPSE: 2.** The nearest domain in the folder: local delivery of goods.

### SRC-SPC-06 - granola-intelligence-report.md

- **Pin:** `e34452125a6d`, 18,650 bytes. Type: report.
- **Origin:** a South Park Commons conversation with Sam Stephenson, co-founder and designer of
  Granola, a meeting-notes application.
- **Thesis:** Meeting notes were chosen as one painful, recurring moment, a way in before
  anything broader. The product found its form when the assistance stopped competing for the
  user's attention during the meeting.
- **Worth keeping:**
  - A general-purpose tool can be pleasant and still matter to nobody. The remedy is one
    painful moment in someone's day: INS-045, T-013.
  - Six months went into real-time suggestions during the meeting, which overloaded people.
    Writing the notes in one pass after the meeting was what worked. For SYNAPSE: an operator
    is better served by a review at a natural point than by a stream of interruptions: INS-038.
  - Someone who signs up hours before their next meeting meets an empty screen and leaves, so a
    simulated meeting was built into onboarding to show the value at once. SYNAPSE's
    traffic generator does the same for an idle console.
  - The month before any code went on interviewing people about their working day: INS-018.
- **Not kept:** the brand redesign, the London hiring story, the year-end summary feature, the
  privacy model and the competitive outlook.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-07 - luma_ai_beyond_tools_intelligence_report.md

- **Pin:** `0ccf98d550d4`, 21,471 bytes. Type: report.
- **Origin:** Amit Jain, who founded and runs Luma AI, a maker of video and multimodal models,
  in conversation at South Park Commons.
- **Thesis:** Customers want the finished job, not a tool that does one step and leaves them to
  assemble the rest. The company trains capabilities into its models from data gathered by
  people embedded with customers, and keeps the software around the model thin.
- **Worth keeping:**
  - A tool that writes copy or makes one clip leaves the customer with the orchestration and the
    clean-up, and customers turned it down. They pay for the finished work: INS-056.
  - The internet holds finished work but not how it was made: the drafts, the edits and the
    reasons. People embedded with customers record that process, and it is what the models
    learn from: INS-032.
  - When the model cannot do something, the company gathers data for a few weeks and trains it
    in, rather than spending months on wrapper code: T-006.
  - A generated video is not interesting because it was generated, and the consumer video app
    lost its users within days. Likewise a stock decision is worth no more for having been
    debated by eight agents: INS-001.
  - A world model is defined by whether it understands cause and effect in its world, not by
    speed or rendering: INS-031.
  - For text-only work a small model often does better than a large one: INS-021.
- **Not kept:** the hardware history, the market sizing, the film and advertising examples and
  the company's architecture claims.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-08 - mercor-brendan-foody-intelligence-report.md

- **Pin:** `8ce0b0568401`, 40,208 bytes. Type: report.
- **Origin:** an interview at South Park Commons with Brendan Foody, chief executive of Mercor,
  which supplies expert-written training tasks and evaluations to model builders. A different
  talk from SRC-SEQAI-14.
- **Thesis:** Once an evaluation exists, reinforcement learning climbs it fast, so the scarce
  thing is evaluations of work that has no automatic checker. What teaches a model is graded
  feedback on attempts, not passive records of past work.
- **Worth keeping:**
  - A task is worth building only if it is realistic and hard. One that every model passes is
    worth nothing; one with a low pass rate leaves room to improve and lasts longer: INS-033,
    INS-053.
  - Reading a company's chat logs and documents does not teach a model, any more than reading
    past slide decks teaches a person. Feedback on what was done well and badly does: INS-032.
  - A thumbs-up or thumbs-down from users shows where failures cluster, which tells you where to
    build evaluations, but it is too coarse to train on: INS-032, R-28.
  - Models exploit loose checks, for example by deleting a codebase so that the tests pass.
    Such exploits appear only once hundreds of attempts are run, so a scoring rule is tested at
    that scale before it is trusted: INS-041, INS-044.
  - Application companies publish benchmarks of their own domain, and the model builders then
    spend far more climbing them: INS-043.
  - Narrow, high-volume tasks move to smaller post-trained models for cost and latency: INS-021.
  - Physical tasks are slow to roll out, costly to reset and intolerant of errors, so simulation
    is the bridge: INS-049, INS-009.
  - He cites a researcher's parallel: language models went from imitation to reinforcement
    learning, and robotics is going from imitating demonstrations to reinforcement learning in
    simulation. For SYNAPSE, a learned policy starts by imitating the tuned rule: INS-057.
- **Not kept:** the company's growth figures, the claim that models now differ only by their
  data, the hiring history, the timelines for automation, and the interpersonal-work claim.
- **Relevance to SYNAPSE: 2.** It bears on the proof harness and on the later training
  sessions.

### SRC-SPC-09 - rasmus_andersson_spc_interview_intelligence_report.md

- **Pin:** `cfe38b9a7554`, 19,415 bytes. Type: report.
- **Origin:** a South Park Commons interview with Rasmus Andersson, a designer and engineer who
  worked at Spotify, Facebook and Figma and drew the Inter typeface.
- **Thesis:** Two decades of building for scale have made software complex and fragile. The new
  tools could raise its quality, but most companies are using them for volume.
- **Worth keeping:**
  - Ordinary software decays fast: he discards a project left untouched for two weeks. A
    typeface hardly decays at all. Everything a system carries has to be maintained to stay
    alive: T-002, INS-019.
  - The new tools multiply whatever a team already does. Most turn them to more features while
    basic interactions stay broken; few keep the same pace and ship much better work: INS-048.
  - The company looked fast from outside because, inside, people explored slowly in parallel,
    some spending a year on one feature and throwing most prototypes away: INS-048.
  - Thousands of hours on projects that were never released had no effect at all, while an
    app built in under an hour at a hackathon reached millions: T-013.
- **Not kept:** the company's product, the typeface history, the advice on founding and the
  personal philosophy.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-10 - sridhar-ramaswamy-founders-superpower.md

- **Pin:** `680dad744c7b`, 20,365 bytes. Type: report.
- **Origin:** a South Park Commons conversation with Sridhar Ramaswamy, chief executive of
  Snowflake, formerly head of Google's advertising business and co-founder of the search
  startup Neeva.
- **Thesis:** Great founders reduce a problem to the few constraints that decide it, and argue
  over it hard without making it personal. Now that code is cheap, value lies in time to value,
  in loops that improve with use, and in connection to the operations outside.
- **Worth keeping:**
  - His search company began from a complaint (search funded by advertising is broken) with no
    concrete picture of how searching itself would change. He calls the belief that clarity
    would appear through building a form of arrogance. The SYNAPSE equivalent is "agentic
    supply chain" as a premise with no named change to anyone's working day: T-013, INS-018.
  - He believed users cared about privacy and about advertisements; they chose convenience.
    What people say they value and what they do differ: INS-018, Q-01.
  - South Park Commons judges a founder partly on whether the next six to eighteen months reduce
    to one or two points of leverage: INS-017, INS-045.
  - His company turns instructions written in plain language into compiled code, for cost and
    speed: INS-040.
  - Customers fear being tied to one model provider and want to switch freely: INS-007.
  - An agent left running on a frontier model cost about 600 dollars a day until it was moved
    to an open model: INS-021.
  - What lasts: getting the customer to the outcome fast, loops that improve with use, and a
    connection to operations in the physical world: INS-039, INS-032.
- **Not kept:** the biography, the remarks on Microsoft and Google, the advice on working
  hours and the advertising rule.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-11 - the-future-of-forward-deployed-engineering.md

- **Pin:** `8e697f13f395`, 21,245 bytes. Type: report.
- **Origin:** a South Park Commons panel on forward-deployed engineering with engineers from
  Ramp, Nominal, Dataland and OpenAI.
- **Thesis:** Forward-deployed engineers sit with the customer, deliver a working result, and
  carry the repeated patterns back into the product. The role grew as models made more kinds of
  work addressable by software, each needing someone who knows the domain.
- **Worth keeping:**
  - The usual chain from customer to account manager to product manager to engineer loses the
    point at each step. One engineer with the whole context does better: INS-018, INS-035.
  - A field build is designed so that it can be pulled into the product for every customer. One
    company spent years with field engineers rejecting a central platform and writing separate
    code for each client, and the fix was to staff the role with people who can tell a one-off
    from a general need: INS-045.
  - Field engineers turn the failures they see into evaluation sets and examples for the model
    team, and the next model handles them. A voice agent that at first could not read back a
    phone number correctly was iterated against that test: INS-032, INS-033, R-35.
  - Coding agents now do the routine plumbing, so the people spend their time on the domain
    problem: INS-048.
- **Not kept:** the services-revenue economics, staffing ratios, hiring profiles and the
  contact details printed in the file.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-12 - tldraw-steve-ruiz-infinite-canvas-report.md

- **Pin:** `a702d0022285`, 30,278 bytes. Type: report.
- **Origin:** a South Park Commons fireside chat with Steve Ruiz, founder of tldraw, which sells
  a software kit for building infinite-canvas applications.
- **Thesis:** The canvas, built for people working together, also suits people working with
  agents. Design has moved from static mock-ups to people who ship code, and what a customer
  pays for is depth that a quick copy lacks.
- **Worth keeping:**
  - A model can copy the surface of his product in minutes. Companies still pay for it because
    of the depth on hard cases (performance, geometry, accessibility) that their own teams would
    skip. For SYNAPSE the comparable depth is the stressed cases the harness covers, if it is
    the product: INS-053, T-004.
  - The working material of development (debugging recordings, design problems) is published
    as it is made, and that built his reputation: INS-034.
- **Not kept:** the licensing model, the agent canvas experiment, the hiring profile, the
  remarks on design teams and taste, and the biography.
- **Relevance to SYNAPSE: 1.**

### SRC-SPC-13 - trae-stephens-startup-ideas-intelligence-report.md

- **Pin:** `75f4fa0d1117`, 41,549 bytes. Type: report.
- **Origin:** a South Park Commons conversation with Trae Stephens, a partner at Founders Fund
  and co-founder of the defence company Anduril, who earlier sold software to government at
  Palantir.
- **Thesis:** Lasting companies come from a practitioner who cannot stop thinking about one
  problem, not from searching for an idea. A hard technology is built in stages, starting with
  something that can be deployed in months.
- **Worth keeping:**
  - The pitch promised autonomous aircraft and submarines. The first product was a sensor tower
    built in six months from bought parts; it became a long-term government programme within
    two years and funded the rest. A rocket company built a one-engine rocket first: INS-045.
  - Bought camera mounts were made for a person steering with a joystick, who corrects small
    drift without noticing. Driven by software from radar tracks, an error of about one degree
    grew with each move until tracking failed, and the company had to build its own mount.
    Automating a loop removes the person who was quietly correcting it: INS-058.
  - Build a part yourself only when bought parts cannot meet what the software needs: INS-019.
  - The early software company took about five years to reach ten million dollars of revenue.
    Retired generals, lobbyists and partnerships with large contractors all failed to sell it;
    working directly with the users did: INS-018, INS-035.
- **Not kept:** the venture-fund arithmetic, valuations, the defence-market structure and the
  founding story.
- **Relevance to SYNAPSE: 1.** The camera-mount lesson is the one direct use.

## What the folder says as a whole

1. **Judge the work by what reaches the customer, and learn the job by doing it.** The delivery
   company runs on measures a customer feels; customers pay for the finished job, not a step
   of it; founders and staff do the front-line work themselves (cards 05, 07, 02, 11, 13).
2. **Start with one piece that can be deployed in months, then expand** (13, 06, 05, 10).
3. **What teaches is graded feedback on attempts, not a pile of records** (08, 07, 11).
4. **Keep the code as the source of truth, and delete what newer tools have made unnecessary**
   (03, 04, 09).
5. **Before automating a loop, find what people were correcting in it without saying so** (13).

No figure from this folder carries a SYNAPSE decision, so no web check was made. The one
number used in a landing, the twin's 8-minute pick-and-pack mean, comes from the repository
(measured, `digital_twin/config.py`).

**Where the folder agrees with SYNAPSE as built:** the proof harness is the kind of hard,
scored task card 08 calls scarce; the traffic generator answers the empty first screen that
card 06 describes; outcome scoring records a graded result for each decision, which is the
feedback cards 07 and 08 say teaches; and the twin models picking and packing, not only travel
(measured).

**Where it argues against SYNAPSE:**

- The console's first screen leads with the system's own state, and the store's fill rate sits
  on another surface (measured; INS-056).
- The twin's world state holds one stock number per item, so the case where the record and the
  shelf disagree, and a loop that trusts the record never reorders, has never been tested
  (measured; INS-058, R-55).
- The evaluation apparatus answers whether the system beats a rule, and nothing yet answers
  whether anyone wants it (T-019). The folder adds four sources to T-013, including a founder
  who calls starting from a premise with no picture of the changed product a form of arrogance.

## Self-review record

- Three entries were added. INS-056 and INS-058 are stated by their sources and landed with
  measured repository facts. INS-057 is sparked rather than stated: the source offers a
  parallel about how models are trained, not advice for SYNAPSE, so it is graded own.
- Not made an entry: "customers want the finished job, not a step of it" (card 07) was merged
  into INS-056 rather than kept apart, and the delivery company's view of its catalogue as a
  data asset was left out as strategy that changes nothing here.
- Card 05's routing point was rewritten after measuring. I had assumed the twin modelled only
  travel time; it models picking and packing too, so R-54 now asks where its 8-minute figure
  came from and whether the router knows when an order is ready.
- Card 02 first tied the history of the domain to INS-055. The link was a stretch and was
  removed; the point stays with R-51.
- Next is YC GUIDE. Three of its files duplicate YC AI GUIDE and are cross-referenced, not
  read again.
