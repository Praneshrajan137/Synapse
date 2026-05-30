# SENSORIUM — The Operator's Interface to an Autonomous Mind

> A first-principles design for the most extraordinary interface this domain can carry.
> Codename **SENSORIUM** — the sum of an organism's perception. This is the operator's
> sensory cortex onto the SYNAPSE collective mind.
>
> **Status:** design north-star (vision + specification). Supersedes nothing yet; the
> current shipping interface is *Atlas Console v1.1*. This document derives where Atlas
> must go and why, grounded in the actual substance of the system.
>
> **Author mandate:** experience design at the frontier — UI, UX, AUX (agentic UX),
> interaction, motion, and color science — derived from first principles, not transplanted
> from dashboards built for slower, dumber systems.

---

## 0. How to read this

This is not a re-skin. It is a derivation. §1 establishes *what SYNAPSE actually is* (the
substance the interface must express). §2 states the first principles that fall out of that
substance. §3 is the thesis — the single organizing idea. §4–§9 are the architecture: the
surfaces, the sensory system (color, type, motion, sound), the signature interactions, and
the honesty contract. §10 maps Atlas v1.1 → SENSORIUM concretely, including the real seams
found in the audit. §11 is a phased, invariant-respecting roadmap.

Every claim is anchored to a file or an invariant. Nothing here breaks `CLAUDE.md` rules:
the 8 agent→hue assignments stay frozen (INV-CLR-012), color stays token-only (INV-CLR-009),
KV-cache discipline (I-13) is untouched, and the honesty/substance mandate (C33, ADR-040/041)
is *amplified*, not undermined.

---

## 1. The investigation — what we are designing for

### 1.1 The substance (what the machine is)

SYNAPSE is not a dashboard's worth of metrics. It is an **autonomous organism** that makes
supply-chain decisions for 10-minute quick-commerce, and the human is *not in the critical
path* for the overwhelming majority of them.

- **Eight specialist minds**, each a genuinely distinct ML core (not CRUD services):
  conformal-interval demand forecasting (`demand_prophet`), attention-RL sub-100ms routing
  (`routing_navigator`), hierarchical federated MARL inventory (`inventory_sentinel`),
  perishables/cold-chain markdown (`freshness_guardian`), MADDPG pricing with causal
  elasticity (`pricing_oracle`), anomaly-ensemble + LLM-reasoning disruption defence
  (`disruption_shield`), Bayesian+GNN supplier trust (`supplier_trust`), and carbon/waste/ESG
  (`sustainability_agent`).
- **A five-phase consensus engine** (`orchestrator/consensus/protocol.py`): Phase 1 *Collect*
  (A2A fan-out to agents) → Phase 2 *Debate* (LLM-mediated, Tier 3–4 only, ≤3 rounds) →
  Phase 3 *Arbitrate* (NSGA-II Pareto optimisation over **8 objectives**, knee-point
  selection, `orchestrator/consensus/pareto.py`) → Phase 4 *Execute* → Phase 5 *Learn*
  (meta-RL re-weights the objectives). The 8 objectives map **one-to-one** to the 8 agents
  (`_AGENT_TO_OBJECTIVE`). The Pareto front is a genuinely **8-dimensional** object.
- **Four latency tiers** (`tier_router.py`): Tier 1 RL-only ≤100 ms (target ≥80 % of all
  traffic, I-10) → Tier 2 `phi3:mini` ≤500 ms → Tier 3 `deepseek-r1:14b` ≤15 s → Tier 4
  `llama3.3:70b` + Monte-Carlo ≤120 s. **The system thinks across three orders of magnitude
  of time.**
- **Confidence-gated human-in-the-loop** (I-5, `orchestrator/hitl/escalation.py`): below
  threshold (or on guardrail violation) the decision escalates and the operator gets a
  **300-second countdown** to approve / reject / modify, with a configurable timeout
  fallback (defer / execute-tier-1 / execute-last-known-good).
- **A digital twin** with a live **KL-divergence fidelity metric** (I-12) — re-sync fires
  above 0.1 — plus Monte-Carlo and what-if simulation. This is a *projection* engine.
- **An append-only, hash-chained audit memory** (I-4, I-14, ADR-033): every decision,
  override, and steering change is immutable and cryptographically chained.
- **A live firehose** (`api/routers/firehose.py`): one WebSocket multiplexing eight channels
  — `decision`, `disruption`, `routing`, `metric`, `twin`, `demand`, `freshness`, `pricing`
  — server-sequenced for dedupe on reconnect, city-filterable.
