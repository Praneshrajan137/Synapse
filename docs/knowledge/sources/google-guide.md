# Digest: GOOGLE GUIDE

Corpus folder `C:\Documentation\GOOGLE GUIDE`. Read in full on 2026-11-15: 3 files, 62,294 bytes.

## What this folder is

Three model-written reports on Google-hosted conversations: the head of Android on the next
release, two practitioners on directing Claude Code by intent on Google Cloud, and the head of
frontier AI at Google DeepMind on building towards general intelligence. Speakers are taken as
verified under the operator's decision of 2026-11-13.

## Cards

### SRC-GOOG-01 - android-17-intelligence-report.md

- **Pin:** `99042bd6d29e`, 20,747 bytes. Type: report.
- **Origin:** a Google podcast episode in which Logan Kilpatrick interviews Sameer Samat,
  president of Android.
- **Thesis:** Android is moving from an operating system the user micromanages to one that takes
  an intent and carries it out. Features are presented by what they do for the user, and
  automated actions run in a contained space that stops before anything irreversible.
- **Worth keeping:**
  - An agent operating another app runs inside an isolated window it cannot leave, and it
    stops before completing a payment so that the person authorises it: INS-009, INS-027.
  - A dedicated place on screen shows each long-running agent task, its progress and its
    questions, so the person can see it and step in: INS-038.
  - Features were adopted when described by the benefit, not when labelled as AI. The
    equivalent for SYNAPSE is to describe it by what it does for a store's stock: INS-018.
  - The on-device scam check applies rules set by the banks themselves: INS-008.
  - Agents take over transactional software, such as ordering, and not the software people use
    for its own sake. Replenishment is transactional: INS-039.
- **Not kept:** the keyboard, widgets, form filling, the car demonstration and the hardware
  strategy.
- **Relevance to SYNAPSE: 1.**

### SRC-GOOG-02 - intent-driven-development-report.md

- **Pin:** `fe1953d8b7ea`, 22,750 bytes. Type: report.
- **Origin:** an episode of Google Cloud's Agent Factory with a developer advocate at Anthropic
  and a practitioner who maintains a widely used collection of Claude Code tips.
- **Thesis:** Developers now say what they want and leave how to the agent, spending most of
  their effort on reviewing and steering. Two tools make that practical: a classifier that
  decides which actions need a person, and workflows that the agent writes down as code that can
  be run again.
- **Worth keeping:**
  - Approving every action trains people to approve without reading, and turning approval off
    is dangerous. A classifier lets safe actions through and stops only the risky ones:
    INS-009, INS-038.
  - A multi-step agent job is generated as a script with fixed phases (build, integrate, review,
    verify), which can be read, versioned and rerun. Ad-hoc sub-agents behave differently each
    time: INS-040, INS-025, INS-026.
  - Ask the broad architectural question, such as which library and why, before asking for
    code: INS-017.
  - Models write more code than a task needs, so only what is necessary is committed. Effort
    moves from writing to reviewing: INS-012, INS-048.
  - Changes go up as draft pull requests for a person to review before merging: INS-012.
  - The agent ran browser tests on its own work without being asked, and bots fix failing
    builds and answer review comments until the checks pass: INS-013.
- **Not kept:** the cloud setup, voice input, the game demonstration and the uses outside
  software.
- **Relevance to SYNAPSE: 2.** It bears on how the ten implementation sessions are run.

### SRC-GOOG-03 - koray-kavukcuoglu-agi-frontier-analysis.md

- **Pin:** `8a851c2b7844`, 18,797 bytes. Type: report.
- **Origin:** a Google podcast episode in which Logan Kilpatrick interviews Koray Kavukcuoglu,
  head of frontier AI at Google DeepMind.
- **Thesis:** Google DeepMind's only priority is the frontier, which has moved to agents that
  write software. There is no single test for general intelligence, and progress comes in
  steps: a breakthrough, then long incremental work.
- **Worth keeping:**
  - The lab's method from its first project onwards: rally a team around one hard, measurable
    challenge. Atari came first: INS-045.
  - No benchmark settles the question, and targets move as capabilities grow: INS-033.
- **Not kept:** the model roadmap, release cadence, hardware history and the lab's competitive
  position.
- **Relevance to SYNAPSE: 1.**

## What the folder says as a whole

1. **Decide which actions need a person by their risk, not one rule for all.** Asking every time
   produces blind approval; never asking is unsafe (cards 01, 02).
2. **Write a repeated agent workflow down as code with fixed phases,** and keep reviewing as the
   main work (02).
3. **Contain what an agent can touch, and stop it before anything irreversible** (01).
4. **One hard, measurable target concentrates a team** (03).

No figure from this folder carries a SYNAPSE decision, so no web check was made. All three
conversations are hosted by Google, and two are about Google's own products.

**Where the folder agrees with SYNAPSE as built:** confidence-gated escalation to a person;
guardrails in front of actions; a typed record of what an agent proposed.

**Where it argues against SYNAPSE:** nothing new. It repeats INS-009 and INS-038 on how autonomy
is granted, and supplies the workflow-as-code practice for the implementation sessions.

## Self-review record

- No entry was added from three documents. Every point worth keeping already had an entry, and
  a new one would have repeated it.
- Card 02 is the only one with direct use, for how the implementation sessions are run, and
  its two practices were filed under INS-009 and INS-040.
- The product announcements and the frontier-lab positioning were read and left out.
