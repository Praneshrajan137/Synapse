# Digest: YC GUIDE

Corpus folder `C:\Documentation\YC GUIDE`. Read in full on 2026-11-15: 26 files, 582,568 bytes,
of which 23 were read here.

## What this folder is

Model-written reports on Y Combinator talks, fireside chats and founder interviews. Speakers
are taken as verified under the operator's decision of 2026-11-13.

Three files were not read again. `building-physical-ai-for-the-industrial-world.md`,
`model-ml-finance-ai-intelligence-report.md` and `solve-intelligence-ai-patent-law.md` are
byte-identical to files digested in folder 6 (YC AI GUIDE).

## Cards

### SRC-YCG-01 - alexandr-wang-yc-talk-intelligence-report.md

- **Pin:** `b20b319e29bc`, 20,017 bytes. Type: report.
- **Origin:** a Y Combinator fireside chat with Alexandr Wang, founder of Scale AI, now leading
  frontier AI at Meta.
- **Thesis:** Models are no longer the bottleneck; spreading what they can already do through
  companies and institutions is. With agents, a small company can take on large incumbents,
  and the scarce thing becomes a clear view of what to build.
- **Worth keeping:**
  - Even if models stopped improving, decades of change would follow as what exists today is
    put to use. The constraint is getting it into the work: INS-039.
  - An agent loop with a clear goal and the right measure can out-produce a large team; without
    the measure it cannot. For SYNAPSE that makes the uplift objective the thing every agent
    loop in the coming sessions will climb, so it has to be right first: INS-033, INS-044.
  - He spends tokens freely on loops that reason, correct and verify: T-008.
- **Not kept:** the biography, the lab's models and pricing, and the advice on conviction.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-02 - banking-ai-agents-intelligence-report.md

- **Pin:** `08ce299a0d37`, 25,741 bytes. Type: report.
- **Origin:** a Y Combinator interview series with six companies: agents for bank back offices,
  for consumer-goods brands' finance and supply planning, a visual agent builder, a monitoring
  layer for agents, training environments for knowledge work, and a voice-agent platform.
- **Thesis:** Agents that do back-office work win by sitting on top of the systems of record
  companies already run, inside a deterministic harness. As models grow more capable they are
  given wider permissions, so the cost of a mistake grows and so does the need for checks.
- **Worth keeping:**
  - Replacing a bank's core system or a company's ERP takes years and carries great risk, so the
    agent works as a layer above it: INS-039.
  - More capable agents get write access and keys, so a mistake costs more, not less: INS-009.
  - The banking agents run inside a deterministic harness that keeps every action compliant:
    INS-008.
  - One team dropped a product a month before its launch because customers would not miss it,
    then found millions of people paying mortgages by phone and moved into a servicer's back
    office until the system was live: INS-045, INS-035, T-013.
  - The consumer-goods company automates cash application, trade-spend accounting, demand
    planning and raw-material buying. Its buyers judge it against the labour it replaces, not
    as software, and an agent reconciles transactions so small that no person ever reviewed
    them. For SYNAPSE: replenishment is bought as a planner's work, and its gain may sit in the
    slow items nobody watches: INS-018, INS-003.
  - A model judge on a 1 to 10 per cent sample doubles token cost and finds only failure modes
    already known. The monitoring company scans every trace for new patterns and simulates each
    change in CI before it ships: INS-011, INS-037.
  - The training-environment company builds layered checkers so an agent cannot hard-code an
    answer without deriving it, and holds that environments must grow harder as models do:
    INS-041, INS-053.
  - Agents adopted where people already work, such as their chat tool: INS-039.
- **Not kept:** funding rounds, pricing models, pivot histories, the voice company's story and
  the enterprise security checklist.
- **Relevance to SYNAPSE: 2.** The nearest folder document to the domain: an agent doing
  supply planning on top of existing systems.

### SRC-YCG-03 - blake-scholl-supersonic-jet-analysis.md

- **Pin:** `9c7eea027824`, 20,351 bytes. Type: report.
- **Origin:** a Y Combinator talk by Blake Scholl, founder of Boom Supersonic, on building a
  supersonic demonstrator with about fifty people.