- **Operator levers, all audit-logged**: override a decision (`decisions.py`), steer the
  Pareto objective weights (cost / time / sustainability / fairness) and per-tier confidence
  thresholds (`steering.py`).

### 1.2 The interface today (Atlas Console v1.1)

Atlas is already sophisticated — React 18 + Vite + TS with a frontier toolkit: deck.gl +
MapLibre + pmtiles, three.js + d3-force-3d, visx + recharts, framer-motion, Radix, TanStack,
a Zod-typed client, and a firehose multiplex into bounded Zustand ring buffers. It ships eight
role-gated surfaces — Mission Control, Override Cockpit, Decision Theater, Agent Council, Twin
Lab, Steering, Audit Vault, Demo Theater — and bespoke viz: a `ProposalConstellation` (8
agents in a radial formation), a 2-D `ParetoFrontier`, a `ReasoningTimeline` (5-phase
stepper), and `ConfidenceGauge`/`ConfidenceChip`.

**This is a strong v1. SENSORIUM is its v2 thesis** — not a teardown but an elevation from
*dashboard* to *instrument*.

### 1.3 The chromatic foundation (genuinely world-class — and one real seam)

`design-system/color/` is a spec-first OKLCH token system governed by 14 `INV-CLR`
invariants. Its **Orthogonal Encoding Principle** is the most important asset we have:

| Data type | SYNAPSE concept | OKLCH axis | Invariant |
|---|---|---|---|
| Nominal (categorical) | Agent identity (8) | **Hue** (8 frozen hues, staggered in L for CVD survival) | INV-CLR-004/005/012 |
| Ordinal (ranked) | Decision tier 1→4 | **Lightness** (strictly monotonic) | INV-CLR-006 |
| Continuous [0,1] | Confidence (gated 0.70 / 0.80) | **Diverging OKLab scale** (red→amber→green→teal, stops anchored *exactly* at the I-5 gates) | INV-CLR-007 |

Plus dual contrast (WCAG 2.1 AA **and** APCA, tiered 75/60/45 by emphasis), CVD-proofing
(deuter/protan/trit), deterministic gamut-mapped builds, and the principle that **every hue
is earned** (PR-CLR-002) and **color is never the sole signal** (PR-CLR-011).

**The seam (a real finding):** there are *two parallel token layers*. The canonical
`design-system/color/dist/` emits perceptually-rigorous OKLCH (`--color-*`, a continuous
`confidenceColor()` interpolator, `agentRgb()`/`tierRgb()` helpers for deck.gl/three). But
`frontend/src/styles/tokens.css` keeps a *separate* `--syn-*` set with **space-separated sRGB
approximations** of tiers and confidence and hand-copied agent OKLCH. The frontend has not
fully adopted its own canonical system. SENSORIUM unifies on the canonical layer — this is
both a craft win and a correctness fix (the sRGB confidence ramp is *not* the gate-anchored
diverging scale the spec defines).

---

## 2. First principles

Everything below is derived from §1, not imported from dashboard convention.

**P1 — The job is trust calibration, not control.** The human is *on* the loop, not *in*
it. The system acts autonomously and the operator supervises. The entire design exists to
align the operator's *perceived* reliability with the system's *actual* reliability — to
defeat both **overtrust** (rubber-stamping the machine) and **undertrust** (over-intervening,
which destroys the value of autonomy). This reframes the interface from "show me the data" to
"help me know when to believe the machine and when to step in."

**P2 — Two clocks. Never pretend the human can watch the fast one.** Tier-1 decisions
resolve in 100 ms; ≥80 % of all traffic. No human can or should track them individually.
Tier-4 takes up to two minutes; a human *can* follow that. Therefore the interface has two
fundamentally different time regimes: the **ambient** (aggregate flow, perceived as *climate*
— rhythm, pulse, color-temperature, texture) and the **deliberate** (the rare slow or
escalated decision, perceived as *theater* — a legible argument the human can reason about).
The cardinal sin of most ops dashboards is forcing item-level legibility onto a stream no
human can read. SENSORIUM renders the firehose as **weather** and the escalation as a
**conversation**.

**P3 — Quiet by default. Color is rationed signal, not décor.** (ISA-101 / High-Performance
HMI, and it *agrees* with our own PR-CLR-002 "every hue is earned.") When the organism is
healthy and autonomous, the screen is calm, near-monochrome, and breathing slowly. The eight
gorgeous agent hues, the tier lightness ramp, the confidence diverging scale — these **fire
only when they carry meaning**: a conflict in consensus, a confidence gate trip, a disruption,
a twin divergence. Rationing the palette makes it pre-attentively powerful. A colorful screen
at rest is a screen that has nothing left to say when something breaks.

