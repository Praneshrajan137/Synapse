# ADR-025: Frontend Elevation — Atlas Console v1.0

## Status
Accepted (S1 of the Atlas Console initiative — see `plans/analyze-my-codebase-enhance-eager-taco.md`)

## Context
The repository's frontend at the start of S1 (`frontend/` v0.4.0) is a five-page React 18 + Vite + Deck.gl + MapLibre + Recharts scaffold authored against ADR-012. Four of five routes are stubs with no live data path; there is no TypeScript enforcement, no tests, no lint, no a11y story, no auth flow, no Docker image, and no CI gating beyond `npm audit`. Meanwhile the backend exposes an immutable `audit_consensus` table, a 1 000-scenario Monte-Carlo Digital Twin, an HITL escalation WebSocket, 9 user-visible Kafka topics, 11 domain JSON schemas, and 7 Grafana dashboards — none of which surface to the operator.

The Atlas Console plan elevates this scaffold to a regulator-grade, ops-first, real-time control surface organised around six DDD bounded contexts (Living City, Mission Control, Decision Trace, Twin Studio, Agent Floor, Audit Vault). It must satisfy:

- **I-1**: zero paid SaaS, OSS only, license allow-list (MIT, Apache-2.0, BSD-2/3, PSF, ISC, MPL-2.0).
- **I-3**: every output validates against `proto/domain/*.schema.json` — at the boundary, on the client.
- **I-5**: confidence-gated HITL escalation as the highest-value UX surface.
- **I-13**: KV-cache prefix stability — payloads sent to `/a2a` and `/api/v1/decisions` must be canonical (sorted-key) JSON.
- **I-14**: append-only runtime context — Decision Trace is replayable through a time-scrubber.
- **ADR-012**: React + Deck.gl + MapLibre + Vite + Recharts. **Kept**, not superseded.
- **ADR-014 / ADR-015**: spec-driven development and the seven-layer testing topology — frontend mirrors them.

## Decision

ADR-025 amends ADR-012 with a layered tooling delta. Nothing in ADR-012 is replaced; the visual stack (React 18, Deck.gl, MapLibre GL, Vite, Recharts) is retained. The additions are:

