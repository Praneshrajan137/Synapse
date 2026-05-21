# ADR-025: Synaptic Calm — frontend rebuild

## Status
Accepted

## Context
The original SYNAPSE frontend exposed roughly 5% of the backend's
expressive surface: a five-page React/Vite/JSX scaffold with Tailwind
installed but unwired, inline styles, no design system, no tests, no
animation, and visualization libraries (three.js, deck.gl) sitting
unused. The backend, by contrast, produces an unusually rich decision
surface — eight agents, four decision tiers (100ms–120s), a five-phase
consensus protocol, append-only context (I-14), immutable audit (I-4),
a Pareto front, a digital twin, and 16 Kafka topics. An operator could
not see, trust, or act on most of it.

A world-class Agentic User Experience (AUX) was needed: an interface
that makes autonomous agent behavior legible, trustable, and
collaborative — not "a dashboard with a chat box".

## Decision
Rebuild the frontend as **Synaptic Calm** — "an operating theater for
autonomous decisions" — via a strangler-fig migration that keeps the app
shippable at every step. Ten phases:

1. **Foundation** — TypeScript strict, Tailwind v4 with a CSS-first
   token system, Biome, Vitest, Playwright, Storybook, MSW, OpenTelemetry
   browser tracing (to a new self-hosted Tempo), a forbidden-imports CI
   gate (I-1).
2. **Design system** — 11 owned, accessible primitives, viz components
   (ConfidenceGauge, KPISpark, TierBadge) and the eight custom agent
   sigils.
3. **App shell** — Sidebar, StatusBar, Synaptic Feed, Command Palette,
   global keyboard map, a synthesized Web Audio sound engine.
4–8. **The seven surfaces** — Bridge, Theater, Council, Replay, Twin,
   Inspector, Streams — each driven by a typed domain layer, React Query
   hooks, and an MSW mock gateway.
9. **Frontier AUX** — generative-UI payload renderers, local voice
   push-to-talk, cinematic Demo Mode, Steering governance, a lightweight
   in-house i18n (en/hi/kn/mr), PWA offline support.
10. **Hardening** — dependency cleanup, route-level code splitting,
   documentation.

Twelve first-principles tenets (T-1 … T-12) govern every design
decision; they are recorded in the plan and the per-surface specs.

Two deliberate scope choices diverge from the original plan:
- **Custom SVG visualization** instead of three.js / deck.gl. The
  surfaces (LivingMap, SupplyGraph, ProposalConstellation, ParetoCell)
  are hand-rolled SVG. This is lighter, fully offline, on-brand, and
  vendor-free (tenet T-12); the heavy libraries were removed.
- **Lightweight in-house i18n** instead of Lingui, avoiding a Babel
  macro in the Vite pipeline. The architecture (typed catalog, `useT`
  hook, locale in the UI store) is in place; component-level adoption is
  incremental.

The backend gains a small set of additive, non-breaking endpoints
(twin what-if, audit timeline, agent detail, topics); until they exist,
MSW serves the same contracts so the UI is fully demonstrable.

## Consequences
**Easier:** an operator can supervise eight agents calmly; every value
has provenance; the consensus protocol is legible as a cinematic
process; decisions are replayable with perfect fidelity; the interface
is keyboard-first, accessible (WCAG 2.2 AA), and installable.
Type-checked end to end (`tsc --strict`), 78 unit/component tests with
jest-axe, Playwright E2E, and a paid-API import gate (I-1) all run in CI.

**Harder:** the frontend now has real surface area to maintain — a
design system, seven surfaces, and a mock layer. The MSW gateway must be
kept in lockstep with the real backend contracts until the additive
endpoints land.

## Alternatives Rejected
- **Incremental patching of the legacy JSX app** — rejected: no design
  system or test foundation to build on; the legacy surfaces exposed too
  little of the backend to be worth preserving.
- **Next.js / RSC** — rejected: SSR adds little to an authenticated
  internal operations console; Vite's dev speed and the existing
  toolchain win.
- **three.js / deck.gl visualization** — rejected for v1: custom SVG is
  lighter, offline-robust, and gives complete aesthetic control; 3D can
  return for the Twin if a future need justifies the weight.
- **Lingui for i18n** — deferred: its Babel macro complicates the Vite
  build; a typed in-house catalog covers the same architecture at zero
  dependency cost.