**P4 — One ontology, many lenses.** (Palantir Foundry's load-bearing idea + Endsley's SA
model.) The Neo4j supply graph — stores, warehouses, suppliers, SKUs, riders, zones, all
city-scoped — *is* the ontology. The geo-map (deck.gl), the supply graph (force layout), the
consensus trace, and the timeline are all **typed projections of the same objects**, and the
operator pivots between lenses *without ever losing the object in focus*. Depth follows
Endsley's three levels of situation awareness: **Perception** (the live field) →
**Comprehension** (why — the consensus argument) → **Projection** (what next — the digital
twin). Our Tier-4 Monte-Carlo *is literally a Level-3 SA engine*; surface its projections as
first-class, not buried.

**P5 — Confidence is rendered into the pixels, not appended as a number.** A low-confidence
recommendation must *look* uncertain. We use the confidence axis of the color system as a
**Value-Suppressing Uncertainty Palette** (Correll/Moritz/Heer, CHI 2018): as confidence
drops below the I-5 gate, chroma and fidelity drain out — the object literally desaturates
toward the quiet grayscale base. Conformal prediction intervals become **quantile dotplots**
("14 of 20 scenarios land here"); demand-forecast distributions become **Hypothetical Outcome
Plots**; Monte-Carlo Tier-4 outcomes become animated draws that accrete into a band. **The
confidence gate is the exact line where color drains away** — perception, not arithmetic.

**P6 — The instrument must never feel slower than the mind it watches.** (Latency as a
design material — Linear.) A system that decides in 100 ms cannot be supervised through a
laggy UI. Local-first, optimistic with rollback, keyboard-first command grammar, springs that
are interruptible. Perceived latency of the supervisor's tools must be below human perception.

**P7 — Honesty is the substrate of trust (the substance mandate, made visible).** The
codebase fought hard to kill synthetic confidence (`confidence = 0.85` everywhere disabled
I-5) and made degradation a first-class, tested state (C33, ADR-040/041; `Provenance` with
`degraded`/`feature_source`/`confidence_basis`). The interface must honor this: when an agent
is running on a fallback model, when features are stale, when the twin has diverged, when the
firehose is on heartbeat-only because Kafka is unreachable — **the UI shows it plainly.** A UI
that fakes a healthy green when the system is degraded is the single fastest way to destroy
the trust calibration of P1. Degraded is a *designed* state, rendered with the same care as
healthy.

---

## 3. The thesis — The Quiet Cortex

> **SENSORIUM is a calm instrument that makes an autonomous mind perceptible —
> quiet when the machine is sure, vivid and conversational exactly where the machine
> reaches the edge of its competence.**

The unifying image, true to the name *SYNAPSE*, is a **cortex**: eight specialist regions
(the agents, each a frozen hue), signals firing across the network (decisions on the
firehose), and moments of integrated thought (consensus). But the metaphor only earns its
place by doing functional work:

- The **resting state** is a slow-breathing, near-monochrome field whose *rhythm* is the
  system's decision cadence and whose *temperature* is its aggregate confidence. You read the
  health of the organism the way you read someone's breathing — pre-attentively, peripherally,
  without effort. (P2, P3.)
- **Stress localizes and surfaces.** A conflict, an escalation, a disruption, a divergence —
  the relevant region floods with its earned color, draws motion, and rises to the foreground.
  Color and motion are the organism's pain signals. (P3, P5.)
- **Diving is continuous, not navigational.** From any firing signal you fall *into* the
  decision — the same object, re-projected through the comprehension lens (the consensus
  argument) and the projection lens (the twin). You never "navigate to a page"; you change
  the depth of attention on the object already in focus. (P4.)

Three postures the operator moves between, each a regime of P2's two clocks:

1. **Ambient** — watching the climate. (Perception / SA-L1.)
2. **Inquiry** — interrogating one decision's argument, replaying it, comparing the Pareto
   tradeoffs. (Comprehension / SA-L2.)
3. **Intervention** — the 300-second threshold: a confidence-gated escalation that demands a
   human judgment, with the agent's full reasoning state inherited intact. (Action.)

---

## 4. The architecture of surfaces

SENSORIUM keeps Atlas's eight surfaces but re-derives each against the principles. The
spine is no longer a flat nav bar of equals; it is an **attention gradient** from ambient to
deliberate.

### 4.1 THE CORTEX — ambient field (reimagines *Mission Control*) · SA-L1