- **Thesis:** A small team built a supersonic jet by replacing the spreadsheets passed between
  engineering disciplines with integrated software that simulates the whole aircraft, and by
  bringing slow suppliers in-house.
- **Worth keeping:**
  - Disciplines that hand each other spreadsheets iterate in months; one parametric model of the
    whole aircraft explores a design in minutes. He calls spreadsheet engineering software with
    no integration and no tests: INS-049.
  - An in-house machine shop turns a design into a part within a day, and an own test stand
    removes the wait for a booked facility. Iteration speed was bought deliberately: INS-013.
  - His rule for young engineers: try what has never been done, but if someone has done
    something like it, call them first and hear them out. For SYNAPSE the people to call are
    the inventory-control literature and practitioners: R-51, R-12.
  - The engine core is sold now as a ground power turbine, which brings revenue and operating
    data years before the airliner: INS-045.
- **Not kept:** the history of aviation speed, the regulatory story, the manufacturing
  politics and the hiring advice.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-04 - building-physical-ai-for-the-industrial-world.md

- **Pin:** `d40d5149251f`, 41,837 bytes. Type: report.
- **Byte-identical to SRC-YCAI-03,** digested in folder 6 and not read again. Its entries are
  recorded under that card.
- **Relevance to SYNAPSE: 3.**

### SRC-YCG-05 - claude_code_intelligence_report.md

- **Pin:** `6fe095f7b3f9`, 20,397 bytes. Type: report.
- **Origin:** a Y Combinator talk by Boris Cherny, creator of Claude Code at Anthropic.
- **Thesis:** Newer models do better with less instruction. The team deletes prompt text by
  ablation, gives the model a hard goal with a way to check its own work, and lets it find the
  path.
- **Worth keeping:**
  - More than 80 per cent of the tool's system prompt was cut for a new model, and a mode that
    strips every prompt sometimes did better. Every six months, delete the system prompt, the
    project instructions file, skills and hooks, run real tasks, and add back only what repeated
    failures call for, since every line costs tokens on every turn. For SYNAPSE this is the test
    for `CLAUDE.md`: INS-014, INS-030, Q-04.
  - The skill is to give the model a task that seems slightly too hard and a way to verify its
    work as it goes. Two rewrites ran for 11 and 15 days, one against a full test suite and one
    comparing screenshots of the old and new applications: INS-012, INS-013.
  - Experienced engineers fail by over-specifying how; state the goal, the limits and the exit
    criteria: T-011.
  - Scheduled agent runs each day delete dead code, remove finished feature flags, add missing
    tests and merge near-duplicate abstractions: INS-030.
- **Not kept:** the benchmark scores, the defences against prompt injection, the drawing demo
  and the remarks on computer science education.
- **Relevance to SYNAPSE: 2.** It bears directly on `CLAUDE.md` and on how the implementation
  sessions brief the agent.

### SRC-YCG-06 - durable-startups-intelligence-report.md

- **Pin:** `277ad53ed510`, 21,848 bytes. Type: report.
- **Origin:** a Y Combinator talk and question session with partners Tom Blomfield and Mathilde
  Collin.
- **Thesis:** Now that software can be generated, code is not what makes a company last. Ask
  where the hard part is (regulation, hardware, a difficult sale) and learn fast by testing
  against the real world.
- **Worth keeping:**
  - Writing a lot of software used to be the hard part and no longer is. For SYNAPSE the eight
    agents could be regenerated; the hard parts are the domain, the connection to a retailer's
    systems and the proof: T-004, INS-039.
  - Startups are empirical: state a hypothesis, test it against the world within two weeks, and
    every two weeks overwhelm the single largest bottleneck: T-015, INS-045.
  - Never hand talking to customers to an agent: INS-018.
  - Before deploying agents, make the company's own records legible, and start with one narrow
    loop: INS-045.
  - One partner writes her own documents so as not to hand her thinking to a model: INS-029.
  - Model prices fall roughly tenfold a year, so do not optimise token cost early: T-008.
- **Not kept:** the hub and ecosystem remarks, the co-founder advice, the venture-capital
  points and the pivot framework.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-07 - emergent-video-intelligence-report.md

- **Pin:** `9fe78c8244cb`, 20,168 bytes. Type: report.
- **Origin:** a Y Combinator interview in India with Mukund Jha, co-founder of the
  quick-commerce company Dunzo and now of Emergent, which generates full-stack applications.
