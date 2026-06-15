# ADR-047 — The Operator Supervisory Layer (Standing Watch)

- **Status:** Accepted
- **Date:** 2026-06-15
- **Sprint:** 19 (`sprint17/standing-watch`)
- **Supersedes / extends:** ADR-044 (AUX truth exposure — per-decision honesty), ADR-040/041 (honest provenance + degradation), ADR-033 (audit chain)
- **Related invariants:** I-3, I-5, I-7, I-14; FE-INV-034..040 (per-decision honesty), new FE-INV-041..044

## Context

Sprints 11–16 made the SYNAPSE console honest **per decision**. A single decision now
carries structured provenance, a degraded marker, a synthetic badge, a tri-state
chain-integrity chip, its full debate/Pareto anatomy, and severity-coded guardrail
violations (ADR-044). Sprint 16 re-skinned all of it (Obsidian).

But supervising an autonomous system is not a per-decision job — it is an **aggregate,
temporal, outcome-closing** job across a shift. The console could not answer the three
questions that define that job:

1. **Is the autonomy trustworthy *right now*, in aggregate?** System posture
   (`GET /api/v1/system/posture`) was a one-line banner — no trajectory, no breaker
   board. SLO burn (`infrastructure/prometheus/rules/orchestrator_burn.yml`, multi-window
   per tier) was surfaced **nowhere**.
2. **Are the confidences *calibrated to what actually happened*?** There was no
   system-level calibration view, because **reality was never recorded** (see below).
3. **Where must I intervene, and *did my intervention help*?** Escalation
   resolution times (`audit_escalations.resolution_time_ms`) and override-action
   outcomes reached no aggregate surface.

### The load-bearing finding: `outcome` is an empty promise

`audit_consensus` has had a nullable `outcome JSONB` column since Sprint 4
(`infrastructure/postgres/02_sprint4_consensus.sql:23`, `orchestrator/audit/models.py:55`).
**The audit logger never writes it** (`orchestrator/audit/logger.py:91-108` inserts every
other anatomy column but omits `outcome`). The decisions API returns it, so it returns
empty. The system records what it *decided* and how *confident* it was, but **never what
actually happened.** There is no ground truth against which "confidence" is ever scored.

The matching frontend symptom: `OutcomeBand` is a built, tested, story-booked compound
that is **wired into no surface**. The outcome loop was open on both ends.

For a project whose post-Sprint-11 identity is *honesty and verification*, an unscored
confidence is the deepest unfulfilled promise in the stack. Closing it is **substance
work, not wiring** — and it is the heart of this sprint.

## Decision

Add a dedicated **Operations / Standing Watch** surface (`/operations`, `minRole=viewer`)
that composes the aggregate, temporal, and outcome signals — keeping Mission Control as
the *present-tense* surface (firehose, living map, Cortex) and Operations as the
*trend-and-trust* surface. Build the missing backend substance to feed it, under the
ADR-044 additive discipline.

### D1 — Additive read endpoints (no new Kafka topics, no schema break)
- `GET /api/v1/system/slo` — per-tier multi-window burn (fast 1h/5m, slow 6h/1h) +
  budget-remaining, via the Prometheus proxy pattern already used by `metrics.py`. New
  Prometheus **recording rules** emit the continuous burn *ratios* so the UI renders a
  gauge, not a binary firing/not-firing.
- `GET /api/v1/escalations/analytics` — escalation pressure over a window (count,
  resolution-time distribution, override-action mix, top escalation reasons), a pure SQL
  aggregate over `audit_escalations` ⋈ `audit_consensus`.
- `GET /api/v1/system/calibration` — reliability curve (predicted-confidence bin vs.
  realized-correct fraction), Brier score, and a per-`confidence_basis` breakdown, read
  from the newly-populated outcomes.

### D2 — Outcomes are an append-only fact stream (`decision_outcomes`), never a mutation
`audit_consensus` grants `synapse_app` **only INSERT + SELECT** — UPDATE is *never*
granted, with a DB self-test that raises on regression (`init_audit.sql:81`). Therefore
the scorer **cannot** write `audit_consensus.outcome`, and it must not (E-S9-02: the
hashed canonical row is byte-pinned). Outcomes live in a **new append-only
`decision_outcomes` table** (INSERT + SELECT only), keyed by `decision_id`, with a
`scored_at` so re-scoring appends a newer fact rather than mutating. The decisions API
LEFT-JOINs the latest outcome and returns it under the existing `outcome` response key;
the legacy `audit_consensus.outcome` column is left NULL and documented as superseded.

### D3 — Honest by construction: outcome is tri-state, `unknown` is the default
The scorer compares each decision (older than a settle horizon H) against the realized
signals that **genuinely exist today**:
- **execution confirmations** — the orchestrator's Phase-4 EXECUTING records
  (`decision.execution_confirmations`), the primary realized signal;
- **twin divergence** — the digital twin's KL signal as a realized-vs-model proxy
  (I-12, C34), where available.

Where no realized signal exists, the outcome is **`unknown`** — never a fabricated
`confirmed`. This is I-7 applied to outcomes: a trust surface that lies about trust is
worse than none. A new AST gate, `scripts/audit/outcome_truth.py` (modelled on
`substance_truth.py`/C33), flags any constant/fabricated outcome path → `verify_claims.py`
C-row + blocking CI step.

Because the live feed is dominated by the `traffic-generator` (synthetic-prefixed), every
aggregate **segments or excludes `is_synthetic`** and labels it, and the calibration panel
always discloses sample size + horizon + "as of" (FE-INV-043/044) — so a small real-n is
visible as small, not laundered into a confident-looking curve.

### D4 — Realized-demand scoring is the named next ratchet, not a fabrication
A full realized-demand join (forecast vs. realized order volume per city/SKU/window from
the orders ingress) is real but heavier than this sprint. v1 ships the
execution-confirmation + twin-divergence scorer and renders `unknown` honestly where those
are absent; realized-demand scoring is the documented next ratchet. The pipeline lights up
as the realized signals get richer — the mechanism, the table, the endpoint, and the
honesty gate are what land now.

## Consequences

- **Positive:** the operator can read system trust at a glance and over time; the outcome
  loop closes on both ends (a real `decision_outcomes` stream + the wired `OutcomeBand` +
  predicted-vs-realized on DecisionDetail); a previously-dead column becomes a live,
  honesty-gated fact stream; four new mechanical FE invariants + an `outcome_truth` gate
  prevent regression.
- **Negative / honest cost:** early real-n is small (synthetic dominance), so the
  calibration curve is sparse at first — surfaced as such, not hidden. The scorer's v1 is
  deliberately narrow; many outcomes will read `unknown` until realized-demand scoring
  lands. That is the truth, and the UI states it.
- **Constraints honored:** additive endpoints only; no new Kafka topics; frozen agent/tier
  hues untouched; `make_canonical_row` byte-pinned (chain mutation tests must stay green);
  entry bundle ≤180 KB gz (the new surface is route-split, visx stays async).
