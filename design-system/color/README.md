# SYNAPSE Chromatic System

The portable, perceptually-grounded colour core for the SYNAPSE platform — a
spec-governed OKLCH design-token system. One source of truth, consumed by the
live HITL Console (`frontend/`) and ready for the TypeScript "Atlas Console"
redesign. Governed by [ADR-025](../../docs/adr/ADR-025-oklch-perceptual-color-system.md).

## The idea — the Orthogonal Encoding Principle

SYNAPSE's UI must show three independent data types at once. Each is mapped to
the OKLCH dimension that natively fits it, so the channels never collide:

| Data type | SYNAPSE concept | OKLCH axis |
|-----------|-----------------|------------|
| Nominal (categorical) | Agent identity (8) | **Hue** |
| Ordinal | Decision tier 1→4 (I-8) | **Lightness** |
| Continuous | Confidence [0,1], gated 0.70/0.80 (I-5) | a **diverging** OKLab scale |

A hue is *earned* by being a distinct point on the categorical wheel; a
lightness is *earned* by its ordinal rank. Nothing arbitrary — every claim is a
testable invariant in [`color-system.spec.yml`](./color-system.spec.yml).

## Bounded context — "Chromatic" (DDD)

- **Aggregate root** — `ColorSystem` (the resolved token model).
- **Value objects** — `OklchColor`, `Token`, `Ramp`, `Theme`.
- **Domain services** — `TokenResolver` (`build/resolve.mjs`),
  `ContrastEvaluator` (`build/contrast.mjs`), `CvdSimulator` (`build/cvd.mjs`).
- **Domain model** — the DTCG token JSON in `tokens/`.
- **Anti-corruption layer** — `build/build.mjs`, which compiles the model into
  the delivery artifacts; consumers never touch the model directly.

## Layout

```
color-system.spec.yml     SDD — 14 INV-CLR invariants, the single source of truth
tokens/                   DTCG token JSON (primitives -> agents -> semantic)
build/                    resolve | contrast | cvd | build  (culori only)
dist/                     GENERATED, committed: tokens.css / .ts / tailwind-preset.cjs / .json
tests/                    7 testing layers (SDD, Fuzz, Contract, Metamorphic, DbC, Oracle, Mutation)
features/                 BDD — Gherkin behaviour specs, mapped to the test files
scripts/                  spec coverage, test scaffolder, contrast report, hex lint, licence audit
schema/                   JSON Schemas for the spec and the token files
```

## Build & verify

```bash
npm run build            # compile tokens/ -> dist/   (deterministic)
npm run verify           # build + spec coverage + the full 7-layer suite
npm run contrast:report  # WCAG/APCA audit + dist/contrast-report.html (CVD swatch sheet)
```

`dist/` is committed and deterministic — CI fails if a rebuild changes it
(INV-CLR-010). Rerun `npm run build` and commit `dist/` after any token edit.

## Consuming the system

- **CSS / Tailwind** — `dist/tokens.css` defines every semantic token as a CSS
  custom property (light + dark via `[data-theme]`); `dist/tailwind-preset.cjs`
  binds Tailwind utilities to them. The frontend reaches both via the
  `@chromatic` Vite alias.
- **JS / TS** — `dist/tokens.ts` is a typed API: the `tokens` map, plus
  `confidenceColor()`, `agentRgb()` / `tierRgb()` (`[r,g,b]` arrays for deck.gl
  / MapLibre / force-graph), and `confidenceZone()`.

## Rules

- No raw hex / `rgb()` / `hsl()` in `frontend/src/**` — colour only via tokens
  (INV-CLR-009, `no-raw-hex` hook).
- The 8 agent→hue assignments are **frozen** (INV-CLR-012). Changing one needs
  a version bump and an ADR supersede note.
- Every `INV-CLR` invariant must have a test (`npm run spec:coverage`).
- Colour is never the sole channel — pair it with a label, glyph, or shape
  (INV-CLR-011).