The home posture. Not a grid of KPI tiles — a **single living field**.

- **The Pulse.** A slow ambient waveform/ring at the periphery whose beat *is* the
  decisions-per-second from the `decision` channel, and whose **color temperature is the
  rolling aggregate confidence** (drawn from the same gate-anchored OKLab scale, P5). Healthy
  autonomy = a calm, cool, regular pulse you stop consciously seeing — until it changes. Tier
  mix renders as the *texture* of the beat (Tier-1 fast ticks vs the rare heavy Tier-4 swell).
  This is the firehose-as-weather (P2). `tabular-nums` counters for anyone who wants the
  literal rate.
- **The Living Map** (deck.gl v9.1, GPU aggregation). Dark-store / rider / demand field over
  MapLibre + pmtiles. At rest: grayscale stores, faint demand `HexagonLayer`
  (`gpuAggregation: true`). In motion: `TripsLayer` for in-flight 10-minute deliveries with
  trailing fade; `ArcLayer` for warehouse→store and inter-zone transfers. Color appears
  **only** on abnormality — a store turns its disruption hue, a route reddens on a freshness
  violation (P3). City switch flushes buffers (existing FE-INV-016).
- **The Council strip.** Eight slim presence indicators, one per agent, in frozen hue — but
  **desaturated to near-gray at rest** and re-chroma'd only when that agent is active in a
  live decision or degraded. Health, p99 latency, and calibration coverage ride along
  (`/api/v1/agents`). A degraded agent (P7) shows a muted, hatched, explicitly-labelled state
  — never a silent green.
- **The Disruption band.** Dormant and invisible until `disruption_shield` fires; then it
  takes the top of the field with alert-level (1–10) → severity, the affected nodes lit on the
  map, and a one-line *next action* (ISA-18.2: every alarm carries a defined response).

The Cortex answers P1's resting question — *should I be paying attention right now?* — with a
glance, from across the room.

### 4.2 THE TRIBUNAL — consensus inspector (reimagines *Decision Theater / Detail*) · SA-L2

The crown jewel. The 5-phase consensus is the system's *reasoning*; render it as a **legible
argument**, borrowing the agent-observability trace idiom (LangSmith node-by-node state diffs +
time-travel; Arize trajectory analysis).

- **The Phase Spine.** Collect → Debate → Arbitrate → Execute → Learn as a horizontal
  trace with **time-travel scrubbing** (`lib/replay.ts` already exists). Fast-path Tier-1/2
  decisions collapse the spine to Collect → Execute (honest to the code's
  `_fast_path`). Tier-3/4 expand Debate (with the actual LLM round-by-round content from the
  append-only context messages) and Arbitrate.
- **The Proposal Constellation, elevated.** Keep the radial 8-agent formation, but each node
  is its agent's hue, sized by `utility_score`, and **the edges are the conflict graph** —
  `_detect_conflicts` made visible. During Debate, edges pulse as positions move; on
  convergence they settle. This is the moment of integrated thought, animated honestly.
