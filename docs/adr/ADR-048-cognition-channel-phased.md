# ADR-048: The Cognition Channel — making the council's deliberation legible (phased)

## Status
Accepted — **Phase 1 (Council Theater) implemented**; Phases 2–3 (live telemetry +
agent-lifecycle tokens) **deferred** to a follow-up PR.

## Context
SYNAPSE's actual "thinking" is the five-phase consensus FSM in
`orchestrator/consensus/protocol.py`: COLLECTING → DEBATING (LLM-mediated, ≤3 rounds) →
ARBITRATING (NSGA-II Pareto) → EXECUTING → LEARNING. All of it is **recorded** in
`audit_consensus` and **already exposed** by `GET /api/v1/decisions/{id}` — proposals +
provenance, `context_messages` (the recited debate transcript), `debate_rounds`,
`pareto_front`, `execution_confirmations`, `outcome`, chain hashes.

Yet the operator's view of this richest-of-all signal was a **manual Radix slider with
text rows** (`DecisionDetail.tsx`), and the live firehose carries only the lean *verdict*
envelope (`decision-envelope.ts`) — never the reasoning. The AUX process-state grammar
(`CouncilStrip.processStateFor`, ADR-044) therefore **honestly refuses** to render
`thinking`/`debating`/`streaming`: no per-agent phase telemetry is emitted live, so
showing those states would be fabrication (I-7). That refusal is correct, and it is the
honesty bar this work must keep.

The opportunity: the deliberation is the highest-value thing the system produces and it
deserves to be *legible*, not buried in a form.

## Decision
Deliver the Cognition Channel in **phases**, so the honest, recorded substance ships now
and the live channel is documented as the explicit next step (rather than faked).

### Phase 1 — Council Theater (this PR, implemented)
A frontend-only, **honest reconstruction** of one recorded decision row:
- New surface `surfaces/council-theater/CouncilTheater.tsx` at route `/council/:id`
  (lazy/route-split, viewer role), deep-linked from `DecisionDetail` ("Watch
  deliberation →"), the Mission Control firehose tail rows, and the command palette.
- New compound `design-system/compounds/ConsensusChoreography.tsx`: auto-narrates the
  five phases by walking the **pure** `replayDecision` slicer (`lib/replay.ts`) — the
  auto-advance drives only the phase *index*, never the slice, so determinism
  (FE-INV-028) holds. It reuses the existing primitives only (`ProposalConstellation`,
  `AgentProposalChip`, `ParetoParallel`/`ParetoFrontier`, `ReasoningTimeline`,
  `ConfidenceChip`, `ChainIntegrityChip`, `SyntheticBadge`, agent-identity hues,
  framer-motion). **No new chromatic tokens; no token build; `design-system/color/dist`
  is byte-identical** (E-CLR-07).
- A shared `hooks/use-decision.ts` (`reshapeDecision` + `useDecisionQuery`) extracted from
  `DecisionDetail` so the analyst scrubber and the cinematic reconstruction share **one
  validated decision source** and can never drift.
- **Honest by construction (I-7):** labelled a *recorded reconstruction*, never "live"; a
  `debate_rounds === 0` decision shows "no debate — fast path" rather than a fabricated
  transcript; a null `pareto_front` shows the empty-front state; the ADR-047 outcome
  tri-state keeps `unknown` distinct from `confirmed`. Reduced motion collapses the player
  into a static, all-phases-at-once reveal where text carries every state.
- Invariants: **FE-INV-045** (renders only recorded phases), **FE-INV-046** (reduced-motion
  static reveal), **FE-INV-047** (labelled reconstruction; synthetic marked).

### Phase 2 — Live phase-telemetry channel (deferred)
Turn the reconstruction *live*:
- Emit FSM phase transitions from `protocol.py` (`_phase_collect/_debate/_arbitrate/
  _execute`) to a **new Kafka topic** `synapse.orchestrator.phase`. The inter-agent topic
  set is frozen (CLAUDE.md Kafka Rules); adding a topic requires a **fresh ADR exception**,
  exactly as ADR-029 did for the orders-ingress topic. This ADR is that exception for the
  cognition-telemetry category.
- Register `api_firehose` as the topic's consumer in `infrastructure/kafka/topics.json`
  (kept truthful by `scripts/audit/topic_consumer_truth.py`), add a new firehose
  `cognition` channel with a **strict Zod schema** (a typed-schema test, mirroring the
  decision/escalation channels — the lesson of the dead-channel defects).
- Payload contract (sketch): `{ decision_id, phase: "collecting|debating|arbitrating|
  executing|learning", agent_name?, round?, ts }` — additive/`.passthrough()` so future
  keys never break the schema.

### Phase 3 — Agent-lifecycle state tokens (deferred, lands WITH Phase 2)
- Chromatic **v1.4.0**: additive `state.cognition.*` tokens
  (thinking/searching/planning/streaming/debating) extending the existing
  `factor.agentstate.*` chroma-rationing (INV-CLR-017). **Frozen agent hues untouched**
  (INV-CLR-012). Reserve **INV-CLR-019+**. Authored in OKLCH; `npm run build` + commit the
  regenerated `dist/` lands only in that PR (so this PR's determinism gate stays green).
- Extend `processStateFor` to honestly derive `thinking/debating/streaming` from the live
  `cognition` events — replacing the current honest refusal with honest *evidence*.

### Numbering note
On disk the max ADR is 047. **ADR-049** (two-tier cost) and **ADR-050** (STRIDE threat
model) are already claimed by in-flight PRs, so this is **ADR-048**. When Phase 2/3 ships,
the agent-lifecycle-token work — if it warrants its own ADR — takes the next free number
at that time, rather than reserving one now for unbuilt code.

## Consequences
**Easier:** operators see the *reasoning*, not just the verdict; the recorded anatomy
(`context_messages`, `pareto_front`) finally reaches the screen; the AUX brief ("make
agency visible across every agent state") advances without fabricating anything; one
validated decision source removes a drift class.

**Harder / cost:** Phase 2 requires a frozen-topic governance exception plus backend
emission and a firehose consumer; until then Council Theater is reconstruction-only
(clearly labelled, never "live"). Phase 3 is a chromatic version bump with its own dist
rebuild. None of that lands in this PR, so the substance shipped here is fully honest and
self-contained.

## Alternatives Rejected
- **Upgrade the DecisionDetail slider in place.** Rejected: the analyst scrubber and the
  cinematic narration serve different jobs (forensic detail vs. causal story) and coexist;
  the operator chose a dedicated stage.
- **Emit live telemetry now (one big PR).** Rejected for this PR: it needs a frozen-topic
  ADR exception, backend FSM emission, a firehose consumer, AND a chromatic version bump —
  multi-PR scope. Phasing ships honest substance immediately and de-risks the rest.
- **Fabricate `thinking`/`debating` in the live AUX without telemetry.** Rejected:
  violates I-7; the grammar already refuses this for good reason.
- **Two separate ADRs (channel + tokens).** Rejected: both are deferred and serve the one
  goal (the cognition channel); a single phased ADR is leaner and avoids reserving an extra
  ADR number for unbuilt code — especially with 049/050 already taken.