- **Thesis:** After Dunzo, six months of unpressured experiments with models led him to build
  for where models were going, and to take users all the way to working software rather than
  demonstrations.
- **Worth keeping:**
  - The one operator of Indian quick commerce in the corpus so far. Dunzo grew to millions of
    orders a month in Bangalore; the founders delivered orders themselves at night, and a
    dedicated unit watched every order as it ran: INS-035, INS-038.
  - His own diagnosis of what went wrong: the dark stores worked very well, but the company
    spread into about ten parallel lines of business and lost focus, and after a large round it
    believed it was too big to fail. For SYNAPSE: keep to the one workflow that works: INS-045,
    Q-07.
  - When his team was stuck, he pointed it at one hard public benchmark for coding agents; the
    work done to top it became the company's core: INS-045.
  - Competing tools were good at starting an application and bad at finishing one. Users want
    software that works, with a real back end, not a demo: INS-056.
  - He skipped problems the next model would solve, such as parsing its output, and rewrote the
    system three times in nine months as models changed: INS-014.
- **Not kept:** the growth figures, the career history, the marketing funnel and the advice
  on ambition.
- **Relevance to SYNAPSE: 2.** A founder's view from inside quick commerce.

### SRC-YCG-08 - jeff-dean-1-percent-rule-ai.md

- **Pin:** `0af0288ad2ce`, 19,865 bytes. Type: report.
- **Origin:** a Y Combinator fireside talk with Jeff Dean, chief scientist at Google.
- **Thesis:** Progress now comes from systems around the model: context, specialised hardware
  and automated experiment loops. Build where general models fail almost completely, and
  specify precisely what you want.
- **Worth keeping:**
  - If a general model already gets a problem right a fifth of the time, it will soon solve it;
    build where it scores near zero, which signals private data or domain logic it lacks. Stock
    decisions in a twin are of that kind, which is one more reason the core decision is not a
    language model's: INS-008.
  - With agents writing the code, specifying what you want matters more. Translating code
    between languages works because the old code and its tests are an exact specification:
    INS-017, INS-012.
  - Agents drift after some tens of steps. Keep them on well-lit paths with skills and
    constraints, and search several attempts in parallel with an evaluator pruning the bad
    ones: INS-025, INS-023.
  - He writes down ten predictions each year and checks them a year later to calibrate his
    judgment: INS-002.
  - A network trained to imitate an expensive quantum-chemistry simulator ran some 300,000
    times faster. A learned stand-in for the twin would multiply simulation throughput, at the
    risk that a learner exploits the stand-in's errors: INS-049, INS-041.
  - The first special-purpose chip began with arithmetic on the back of an envelope: if every
    user spoke to the phone three minutes a day, the server fleet would have to double:
    INS-016.
- **Not kept:** the hardware energy figures, the history of search, the rejected paper and the
  career advice.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-09 - jensen_huang_nvidia_mindset.md

- **Pin:** `2d6cff60bf2f`, 21,348 bytes. Type: report.
- **Origin:** Jensen Huang, founder and chief executive of NVIDIA, interviewed by Garry Tan at
  Y Combinator's Startup School.
- **Thesis:** A technology company lasts by confronting reality when its starting technology
  turns out wrong, and by accelerating whole domains rather than selling chips. In the agent
  era the human skill is systems thinking.
- **Worth keeping:**
  - The company's founding rendering approach was wrong. He said so to the customer funding the
    chip and changed course, and the honesty kept the company alive. SYNAPSE's E5 result is the
    same kind of moment: T-001.
  - The largest gap for agents in production is fine control: a person must be able to change
    one word, pixel or layer of the output without the rest being regenerated: INS-038, R-28.
  - Physical AI follows three steps: capture the real world into a simulation, simulate with
    physics, then train in simulation and transfer to the machine: INS-031, INS-049.
- **Not kept:** the company history, the management philosophy, the remarks on jobs and the
  robotics market forecast.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-10 - legora-story-max-junestrand-analysis.md

- **Pin:** `a75d3b40b266`, 16,802 bytes. Type: report.
- **Origin:** a talk at Y Combinator's Startup School by Max Junestrand, chief executive of the
  legal AI company the file calls Legora, with a question session.