### Language & build
- **TypeScript 5.6 strict** (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`). Existing JSX coexists via `allowJs: true` for the duration of S1; full migration completes in S2.
- **Vite 5** (kept) + project-references TS configs (`tsconfig.app.json` for src, `tsconfig.node.json` for tooling) so the build never typechecks Vite plugins against DOM globals.
- **pnpm 9** + Corepack for hermetic installs. `pnpm-lock.yaml` is the pin; CI gate verifies via `lockfile-lint`.

### Routing & state
- **TanStack Router** with file-based routing under `src/surfaces/` and Zod-validated typed search-params. Replaces `react-router-dom` (kept as a shim through S1 for the legacy JSX pages). Justification: every Atlas Console surface is filter-heavy (decision tier, time window, agent, override). Typed search-params make every URL bookmark-shareable for shift handoffs and eliminate the "stale query string" class of bugs entirely.
- **TanStack Query 5** (kept) for server state, with the canonical key shape `[cityId, ...]` so a city switch invalidates everything cleanly.
- **Zustand 5** for ephemeral global state (one slice per surface). Forbidden: a third store layer (Jotai, Redux). Local UI state stays in `useState`/`useReducer`. URL-shareable state goes through TanStack Router search-params, never Zustand.

### UI & design system
- **shadcn/ui** components (Radix + Tailwind, copy-in, registry commit pinned in `components.json`). Accessibility comes from Radix primitives; we own and version the source.
- **Tailwind v3.4** (deferring v4 until plugin parity catches up — `@tailwindcss/forms`, `@tailwindcss/typography`, RTL ecosystem).
- **CSS-variable design tokens** in `src/shared/design-tokens/tokens.css`. Light + dark themes via `[data-theme]`; safety-critical palette (`--color-safety-*`) clears AAA contrast (7:1) on bg/fg.

### Data contracts
- **Orval** generates TanStack-Query hooks from `packages/openapi/openapi.json` — a committed snapshot. CI asserts byte-equality with `GET /openapi.json` from a freshly booted gateway (`tests/contract/test_openapi_byte_equality.py`, B5). Drift is red.
- **`json-schema-to-zod`** compiles `proto/domain/*.schema.json` to Zod schemas at build time. Inbound WS/SSE payloads validate at the edge.

### Real-time transport (also ratified by ADR-026)
- **WebSocket** for HITL escalation only (existing `/ws/escalation`).
- **SSE** for all Kafka topic tails through a new `/api/v1/stream/{topic}` bridge (B1). Backend gap closes in S1 alongside this ADR.

### Auth (also ratified by ADR-027)
- **Backend-for-Frontend (BFF) cookie session**, not JWT-in-memory. The new `api/routers/auth.py` (B3) holds the JWT server-side; the browser sees only an HttpOnly + SameSite=Strict + Secure session cookie. CSRF is mitigated by SameSite + a double-submit `X-CSRF` header on mutations.

### i18n
- **i18next** with ICU MessageFormat. Day-1 locales: `en`, `hi`. Scaffolded empty: `kn`, `mr`. Extracted by `i18next-parser`; CI gates on missing keys per locale.

### Telemetry & observability
- `web-vitals` v4 → `POST /api/v1/rum` (B4) via `navigator.sendBeacon`.
- OTel JS, sampled 1% trace / 100% errors, → existing OTLP collector.
- Self-hosted **GlitchTip** (Sentry-API compatible, Apache-2.0) for error capture.
- Self-hosted **Unleash** (Apache-2.0) for feature flags / kill-switching.

### Test topology (mirrors ADR-015 seven-layer)
| Layer | Tooling |
|---|---|
| L1 — Unit | Vitest + RTL + jsdom (≥85% lines / 80% branches per surface) |
| L2 — Property | `fast-check` (gauges, color thresholds, canonical-JSON encoder) |
| L3 — Visual | Storybook 8 + `@storybook/test-runner` |
| L4 — A11y | `storybook-addon-a11y` (axe) + `@axe-core/playwright`. AAA on tagged stories per ADR-028 |
| L5 — Contract | MSW 2 (REST + WS + SSE) + OpenAPI byte-equality |
| L6 — E2E | Playwright + `@cucumber/cucumber` (BDD scenarios per persona) |
| L7 — Performance | Lighthouse CI with per-route LCP/TBT/CLS budgets + bundle thresholds |

### Repository organisation — vertical slice by surface
```
src/
├─ app/                 providers, router root, error boundary
├─ surfaces/            one folder per bounded context
│  ├─ living-city/{routes,components,hooks,api,model,stories,e2e,bdd}/
│  ├─ mission-control/...
│  ├─ decision-trace/...
│  ├─ twin-studio/...
│  ├─ agent-floor/...
│  └─ audit-vault/...
└─ shared/              ui (shadcn), design-tokens, api (Orval), schemas (Zod),
                        realtime, telemetry, flags, i18n, canonical-json, test
```
Cross-surface imports are forbidden (ESLint rule); surfaces talk via `@shared/*` anti-corruption layers only.

### Charting
- **Recharts** retained for the existing `KPITicker` (no migration churn).
- **Visx** (MIT) is the standard for new visualisations: brushable trace timeline, force-directed agent debate, Pareto knee, KL divergence sparkline, scenario fan-out. One chart library per problem class — no overlap permitted.

### Build & deployment
- Multi-stage Dockerfile (`frontend/Dockerfile`, build context = repo root): `node:20-alpine` build → `nginxinc/nginx-unprivileged:1.27-alpine` runtime serving static `dist/` on port 8080.
- `synapse-frontend` service added to `docker/docker-compose.yml`. Outer nginx upstream corrected from `:5173` to `:8080` (B6). Two nginx layers: outer owns CSP/rate-limiting/CORS/request-id; inner owns SPA fallback + cache headers.
- CycloneDX SBOM embedded as `org.opencontainers.image.sbom` label on every build.

## Consequences

### Positive
- **Boundary safety end-to-end**: TS strict + Zod from JSON Schema + Orval from OpenAPI eliminates the entire "shape mismatch" failure mode.
- **Audit-friendly**: vertical slice + DDD aligns the codebase with the bounded contexts a regulator already understands. The Audit Vault surface becomes a one-folder reading exercise.
- **Reproducible URLs**: every filter, every scenario, every time-window is shareable. Ops handoffs work.
- **Zero cost**: every line-item is on the I-1 license allow-list and self-hostable.
- **Test parity with backend**: ADR-015's seven layers map 1:1 onto the frontend; no new mental model to teach.

### Negative / costs
- **Dependency surface grows considerably** — TanStack Router, shadcn primitives, Visx packages, Storybook, Playwright, Cucumber, Orval, MSW, Stryker, Lighthouse CI, GlitchTip SDK, Unleash, OTel. Mitigated by license allow-list CI, `lockfile-lint`, supply-chain audit, and CycloneDX SBOM in every build.
- **Two routers in S1** (react-router-dom shim + TanStack Router scaffolding). Documented; removed in S2.
- **Two charting libraries** (Recharts + Visx) until KPITicker migrates; no runtime overlap because both are chunk-split per route.
- **Backend gap deliverables (B1–B7) are in the same sprint** as the frontend foundation. If they slip, frontend is mocked via MSW handlers but visible work appears blocked.
- **Tailwind v4 deferred** — gives up native cascade-layer ergonomics until plugin ecosystem catches up.

### Migration plan (S1 → S6 per plan §15)
- **S1**: this ADR, package.json rewrite, TS configs, Vite 5 config migration, design tokens, Orval pipeline, Storybook init, Vitest + Playwright + Lighthouse, ESLint/Prettier/commitlint, Dockerfile + compose service, frontend.yml CI gates. Backend B1–B3 + B6 ship in lockstep.
- **S2**: TanStack Router migration, BFF wired, MSW REST/WS/SSE handlers, i18next (en+hi). Backend B4, B5, B7 ship.
- **S3**: Mission Control + Decision Trace surfaces.
- **S4**: Living City + Agent Floor.
- **S5**: Twin Studio + Audit Vault.
- **S6**: Hardening (Lighthouse budgets, threat model, runbook, rollback drill, Stryker, demo-mode determinism, kn+mr translations, AAA contrast tests, motion-reduce sweep).

## Alternatives Rejected

- **Next.js / TanStack Start (SSR)** — rejected. Atlas Console is an internal control surface; SSR adds operational complexity without persona benefit. Vite SPA stays.
- **Feature-Sliced Design** — rejected. FSD's 7-layer hierarchy is overkill at 6 surfaces and 1 team; vertical slice wins on discoverability and refactor blast-radius for our DDD-aligned domain.
- **Jotai or Redux Toolkit for client state** — rejected. TanStack Query owns server state; Zustand covers ephemeral global; URL-shareable state belongs in TanStack Router search-params. A third store layer creates atom-graph entropy at scale.
- **Visx + Recharts simultaneously for new viz** — rejected as two libraries doing one job. Recharts is retained only for KPITicker; new viz is Visx-only.
- **WebSocket for Kafka tails** — rejected. SSE wins for one-way streams: HTTP/2 multiplexes through nginx, `EventSource` ships built-in `Last-Event-ID` reconnection, and corporate proxies that strip WS upgrades survive. WebSocket is reserved for the bidirectional `/ws/escalation` channel.
- **JWT-in-memory + refresh cookie** — rejected. BFF cookie session is safer behind our existing nginx (no XSS-token-theft surface, page-refresh keeps you logged in, single auth-event log point for DPDPA audit).
- **i18n for 4 locales Day-1** — rejected as over-engineering. en + hi covers ~85% of staff; kn + mr scaffolded empty as 1-PR additions in S4+.
- **Mapbox / Auth0 / SaaS Sentry / SaaS Chromatic** — rejected. Violates I-1.
- **React Compiler enabled in S1** — rejected. Beta on React 18; risk to a stable foundation. Revisit in S6 hardening.

## References
- Plan: `plans/analyze-my-codebase-enhance-eager-taco.md`
- Adjacent ADRs: ADR-012 (visual stack, kept), ADR-014 (SDD), ADR-015 (seven-layer testing), ADR-026 (SSE), ADR-027 (BFF auth), ADR-028 (a11y AAA tagging — to be written in S6).
