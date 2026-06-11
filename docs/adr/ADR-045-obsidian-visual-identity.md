# ADR-045: The Obsidian Visual Identity — Cold-Void Neutrals, Borderless Depth, Real Typography

**Status**: Accepted
**Date**: 2026-06-11
**Sprint**: 16 (Obsidian Control Room)
**Relates to**: ADR-025 (chromatic system), ADR-044 (AUX truth surface), INV-CLR-002/003/006/012, I-1

## Context

Sprint 15 made the interface semantically honest, but it still *looked* like
every default Tailwind dashboard, for three diagnosable reasons:

1. **The fonts never loaded.** The Tailwind config named Inter/JetBrains Mono
   but no font files or `@font-face` rules existed anywhere — every user saw
   `system-ui`.
2. **The frontend ignored its own design system.** The governed OKLCH palette
   (tier as a single H258 lightness ramp per INV-CLR-006, the gate-anchored
   continuous confidence scale) sat unconsumed in `design-system/color/dist/`
   while `frontend/src/styles/tokens.css` ran a parallel fork: Tailwind
   slate-950/900/800 neutrals and tier = emerald/sky/amber/rose — four
   unrelated hues violating the system's own ordinal-encoding principle.
3. **Border-grid monotony.** Every panel carried `border border-border`;
   elevation never came from surface contrast; all 8 surfaces shared one
   templated header.

## Decision

### D1 — Cold-void neutral retune (Chromatic v1.2.0)

`ref.neutral` moves from the H255 faint-cool ramp to a deeper **H265
blue-violet void** whose chroma *rises with depth* (the darkest surfaces read
rich, not dead grey) and whose lightness steps are **large enough that
elevation is legible without borders**:

| Role (dark) | v1.1.0 | v1.2.0 |
|---|---|---|
| canvas | 0.160 | **0.135** (C 0.016) |
| panel | 0.205 | **0.180** (C 0.018) |
| raised | 0.255 | **0.225** (C 0.018) |
| overlay | 0.310 | **0.285** (C 0.017) |
| border subtle/strong | 0.255 / 0.380 | **0.340 / 0.420** |
| text primary/secondary/tertiary | 0.972 / 0.850 / 0.805 | **0.972 / 0.790 / 0.700** |

Light theme analogous (canvas deepened 0.972 → 0.965 so panel-on-canvas
separation survives borderless; text secondary/tertiary 0.420/0.500 widen the
hierarchy). The text hierarchy spread is now *visible*, not just measurable.

**Gate-tuned, not taste-tuned**: the APCA tier gates rejected the first two
candidates — tertiary 0.660 failed on canvas (Lc 43.5 < 45) and 0.680 failed
on overlay (Lc 42.9 < 45); secondary 0.780 failed on overlay (Lc 59.7 < 60).
The shipped values (tertiary **0.700**, secondary **0.790**) are the lowest
lightnesses that clear every INV-CLR-002/003 pair on every surface in both
themes — all 58 spec tests pass. `ref.state.neutral` hue follows 255 → 265
for coherence (ΔEOK impact at C ≈ 0.012 is negligible; INV-CLR-014/015
distinctness re-verified).

**Untouched**: the 8 frozen agent hues (INV-CLR-012), the tier H258 ramp, the
confidence gates and stops, the v1.1.0 honesty states (degraded/synthetic)
and process-state factors.

### D2 — Borderless depth (dark theme)

Elevation = surface step + top-edge highlight + ambient shadow; **borders are
earned** (interactive affordances, table rules, alert states), never default
panel chrome. Recipes pinned in spec thresholds (the v1.1.0 interaction-recipe
precedent): `surface_highlight_alpha_dark: 0.04` (the 1px inset top edge),
`ambient_glow_alpha: 0.04` (a brand-tinted canvas radial — a NEUTRAL
constant; ADR-044 already rejected posture-driven ambience: degradation is a
marker, never a mood). **Light theme keeps hairlines + soft shadows; high
contrast keeps strong borders and no shadows** — borderless depth is a
contrast-budget luxury AAA cannot afford. Encoded per-theme in the FE token
blocks, not in components.

### D3 — Typography (the largest single lever)

Three self-hosted OFL faces (I-1, $0; sources + licenses recorded in
`frontend/public/fonts/FONTS.md`): **Space Grotesk** (display: titles, brand,
KPI numerals), **Inter Variable** (body/UI), **JetBrains Mono** (ids, data,
tabular numerals). `font-display: swap`, the two paint-critical variable
files preloaded. Fonts are static assets — zero cost against the FE-INV-014
JS bundle budget.

### D4 — The frontend finally adopts the governed palette

`frontend/src/styles/tokens.css` keeps its `--syn-*` names and RGB-channel
format (every existing utility restyles in place) but every value is
transcribed from the rebuilt `dist/tokens.json` `rgb255` fields — never
hand-converted. **Tier becomes the H258 lightness ramp** (the
emerald/sky/amber/rose fork dies). The chromatics mirror test extends to pin
surfaces/tier/brand and the MapLibre/deck literals against dist, so drift is
a failing test rather than a review hope.

### D5 — Versioning ruling: 1.2.0 (minor)

The emitted token API (names, structure, themes) is byte-compatible;
consumers bind to semantic names whose behavioural contract is "passes the
INV-CLR contrast/CVD/gamut gates", and that contract is preserved by
construction; frozen identity hues are untouched. ADR-025 ties major bumps to
API/meaning changes, not value tuning. (Strict semver-on-values → 2.0.0 was
considered and rejected: nothing can break for a gate-compliant consumer.)

## Consequences

- The dark console gains real depth without borders; panel chrome quiets down
  so the chromatic signals (agent hues, tier ramp, confidence scale, honesty
  states) carry more of the meaning — PR-CLR-002 "every hue is earned" now
  applies to borders too.
- Primitive neutral keys were renamed to stay honest to their L×1000 naming
  (primitives are build-time only; no emitted-API change). Unused mid-step
  `620` is reserved as the documented deck.gl neutral mirror source.
- `dist/` regenerated deterministically and committed (INV-CLR-010).

## Alternatives rejected

- **Warm graphite / abyssal teal canvases** — offered to the operator; cold
  void chosen (the cognition-blue brand and agent hues glow against it).
- **Importing dist/tokens.css directly into the FE build** — couples the FE
  build graph to the design-system build and loses the RGB-channel format
  Tailwind's alpha modifiers need; the pinned mirror gives value-identity
  with an enforced test instead.
- **Borderless in all three themes** — fails AAA in `hc`; per-theme depth
  encodings instead.