- **Thesis:** Founders with no legal background outgrew the field by learning faster than
  anyone else, staying close to lawyers, and stopping sales to fix reliability when one failure
  would have cost a customer for good.
- **Worth keeping:**
  - With no lawyer among them, the founders paid lawyers their hourly rate to explain their work
    over lunch, then moved into the offices of a large firm: INS-018, INS-035.
  - Asked which kind of lawyer they served, the founder replied that he did not know there were
    kinds, and the application was turned down on the spot. The equivalent question for
    SYNAPSE is which operator in a dark store it serves, and it has no answer yet: Q-01.
  - In law you are punished when things go wrong, so the company froze all sales for six months
    to rebuild for reliability: T-015.
  - Instead of training its own legal model, it bet that general models would improve and
    built the orchestration and an evaluation suite over three years. The suite chooses which
    model to use by quality and cost, and was later published: T-006, INS-007, INS-043.
  - A single written product manifesto replaced feature voting: INS-017.
- **Not kept:** the funding story, the culture and hiring remarks, and the marketing campaign.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-11 - max-hodak-knowledge-extraction.md

- **Pin:** `cb225e4d7301`, 18,201 bytes. Type: report.
- **Origin:** a talk at Y Combinator's Startup School by Max Hodak, chief executive of Science
  Corp and former president of Neuralink.
- **Thesis:** Startups rarely fail because the science fails; they fail because operations
  slow them down. The rate of iteration decides, and infrastructure sets it.
- **Worth keeping:**
  - A company that learns one thing a week outruns one that learns one a month, and the speed
    comes from infrastructure, not effort: INS-049, INS-013.
  - When materials are bought in bulk, each experiment looks free. Showing its real cost, such
    as the price of one foundry run, changes how people spend. For SYNAPSE the units are the
    cost of a replicate and of an hour of cloud time: INS-049, R-30, Q-02.
  - Hiring tasks are built so that a candidate may use AI freely, with no ceiling, and are
    scored on two or three numbers against the best results so far: INS-033.
  - Action produces information; a stalled organisation is moved by doing something: T-015.
- **Not kept:** the purchasing and hiring pipelines, the peer-review algorithm, the custom
  internal software and the fundraising rule.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-12 - model-ml-finance-ai-intelligence-report.md

- **Pin:** `0ff6f0e2cb82`, 39,547 bytes. Type: report.
- **Byte-identical to SRC-YCAI-05,** digested in folder 6 and not read again. Its entries are
  recorded under that card.
- **Relevance to SYNAPSE: 2.**

### SRC-YCG-13 - patrick_collison_ai_lean_startup.md

- **Pin:** `d977f27e91f0`, 19,394 bytes. Type: report.
- **Origin:** Patrick Collison, co-founder and chief executive of Stripe, interviewed by Harj
  Taggar at Y Combinator's Startup School in 2024.
- **Thesis:** Knowledge held in your own head is still faster than asking a model. Hunting for a
  small niche and growing outward is now crowded, so founders should start from more
  ambitious, less correlated positions.
- **Worth keeping:**
  - Stripe took almost two years to launch publicly, but had its first live production user
    within two months and built each feature against that user's real needs. That reconciles
    the two sides of T-015: hold the public launch, not the first real user.
  - He writes his own essays and keeps the fundamentals in his own head, because thinking with
    them is faster than retrieving them: INS-029.
  - Founders avoid tedious problems such as payments, compliance and logistics, and those are
    where lasting businesses form: T-004.
- **Not kept:** the startup-creation data, the remarks on dropping out and on monopoly, and the
  enterprise-buying claims.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-14 - paul-graham-founders-analysis.md

- **Pin:** `157253ae31ed`, 17,436 bytes. Type: report.
- **Origin:** a conversation with Paul Graham, co-founder of Y Combinator, in the company's
  original offices.
- **Thesis:** The fundamentals of startups have not changed with the technology: speed, fear of
  failure as the daily motive, and founders who get what they want.
