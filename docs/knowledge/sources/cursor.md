# Digest: Cursor

Corpus folder `C:\Documentation\Cursor`. Read in full on 2026-11-14: 2 files, 44,208 bytes.

## What this folder is

Two model-written reports from Cursor's events: a panel of engineering leaders from three large
companies, and a nine-talk conference. Speakers are taken as verified under the operator's
decision of 2026-11-13. No figure here is load-bearing for a SYNAPSE decision, so no web check
was made.

## Cards

### SRC-CURSOR-01 - ai-coding-adoption-analysis.md

- **Pin:** `89ce468679d0`, 11,495 bytes. Type: report.
- **Origin:** a Cursor panel with engineering leaders from Intuit, DoorDash and Atlassian on
  adopting AI coding across the whole delivery cycle.
- **Thesis:** Writing code was never most of the job, and it is now a small part: the panel puts
  it at 30%, 15% and about 5% of an engineer's time. The gains come from the rest of the cycle,
  and they are counted in work finished, not in hours saved.
- **Worth keeping:**
  - The queue is now people reviewing machine-written code. Review is moving from reading
    lines to judging intent and watching a demonstration: INS-012, INS-034.
  - Count completed backlog and the time from idea to release. Hours saved do not turn into
    output by themselves: INS-020.
  - One company requires a working prototype before a specification may be debated: INS-030.
  - One company gives a small team a whole roadmap and a month where nine were once planned.
    The deadline is a deliberate forcing function, and it works because scope gives: INS-016,
    T-011.
  - New practices are proven on small teams before release to everyone: INS-022.
- **Not kept:** adoption percentages, the internal tool names, and the merger story.
- **Relevance to SYNAPSE: 2.** DoorDash is a delivery company, but nothing here is about
  delivery decisions; the weight is on how the implementation sessions are run and measured.

### SRC-CURSOR-02 - compile26_intelligence_report.md

- **Pin:** `0aeb85286573`, 32,713 bytes. Type: report.
- **Origin:** Cursor's Compile 26 conference: nine talks, among them Sam Lambert of PlanetScale
  on infrastructure for agents, Claire Vo of LaunchDarkly on product work, Ryo Lu of Cursor on
  interface design, and Ben Geist of Ramp on the efficiency of token spending.
- **Thesis:** Engineering capacity is no longer scarce, so the limits move elsewhere: to
  infrastructure that keeps non-deterministic agents safe, to interfaces that keep people as
  authors, and to knowing what is worth building.
- **Worth keeping:**
  - Infrastructure built for agents offers undo as a primitive, blocks destructive changes
    whatever the agent asks, and throttles background agents under load. Small, sharp,
    composable primitives let capability grow without the risk growing: INS-009, INS-027.
  - An interface that offers only accept or reject turns the person into an approver. One that
    shows the plan and the steps, and lets the person step in at any point, keeps them an
    author: INS-038, INS-034.
  - With code abundant, the limits are commercial value, changing what users actually do, a
    first-principles view of what to build, and distribution. Planning artifacts that existed
    to protect scarce engineering time are now overhead: INS-018, INS-030, T-013.
  - Returns to spending more tokens fall off logarithmically. Structured prior information
    does more than extra compute, and sub-agents started from one shared compressed context
    spend far less rediscovering it: INS-015, INS-010.
  - Agents running on a developer's machine are limited by that machine and collide in one
    workspace: INS-013.
- **Not kept:** the vendor's product announcements, the memory-compaction research, the talk on
  notation, and the talk on the vagueness of the word "AI". None changes a decision in the
  planned sessions.
- **Relevance to SYNAPSE: 3.** The infrastructure and interface talks bear directly on how
  SYNAPSE grants autonomy and how its console treats the operator.

## What the folder says as a whole

1. Coding is a small and shrinking share of the work. Review, verification and deciding what to
   build are where time goes.
2. Autonomy is made safe by the infrastructure underneath: undo, hard blocks on destructive
   actions, and backpressure.
3. The person should stay an author, not an approver.
4. Value is measured in finished work that someone uses, not in volume.

**Where the folder agrees with SYNAPSE as built:** the console already shows a decision's
anatomy and lets the operator steer and override (read, `CLAUDE.md`), which is the legible,
steerable interface the design talk asks for; brownout is a form of backpressure.

**Where it argues against SYNAPSE:** it restates, more bluntly than any folder so far, that
building is no longer the hard part and value is. That is now recorded as T-013. It also
sharpens INS-009: undo is a property of the infrastructure, and SYNAPSE's actions have no named
undo.

## Self-review record

- Nine talks produced one new ledger entry and a set of corroborations. Five talks were left
  out as changing no decision.
- The deliberate use of a tight deadline was drafted as a tension with INS-016 and folded into
  it, because the two agree once scope is allowed to give.
- T-013 records a point first met in folder 1, where it was filed only as an insight and a
  question. It belongs with the tensions.
