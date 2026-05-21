# SYNAPSE — Synaptic Calm Interface

An operating theater for autonomous decisions. The frontend for the SYNAPSE
multi-agent quick-commerce supply-chain platform.

> See `.claude/plans/you-are-the-singular-splendid-yeti.md` for the full plan
> and `docs/adr/ADR-025-frontend-synaptic-calm.md` for the decision record.

## Stack

- **Vite 6** + **React 19** + **TypeScript 5.7** (`strict`, `noUncheckedIndexedAccess`)
- **Tailwind v4** (CSS-first `@theme` tokens) — see `src/styles/globals.css`
- **Motion** (springs), **Radix** primitives, **TanStack** Query + Virtual
- **Zustand** state, **cmdk** command palette, **MSW** mock gateway
- **Biome** (lint + format), **Vitest** + **Testing Library** + **jest-axe**,
  **Playwright** (E2E), **Storybook 8** (workbench)
- **OpenTelemetry** browser SDK → self-hosted Tempo; **PWA** offline support

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Dev server on :3001 (proxies `/api`, `/ws` → :8085) |
| `npm run build` | Type-check (`tsc -b`) + production build |
| `npm run typecheck` | Strict type-check only |
| `npm run lint` | Biome lint + format check |
| `npm run test` | Vitest unit + component tests |
| `npm run test:e2e` | Playwright end-to-end |
| `npm run storybook` | Storybook workbench on :6006 |
| `npm run audit:imports` | I-1 gate — fails on paid-API imports |
| `npm run verify` | typecheck + lint + test + import audit |

The MSW mock gateway runs by default so the interface is fully demonstrable
without the Python stack. Build with `VITE_MOCK_API=false` to hit a real backend.

## Architecture

Hexagonal / DDD-aligned:

- `src/domain` — pure types, zero React (Decision, Twin, KPI, Audit, …)
- `src/application` — React Query use-case hooks
- `src/infrastructure` — API client, realtime hooks, telemetry
- `src/ui` — tokens, primitives, components, charts, viz
- `src/aux` — frontier AUX (payload renderers, voice, sound, demo mode, keyboard)
- `src/app` — routes, shell, stores
- `src/mocks` — MSW gateway with deterministic mock data

### The seven surfaces

| Surface | Route | Purpose |
| --- | --- | --- |
| Bridge | `/` | Situational awareness — KPIs, living map, decision tape |
| Theater | `/theater` | Cinematic five-phase consensus playback |
| Council | `/council` | HITL override — escalation interrogation |
| Replay | `/replay` | Decision time machine over the immutable audit log |
| Twin | `/twin` | Supply network + Monte Carlo what-if |
| Inspector | `/inspector` | Per-agent x-ray — rewards, calibration, traffic |
| Streams | `/streams` | Kafka topic explorer |

Plus `/steering` for governance (Pareto weights, thresholds, demo, language).

## Build status — all ten phases complete

1. Foundation — TS strict, Tailwind v4, tokens, test infra, OTel, CI
2. Design system — 11 primitives, viz components, 8 agent sigils
3. App shell — Sidebar, StatusBar, Synaptic Feed, Command Palette, sound
4–8. The seven surfaces, domain + data layer, generative UI, voice PTT
9. Steering, cinematic Demo Mode, in-house i18n (en/hi/kn/mr), PWA
10. Hardening — dependency cleanup, code splitting, docs

## Design tokens

`src/styles/globals.css` is the single source of truth (Tailwind `@theme`).
`src/ui/tokens/*.ts` mirrors it for JS consumers (canvas, SVG viz);
`colors.test.ts` guards against drift between the two.