- **Worth keeping:**
  - The most reliable predictor he knows is how fast a team ships: T-015.
  - Models arrived as human-like reasoners that were unreliable on simple facts, good at hard
    problems and wrong about a restaurant's opening hours. Where the answer must be exact, a
    model's output needs a check: INS-008.
  - For AI companies, token bills have replaced salaries as the main cost, while the price of
    inference keeps falling fast: T-008.
- **Not kept:** the history of Y Combinator, the founder psychology and the remarks on
  ambition and credentials.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-15 - peter_steinberger_fun_is_velocity.md

- **Pin:** `1998a70e5952`, 16,772 bytes. Type: report.
- **Origin:** a Y Combinator talk and question session with Peter Steinberger, creator of the
  open-source agent OpenClaw.
- **Thesis:** A personal tool became a very large open-source project, and then slowed under
  configuration options, security alarms and dependence on one model provider. It recovered
  when its author went back to building for himself.
- **Worth keeping:**
  - The project was built around one provider's model, and when the provider changed its terms
    at a day's notice the project stalled. In his words, the business model of your dependency
    becomes yours. For SYNAPSE that argues for one seam behind every model call, and it applies
    to the cloud trial credit too: INS-007, Q-02.
  - Accepting every request produced about 9,500 configuration options, at which point testing
    every combination was impossible and things broke often: INS-019, INS-030.
  - Once he was building for every user, he no longer used the tool himself. In the weeks he
    enjoyed the work, the product got visibly better: INS-035.
  - He no longer reads all generated code. He reviews by risk: light for interface code,
    careful for what touches the file system: INS-009, INS-012.
  - The first user is the builder; the next twenty are friends: INS-018.
- **Not kept:** the project's history and naming, the press episode, the non-profit, and the
  remarks on personal brand.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-16 - recursion-ai-scaling-analysis.md

- **Pin:** `eeaad2a6eb7d`, 17,396 bytes. Type: report.
- **Origin:** a Y Combinator technical discussion of two recent model designs that loop over
  their own hidden state many times per answer.
- **Thesis:** A transformer does a fixed amount of computation per step, which some problems
  cannot fit. Very small models that iterate in their hidden state beat far larger ones on
  puzzles such as Sudoku, mazes and the ARC benchmark.
- **Worth keeping:**
  - An independent ablation of the first design found that one of its loops gave most of the
    gain. The follow-up dropped most of the rest, used a quarter of the parameters, and scored
    higher. As the host puts it, the second paper deletes three quarters of the first and keeps
    what works. That is the ablation SYNAPSE's consensus has not had: INS-030, R-16.
  - For a narrow, structured problem a model of a few million parameters, trained for it, beat
    general models: INS-021.
- **Not kept:** the architecture details, training tricks and the history of recurrent
  networks.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-17 - running_cisco_like_a_startup_intelligence_report.md

- **Pin:** `c78ba8a0807a`, 23,171 bytes. Type: report.
- **Origin:** a Y Combinator interview with Jeetu Patel, president and chief product officer of
  Cisco.
- **Thesis:** A large company can move like a startup if its leaders own the whole business, and
  it can adopt AI by making use mandatory first and efficient later.
- **Worth keeping:**
  - The limit on deploying agents is moving from compute to trust: delegating to an agent that
    can be manipulated or misread its task needs identities for non-human actors, guardrails
    while it runs, and testing by attack: INS-009, INS-027.
- **Not kept:** the networking business and its figures, the organisation design, the adoption
  mandate and the biography.
- **Relevance to SYNAPSE: 0.** One point, already well covered.

### SRC-YCG-18 - self-improving-company-ai-intelligence-report.md

- **Pin:** `ba162f6f939b`, 15,249 bytes. Type: report.
- **Origin:** a Y Combinator talk on running a company as a set of loops that improve
  themselves, illustrated with Y Combinator's own internal tools.
- **Thesis:** Adding an assistant to an existing hierarchy only speeds it up a little. A company
  can instead be built from loops that sense, act within a policy, check quality and learn from
  their own failures.