- **The Pareto surface, done right.** The front is 8-dimensional — do **not** dump it. Use
  **parallel coordinates** (one axis per objective, each axis tinted its agent's hue), draw
  every non-dominated candidate as a faint polyline, and draw the **selected knee-point**
  bold. Annotate *why it won*: the weighted distance-to-ideal from `pareto.py`, with the
  current meta-RL objective weights overlaid (the same weights the operator steers in §4.6).
  A "ghost" polyline shows what a different weighting would have chosen — making steering's
  consequence legible before the operator touches it.
- **Confidence rendered (P5).** The decision's confidence sets the *fidelity* of the whole
  Tribunal: a high-confidence decision is crisp and saturated; a gate-tripping one is rendered
  with VSUP suppression and an explicit escalation marker exactly at the 0.70/0.80 line.
- **One click to memory and to regression.** Every decision links to its immutable audit row
  (hash-chain verified) and — borrowing Braintrust's trace→eval loop — an operator can mark a
  decision "this was wrong" to seed a counterfactual replay case.

### 4.3 THE THRESHOLD — intervention (reimagines *Override Cockpit*) · Action

Where trust calibration becomes a decision. The confidence gate has tripped; the machine has
**handed the human full context** (the AUX "context-preserving handoff" pattern) and is
running a **300-second countdown** (`escalation.py` timeout) toward its configured fallback.

- **The countdown is the spine of the surface** — a calm, honest timer (tabular-nums,
  reduced-motion-safe) showing not just time-left but *what happens at zero* (defer /
  execute-tier-1 / execute-last-known-good). The operator must always know the cost of *not*
  acting. This is the antidote to both overtrust (the machine isn't waiting forever) and
  undertrust (you don't have to babysit; there's a safe fallback).
- **Inherited reasoning, not a cold alert.** The full Tribunal view for the escalated
  decision is *right here* — the proposals, the conflict, the guardrail violations that
  triggered escalation, the Pareto knee and its runner-up. The human reasons with everything
  the machine knew.
- **Three verbs, keyboard-first** (existing A/R/M shortcuts, J/K queue nav): **Approve**,
  **Reject**, **Modify**. Approve is optimistic with rollback (P6) — the audit-row-first commit
  order (`decisions.py`, FE-INV-003) is preserved so the immutable record is written *before*
  the orchestrator is notified. Modify opens an action editor constrained by the same guardrails
  the agents obey (e.g. essential-SKU price cap ≤1.3×, I-6) — the human cannot violate an
  invariant the machine can't.
- **Calibration feedback.** Over time, the Threshold shows the operator their *own* override
  hit-rate vs the system's — am I overriding decisions that turn out fine (undertrust), or
  rubber-stamping ones I should have caught (overtrust)? This closes the P1 loop explicitly.

### 4.4 THE PROJECTION — digital twin (reimagines *Twin Lab*) · SA-L3

The future, made first-class. The twin is the system's imagination.

- **Divergence as a drift trace** (not just a gauge). The KL-divergence (I-12) over time, with
  the 0.1 re-sync threshold marked; when the twin and reality disagree, *that is itself a
  signal worth attention* (Arize drift idiom).
- **What-if as HOPs / Monte-Carlo draws.** Tier-4 Monte-Carlo scenarios (`monte_carlo.py`,
  `what_if.py`) render as animated hypothetical outcomes that accrete into a distribution —
  the operator *feels* the spread of futures rather than reading a p95 number.
- **The supply graph in 3-D**, but GPU-scaled (force layout; the existing
  `react-force-graph-3d` is fine for the demo network, with a documented upgrade path to a
  GPU-shader graph if node counts grow). Communities (zones) cluster naturally; the same
  ontology objects as the map (P4), one pivot away.

### 4.5 THE COUNCIL — the eight minds (reimagines *Agent Council*) · engineer depth

Each agent is a *character* with a distinct ML soul, not a row in a health table. A per-agent
view speaks that agent's native uncertainty language: conformal calibration curves for
`demand_prophet`, elasticity for `pricing_oracle`, Bayesian posteriors for `supplier_trust`,
anomaly-ensemble breakdown for `disruption_shield`. Latency percentiles and SLA status ride
along, but the hero is *how this mind reasons and how sure it is*. Degradation (P7) is shown
per-agent with its `Provenance` (`model_version`, `feature_source`, `degraded`).

### 4.6 THE WILL — steering (reimagines *Steering*) · ops

Steering the Pareto objective weights (cost / time / sustainability / fairness) and per-tier
confidence thresholds is **adjusting the values of the organism**. Render it as such: the four
weights as a balance the operator tilts, with a **live preview** that re-runs the knee-point
selection on a recent decision so the consequence is visible *before* commit (ties to the
Tribunal ghost polyline). Audit-first (WS-5 / FE-INV-033): POST to `/api/v1/steering` before
the local mutation, revert on failure. Tier thresholds visibly move the line at which color
drains in the Cortex (P5) — the operator sees they are literally tuning the machine's
willingness to ask for help.

### 4.7 THE MEMORY — audit vault · compliance

The immutable, hash-chained record (I-4, ADR-033). Read-only, queryable *in the moment of
doubt* (the AUX accountability pillar). Make the **chain itself visible** — a verified
tamper-evident lineage, with the daily anchor (E-S9-03) shown — so an auditor perceives
integrity, not just reads rows. Zero PII (the redaction processor, E-S9-13).

---

## 5. The sensory system

### 5.1 Color — orthogonal encoding, made animate and rationed

1. **Unify on the canonical token layer (fix the seam).** Retire the parallel `--syn-*` sRGB
   approximations in `frontend/src/styles/tokens.css`; consume `design-system/color/dist`
   directly (`tokens.css` vars, `agentRgb()`/`tierRgb()`/`confidenceColor()` for
   deck.gl/three). This makes the confidence ramp the *real* gate-anchored diverging scale, not
   a hand-rolled green/yellow/red. No raw hex anywhere (INV-CLR-009 stays enforced).
2. **Encoding stays orthogonal and frozen** — agent→hue (INV-CLR-012, untouched), tier→L,
   confidence→diverging OKLab. SENSORIUM's contribution is to make these *temporal*: a node's
   chroma rises as its agent engages and falls as confidence settles. Encoding axes never
   cross (the orthogonality is the whole point).
3. **Rationing (P3).** Define a `--field-rest` near-monochrome base. Agent/tier/confidence
   color is *additive over rest*, gated on activity/abnormality. Implement as a chroma
   multiplier driven by state, clamped so the gamut-mapped tokens stay in sRGB (INV-CLR-008).
4. **Confidence as VSUP (P5).** Below the 0.70 gate, multiply chroma → toward 0 and coarsen
   value-bins; the I-5 escalation gate becomes a visible perceptual edge. Implement on top of
   `confidenceColor()` — no new hues, just suppression.
5. **Keep dual contrast and CVD discipline** — APCA-tiered (75/60/45) + WCAG 2.1 AA floor;
   verify every new surface under deuter/protan/trit. Color never the sole channel
   (INV-CLR-011): every state also carries text/icon/shape (the countdown, the alarm next-action,
   the degraded hatch).

### 5.2 Typography & density

- **`font-variant-numeric: tabular-nums` everywhere a number lives** — the Pulse rate, the
  300 s countdown, latency percentiles, prices, KL-divergence. Non-negotiable in a numeric
  control room; prevents digit jitter on live-updating values (Rauno's checklist).
- **Grayscale hierarchy carries structure; color carries signal.** Weight, size, and the
  neutral ramp (the canonical `--color-text-{primary,secondary,tertiary}`) do the layout work
  so hue is free to mean something.
- **Density without noise** — a strict spatial grid (the existing radius/space tokens),
  dense like Bloomberg/Linear but quiet, because §5.1's rationing keeps the resting screen
  monochrome.
- Consistent font-weight across interactive states (no layout shift); focus via `box-shadow`
  ring (existing `--color-focus-ring`), never `outline`.

### 5.3 Motion — the breath, and interruptible springs

Motion has two jobs here, both derived: **make the organism's rhythm perceptible** (P2) and
**direct attention to state change** (P3) — never decoration.

- **Springs over fixed easing** for anything input-driven (Emil Kowalski): interruptible,
  re-targetable. Reserve cubic-bezier (the `--motion-ease-*` tokens) for entrances/exits with
  known endpoints.
- **Compositor-only properties** (`transform`, `opacity`); never animate during theme
  switches; **pause looping animation off-screen** (the Pulse stops when the Cortex isn't
  visible). Profile shared-element transitions — they're powerful for the dive-into-decision
  continuity (P4) but expensive.
- **Suppress animation on high-frequency repeated actions** — an operator clicks Approve a
  thousand times a shift; that action must be instant, not animated (Rauno).
- **The Breath.** The Cortex's resting pulse uses the long `--motion-duration-pulse` (2400 ms)
  token; it is the *only* always-on motion, and it is calm by construction.
- **`prefers-reduced-motion` is a first-class equivalent, not a removal** (INV-CLR-013). Every
  motion-encoded state — the pulse, the constellation settle, the countdown — has a static
  equivalent (a numeric rate, a settled layout, a discrete timer). Reduced motion must lose
  *no information*.

### 5.4 Sound (optional, frontier) — ambient sonification

A control room that can be *heard* lets the operator look away. A barely-audible ambient tone
whose pitch tracks aggregate confidence and whose rhythm tracks decision cadence (the Pulse,
sonified). An escalation has a distinct, non-alarming earcon. Strictly opt-in, off by default,
and — like color — *rationed*: silence is the healthy state. This is a stretch goal; it must
never be required to operate the system (accessibility parity with the visual channel).

---

## 6. Signature interactions

- **Command palette as the primary verb surface** (Raycast/Linear lineage, Bloomberg's
  two-key grammar ancestor). `⌘K` → fuzzy verb-noun: "override D-1a2…", "steer cost +0.1",
  "replay last Tier-4", "focus disruption". Expert operators live here 8 hours a day; the
  keyboard beats the mouse. Opens on `mousedown`, `↑↓`-navigable, `⌘⌫` to clear.
- **Optimistic with rollback (P6).** Override and steering commit locally instantly, reconcile
  with the audit-first server write, roll back with inline feedback on failure. The supervisor's
  tools feel faster than the agents.
- **Dive, don't navigate (P4).** Clicking a firing signal in the Cortex *falls into* its
  Tribunal via a shared-element transition that preserves the object's identity (the node you
  clicked *is* the node that grows into the constellation). Escape rises back to ambient.
- **Time-travel everywhere it makes sense** — the Tribunal phase-scrub, the divergence trace,
  the Monte-Carlo draws. Replaying a decision is the core comprehension act.
- **Lens-pivot keeps focus** — a SKU selected on the map stays selected when you switch to the
  supply graph or the demand-forecast view. One ontology, many lenses.

---

## 7. The honesty contract (P7) — designed degraded states

This is the AUX differentiator and the thing that makes trust calibration *possible*. Every
surface defines its **degraded** rendering with the same rigor as its healthy one:

| Condition | Source of truth | How SENSORIUM shows it |
|---|---|---|
| Agent on fallback model | `Provenance.degraded` / `model_version` (ADR-040) | Council node hatched + muted + labelled "fallback"; its confidence rendered with extra VSUP suppression |
| Stale features | `Provenance.feature_source` (degraded vs Feast-live) | A "stale" chip on any number derived from it; never a confident point estimate |
| Ollama unreachable (I-7) | graceful-degradation fallback path | Debate phase shows "LLM unavailable — heuristic convergence"; never a fabricated reasoning chain |
| Twin diverged (I-12 > 0.1) | KL-divergence metric | Projection surface flags "twin re-syncing — projections unreliable"; the drift trace spikes |
| Firehose heartbeat-only | `firehose.py` aiokafka fallback | Connection pill honest: "Live (heartbeat)" not a fake green; the Pulse shows it's not receiving decisions |
| Build mismatch | `BuildSHAChip` vs `/version` | Existing chip; "old UI" → cache, per ADR-039 ops note |

**A degraded SYNAPSE looks degraded.** This is not a failure of polish; it is the highest
polish — because an interface that lies about the machine's state breaks P1 instantly and
permanently.

---

## 8. Accessibility & internationalization (non-negotiable)

- WCAG 2.1 AA as the legal floor; APCA-tiered (75/60/45) as the craft target (note: APCA is
  still a WCAG-3 *candidate*, so the floor stays WCAG 2.1 — exactly as the spec already does).
- CVD-proof: every new color use verified under deuter/protan/trit (INV-CLR-005); lightness
  staggering preserved; color never sole-channel (INV-CLR-011).
- `prefers-reduced-motion`, `prefers-contrast`, `forced-colors` honored with full-information
  fallbacks (INV-CLR-013; the `hc` theme exists).
- Keyboard-complete (Radix primitives, focus-visible rings, J/K/A/R/M already present); the
  command palette makes every verb reachable without a mouse.
- i18n (en/hi present) — the Pulse, the countdown, and alarm next-actions are all localizable;
  numerals stay tabular.

---

## 9. Visualization technique → data mapping (the concrete crosswalk)

| Data (source) | Technique | Why |
|---|---|---|
| Decision cadence + aggregate confidence (`decision` channel) | **The Pulse** — sonifiable ambient waveform, temp = confidence | P2 ambient clock; P3 quiet-by-default |
| Demand density (`demand` channel) | deck.gl **`HexagonLayer`**, `gpuAggregation: true` | Millions of points, GPU, live |
| In-flight deliveries / routes (`routing`) | deck.gl **`TripsLayer`** (trailing fade) + **`ArcLayer`** | 10-min delivery is inherently temporal |
| 8-objective Pareto front (`pareto.py`) | **Parallel coordinates** + bold knee polyline + ghost (what-if weights) | n-D front; show the few candidates + *why chosen* |
| Conformal intervals (`demand_prophet`, `lower_90`/`upper_90`) | **Quantile dotplots** | Untrained-operator decision quality (proven) |
| Monte-Carlo / what-if (Tier-4 twin) | **HOPs** (animated draws → accreted band) | Operator *feels* the spread of futures |
| Confidence everywhere (I-5) | **VSUP** chroma suppression below gate | Renders uncertainty into the pixels (P5) |
| Twin KL-divergence (I-12) | **Drift trace** with 0.1 threshold | Disagreement is itself signal |
| Consensus 5-phase + debate | **Execution trace** + time-travel scrub | LangSmith idiom; comprehension (SA-L2) |
| 8-agent conflict graph (`_detect_conflicts`) | **Constellation edges** that pulse + settle | The debate, made honest and animate |
| Supply graph (Neo4j topology) | GPU **force layout**, community-clustered | One ontology, many lenses (P4) |

---

## 10. Atlas v1.1 → SENSORIUM — concrete deltas

This is an evolution, not a rewrite. The toolkit, the surfaces, the typed client, the firehose
plumbing all stay. What changes:

1. **Token unification (foundational).** Consume `design-system/color/dist` directly; delete
   the parallel `--syn-*` sRGB confidence/tier ramps; route deck.gl/three through
   `agentRgb()`/`tierRgb()`/`confidenceColor()`. *Correctness + craft.* (Respects INV-CLR-009/010.)
2. **Mission Control → The Cortex.** Replace the KPI-tile grid with the Pulse + rationed
   Living Map + desaturated Council strip. Color goes quiet-by-default (P3).
3. **Decision Theater → The Tribunal.** Elevate `ParetoFrontier` (2-D) to 8-D parallel
   coordinates with knee + ghost; turn `ProposalConstellation` edges into the live conflict
   graph; wire `ReasoningTimeline` to full time-travel via `lib/replay.ts`.
4. **Override Cockpit → The Threshold.** Make the 300 s countdown + its fallback the spine;
   embed the full inherited Tribunal context; add the operator calibration mirror (override
   hit-rate).
5. **Twin Lab → The Projection.** Divergence *trace* (not gauge); Monte-Carlo HOPs; keep 3-D
   graph with documented GPU upgrade path.
6. **Steering → The Will.** Add the live knee-point preview (consequence-before-commit),
   visibly coupled to the Cortex's color-drain threshold.
7. **Confidence everywhere → VSUP.** Replace the three-stop ok/warn/risk chips with the
   continuous gate-anchored scale + chroma suppression.
8. **The honesty contract (§7)** becomes a cross-cutting component spec: every surface gets a
   designed degraded state wired to `Provenance` / I-7 / I-12 / firehose fallback.
9. **Command palette** as a new global verb surface.
10. **Sound (opt-in)** as a stretch experiment behind a flag.

None of this requires breaking a frozen invariant. The one thing that *would* — re-assigning an
agent hue — is explicitly **not** proposed; SENSORIUM's power comes from using the existing
frozen palette *more rigorously* (rationed, animate, gate-anchored), not from changing it. If a
future need arises to add a 9th agent hue, that requires a version bump + ADR supersede note
per INV-CLR-012 — flagged, not assumed.

---

## 11. Roadmap (phased, invariant-respecting)

- **Phase 0 — Foundation & seam fix. ✅ SHIPPED.** `lib/chromatics.ts` brings the
  gate-anchored OKLCH confidence scale (mirrors the canonical `dist` `confidenceColor()`,
  INV-CLR-007) + the VSUP suppression model + `rationedAgentColor()` (the rationing
  primitive); `lib/agent-identity.ts` becomes the single frozen-identity source
  (ProposalConstellation deduped onto it). Pure, deterministic, 17 tests. No new ADR.
- **Phase 1 — The Cortex. ◐ IN PROGRESS.** Shipped: the **Pulse** (firehose-as-weather,
  quiet-by-default, VSUP confidence) and the **rationed Council strip** with the honest
  degraded-state contract (§7), wired into Mission Control via `CortexBanner` from the live
  firehose + agents query (18 tests; full suite 111/111, `vite build` green). Remaining: the
  rationed Living Map (grayscale-at-rest deck.gl layers) and lifting the legacy KPI band into
  the ambient field.
- **Phase 2 — The Tribunal.** 8-D Pareto parallel coordinates, live conflict-graph
  constellation, time-travel scrub. The comprehension crown jewel.
- **Phase 3 — The Threshold.** Countdown-spine, inherited context, calibration mirror.
- **Phase 4 — The Projection & The Will.** Divergence trace, Monte-Carlo HOPs, steering
  live-preview.
- **Phase 5 — Signature interactions.** Command palette, optimistic/rollback polish,
  lens-pivot focus preservation.
- **Phase 6 — Stretch.** Ambient sonification (opt-in); GPU-shader supply graph if scale
  demands.

Each phase ships behind the existing test rigor (vitest + axe + Storybook + Playwright +
Stryker), preserves every `INV-CLR` and `FE-INV`, and adds spec coverage for any new invariant
it introduces (e.g. "the resting Cortex emits no chroma above ε," "every surface has a degraded
render," "VSUP suppression crosses zero-chroma exactly at the 0.70 gate").

---

## 12. The one-sentence north star

> **SENSORIUM makes an autonomous mind perceptible — calm and near-colorless when the machine
> is sure, vivid and conversational precisely at the edge of its competence — so a human can
> calibrate exactly how much to trust it, and step in only where it counts.**

That sentence is the whole design. Everything above is its derivation.