- **Worth keeping:**
  - The loop has five layers: sensors (tickets, email, telemetry), a policy (limits and when to
    ask a person), tools (deterministic interfaces), a quality gate (checks and human approval
    for risky actions), and learning. This is SYNAPSE's loop after ADR-052 almost part for part:
    the sensor loop, the guardrails, world actions, the confidence gate, and meta-learning.
  - A monitoring agent reads the questions the internal assistant failed to answer, works out
    why, writes the fix, has it reviewed by another agent and deploys it overnight. For SYNAPSE,
    a decision scored `diverged` should likewise become a case the harness tests: INS-037,
    R-35.
  - If something was not recorded, it did not happen as far as the AI is concerned. Record it
    and distil it into context: INS-011, INS-032.
  - Interfaces and internal tools are disposable and regenerated as models improve; the data
    and the know-how are the asset. For SYNAPSE the console is the disposable part, and the
    decision records, the proof and the domain knowledge are what to keep: T-004.
- **Not kept:** the history of hierarchy, the revenue-per-employee claims, the remarks on
  middle management and the case for recording all staff communication.
- **Relevance to SYNAPSE: 2.** It describes SYNAPSE's own loop from outside.

### SRC-YCG-19 - solve-intelligence-ai-patent-law.md

- **Pin:** `d4860ad43e4c`, 40,461 bytes. Type: report.
- **Byte-identical to SRC-YCAI-07,** digested in folder 6 and not read again. Its entries are
  recorded under that card.
- **Relevance to SYNAPSE: 2.**

### SRC-YCG-20 - state_of_startups_2026_report.md

- **Pin:** `c4980d53e92a`, 16,622 bytes. Type: report.
- **Origin:** an episode of Y Combinator's podcast in which Garry Tan, Diana Hu and Jared
  Friedman review the year's batches.
- **Thesis:** Hardware and physical companies have grown fast because generated code removed
  software headcount as their limit, and companies that do a whole job are replacing tools a
  person has to operate.
- **Worth keeping:**
  - Companies that do the whole job, such as clinical intake or medical billing, grew from a
    tenth to over a quarter of a batch, while tools that need a person to drive them lose
    ground: INS-056.
  - A system of record either becomes the place where people do their work, or agents take its
    data elsewhere: INS-039.
  - Model builders are said to spend about a billion dollars a year on training data and
    environments for reinforcement learning, and more than a dozen young companies sell them.
    A scenario set with a scorer is a kind of asset people buy: T-004.
- **Not kept:** the batch statistics, the hardware and defence examples, the compute market and
  the founder demographics.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-21 - supabase-journey-knowledge-report.md

- **Pin:** `468af7e64d1d`, 16,658 bytes. Type: report.
- **Origin:** a Y Combinator interview with Paul Copplestone, co-founder and chief executive of
  the database company Supabase.
- **Thesis:** An open-source database platform grew by building on an established database and
  obsessing over how quickly a developer gets to the first useful result.
- **Worth keeping:**
  - The team measured the seconds from sign-up to a first row in the database, against more
    than eight minutes on a large cloud provider, and drove it down to about five seconds. For
    SYNAPSE the comparable figure is the time from a fresh clone to a first decision on screen,
    which matters for every agent session and for anyone trying it: R-57, R-08, INS-013.
  - It built on a decades-old database that nobody owns, for the trust and the ecosystem that
    come with it, rather than writing a new one: INS-019.
  - Interest arrived when the description changed from what it was built on to what it replaced
    for the user: INS-018.
  - Code generators now make the build easy; the harder, more durable problem is operating the
    system afterwards: T-002.
  - Years of written decisions became a record that agents can now search: INS-011.
- **Not kept:** the funding and growth figures, the open-source business model, the remote
  culture and the agent-platform product.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-22 - the_founder_playbook_intelligence_report.md

- **Pin:** `f88481546394`, 15,571 bytes. Type: report.
- **Origin:** a Y Combinator conversation between Mark Pincus, founder of Zynga, and Garry Tan.
- **Thesis:** Consumer software looks uninvestable now, as it did after past crashes, and that
  is when the next consumer giants start. Build from proven mechanics, improve them, and test
  one new idea at a time.
- **Worth keeping:**
  - His frame: copy what is proven, make it better (cheaper, faster, easier), and keep one new
    idea isolated so it can be tested, expecting most new ideas to fail. For SYNAPSE the proven
    part is the tuned replenishment rule, and the consensus is the one new idea, to be tested
    in isolation against it: INS-047.
  - When a product truly works, the signal is unmistakable and nobody needs a metric to see it:
    T-013.
- **Not kept:** the history of social networks, the management advice, the forecasts of token
  costs and the consumer thesis.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-23 - the-ai-pilled-ceo-intelligence-report.md

- **Pin:** `ea0b5abbab9a`, 27,785 bytes. Type: report.
- **Origin:** an episode of Y Combinator's podcast with Pedro Franceschi, co-founder and chief
  executive of Brex.
- **Thesis:** Agents should be given real tools and freedom, with safety enforced at the network
  boundary. Processes should be redesigned around what is now cheap rather than automated as
  they are.
- **Worth keeping:**
  - An over-constrained harness cripples the model. Brex lets its agents act and puts a proxy
    at their network boundary: rules derived from recorded traffic pass the routine 98 per
    cent of requests at once, and a model judges the rest. For SYNAPSE the equivalent boundary
    is the world action, checked against what the store's own history makes normal: T-020,
    INS-027, R-42.
  - When a person overrides an agent or reports a fault, the case becomes a test automatically,
    and a background agent works on the fix: INS-032, R-35.
  - The great products started with a tiny surface, such as a few lines of code or one form.
    Generated code tempts teams to build large surfaces, and good founders resist it. SYNAPSE's
    console has many surfaces: R-39, INS-048.
  - Models are trained on what has been written down; what customers need but do not say is
    the founder's job to find: INS-018.
  - Token spend is attributed to each product, workflow and person, to see what it buys:
    INS-049.
- **Not kept:** the electricity analogy, the adoption tiers, the advice to the chief executive,
  the redesign of customer checks and the adoption statistics.
- **Relevance to SYNAPSE: 2.**

### SRC-YCG-24 - video-intelligence-report (1).md

- **Pin:** `c8e8844297d1`, 16,072 bytes. Type: report.
- **Origin:** a Y Combinator interview with Alex Lebrun, a repeat founder now building world
  models, by partner Nicolas Dessaigne. Not a copy of any other file named like it.
- **Thesis:** Language models handle symbols, not the physical world; models trained on sensory
  data will handle continuous, noisy, long-horizon problems. A startup's one advantage over a
  large company is its willingness to take risk.
- **Worth keeping:**
  - Language models are hard to beat on discrete symbolic work and weak on continuous, noisy,
    long-horizon control. A stock decision is of the second kind, which is why its core belongs
    to forecasting and control methods, not a language model: INS-008.
  - His advice in hindsight: choose a very narrow problem and be very ambitious inside it. Great
    ambition across a wide field is not credible: INS-045.
- **Not kept:** the founding history, the world-model architecture claims, the risk-aversion
  stories and the remarks on raising very large rounds.
- **Relevance to SYNAPSE: 1.**

### SRC-YCG-25 - waymo_dmitri_dolgov_analysis.md

- **Pin:** `6d70843507c1`, 19,813 bytes. Type: report.
- **Origin:** a talk at Y Combinator's Startup School by Dmitri Dolgov, co-chief executive of
  Waymo.
- **Thesis:** In physical AI a working demonstration is about one per cent of the work. The rest
  is climbing the reliability ladder, proved with closed-loop simulation and a critic, and the
  evaluation framework is the lasting asset.
- **Worth keeping:**
  - The car drove ten long routes with no intervention after eighteen months; reaching
    commercial service took another fifteen years. Each further nine of reliability costs
    roughly ten times the last and needs different engineering, such as redundancy and
    fallbacks. Teams that overspend on the demonstration starve the long tail: INS-053, T-015.
  - Decide quantitatively what is good enough before building; without that you are iterating
    on a demo. SYNAPSE has no such number for its autonomous decisions: INS-033, INS-044, Q-08.
  - Open-loop testing (predicting the next step) is not enough; only closed-loop simulation, in
    which the agent's actions change the world, can validate it. Rare events are generated in
    simulation: INS-046, INS-053.
  - Three systems share one foundation: the agent, the simulator it practises in, and the critic
    that judges it. Real miles keep the simulator honest. For SYNAPSE these are the agents, the
    twin and the objective, and the last two need checking as much as the first: INS-031,
    INS-044.
  - Pure end-to-end models are hard to validate. Keeping explicit intermediate representations
    lets an onboard check verify each output before it reaches the wheels: INS-008.
  - A new technique is adopted only if it performs better and also makes the system simpler:
    INS-030, INS-019.
  - Publishing audited safety data built a trust that no copied model can: INS-034, INS-043.
- **Not kept:** the sensor debate, the operating figures, the model architecture and the
  hardware cost remarks.
- **Relevance to SYNAPSE: 3.** The clearest statement in the corpus of how an agent is proved
  in simulation before it acts in the world.

### SRC-YCG-26 - yc-ai-playbook-intelligence-report.md

- **Pin:** `e2d89dfd29dd`, 24,862 bytes. Type: report.
- **Origin:** Garry Tan and partner Pete Koomen describe how Y Combinator runs its own operations
  on an internal agent harness.
- **Thesis:** An organisation gets most from agents when all its data sits in one queryable
  place, its tools are registered for agents to use, and nightly loops improve the agents'
  skills from their own transcripts.
- **Worth keeping:**
  - All of Y Combinator's records sit in one Postgres database, and agents were given read-only
    SQL. People then asked many more questions, and harder ones. For SYNAPSE, the decision and
    outcome tables are where session 2 can sort the losses by cause: R-40, INS-011.
  - A skill checks the registry of 350 tools for duplicates and overlaps, so agents are not
    confused by two tools doing one job: INS-028.
  - Each night an agent reads the day's conversations with the internal agents, finds errors
    and missing context, and rewrites the skills: INS-032, INS-037.
  - Most software puts the model in a small box inside deterministic code; they argue the agent
    should wrap deterministic tools instead: T-020.
- **Not kept:** the finance origin story, the culture of public transcripts, the token budgets,
  the rewritten personal application and the closing argument about centralised AI.
- **Relevance to SYNAPSE: 1.**

## What the folder says as a whole

1. **Prove an agent in a closed loop, against a target set in advance.** A demonstration is a
   small part of the work; decide in numbers what is good enough, test in simulation where the
   agent's actions change the world, and check the simulator and the critic as hard as the
   agent (cards 25, 01, 11).
2. **Keep the check at the boundary where an action leaves the system,** and let the reasoning
   inside it be free (02, 23, 25, against 05 and 26; T-020).
3. **Turn every failure and every override into a test, automatically** (18, 23, 26).
4. **Delete instructions and parts that a newer model or a simpler design makes unnecessary,
   and adopt a new technique only if it also simplifies** (05, 15, 16, 25).
5. **Copy the proven method, improve it, and test one new idea in isolation; stay narrow**
   (22, 24, 07, 02).

No figure from this folder carries a SYNAPSE decision, so no web check was made. One repository
fact was measured for Q-08: the four SLO files set completion times per tier and nothing about
decision quality.

**Where the folder agrees with SYNAPSE as built:** the five-layer loop of card 18 is SYNAPSE's
loop after ADR-052; the twin is a closed-loop simulator, which card 25 says is the only kind
that validates an agent; and guardrails sit on each world action, which is the boundary T-020
settles on.

**Where it argues against SYNAPSE:**

- SYNAPSE has no numerical target for the quality of autonomous decisions, so no measurement can
  say autonomy has been earned (card 25; Q-08).
- The only quick-commerce operator in the corpus says dark stores worked and his company failed
  by spreading across ten lines of business (card 07). SYNAPSE runs eight agents across
  demand, inventory, routing, pricing, freshness, suppliers and disruption; Q-07 asks whether
  replenishment comes first.
- Large surfaces are what generated code makes easy and good products avoid (card 23); the
  console is large (R-39).

## Self-review record

- No new ledger entry. The folder is the most heavily corroborating so far: 38 existing entries
  gained sources, chiefly INS-008, INS-045 and INS-049. A candidate entry on stating a
  reliability target first became Q-08 instead, because the answer is the operator's.
- T-020 was added because three documents argue for free agents and three for a deterministic
  harness, and the folder itself shows where they meet.
- Card 24 has a generic file name and was checked against the similarly named card in folder
  3. The hashes differ and so do the talks.
- Card 25 was rated 3 against the folder's run of 1s: it is the corpus's clearest account of
  proving an agent in simulation, which is SYNAPSE's central problem.
- The venture, culture and hiring material, about half of the folder, was read and left out.
