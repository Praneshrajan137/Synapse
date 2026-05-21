# ADR-025: OKLCH Perceptual Color System (SYNAPSE Chromatic System)

## Status
Accepted

## Context
The HITL Console (`frontend/`) had no color system. Every color was a raw hex
literal hard-coded inside inline `style={{}}` objects — duplicated across 17
files, unmeasured for contrast, and untyped to any domain meaning. Tailwind was
installed but never configured.

The platform must render three independent data types *at once*: which of the
8 agents acted (nominal), which of the 4 decision tiers ran (ordinal — I-8),
and how confident the system was (continuous, gated at 0.70/0.80 — I-5).
Encoding all three in arbitrary hand-picked colors guarantees collisions and
gives an operator no perceptual handle on the data.

There is also an accessibility obligation: operators work long shifts in
low-ambient control rooms, ~8% of male operators have a color-vision
deficiency, and the console is a safety-relevant surface where a misread
escalation has real cost.

## Decision
Adopt a spec-governed, perceptually-grounded color system — the **SYNAPSE
Chromatic System** — built as a portable token core at `design-system/color/`.

1. **Color space — OKLCH.** All tokens are authored in OKLCH (CSS Color 4,
   Baseline 2023). OKLCH is perceptually uniform, so its three axes —
   Lightness, Chroma, Hue — are independent and meaningful, which hex and HSL
   are not.

2. **The Orthogonal Encoding Principle.** Each data type is mapped to the
   OKLCH axis that natively fits it:
   - Agent identity (nominal) → **Hue** — 8 earned hues around the wheel.
   - Decision tier (ordinal) → **Lightness** — a strictly monotonic ramp (I-8).
   - Confidence (continuous) → a **diverging scale** interpolated in OKLab,
     anchored at the exact I-5 gates (0.70 / 0.80).

3. **Three-tier token architecture (W3C DTCG format).** Primitive →
   semantic → component tokens in JSON, compiled by a deterministic Node
   build (`culori` only) into four artifacts: `tokens.css` (CSS custom
   properties, light + dark), `tokens.ts` (typed API incl. `[r,g,b]` arrays
   for deck.gl), `tailwind-preset.cjs`, and `tokens.json`.

4. **Spec-first governance.** `color-system.spec.yml` declares 14 `INV-CLR`
   invariants; every one has a test (`scripts/check-spec-coverage.mjs`
   enforces this). All 7 repo testing layers apply — notably theme inversion
   and color-vision-deficiency simulation are modelled as metamorphic
   transforms.

5. **Dual contrast model.** Tokens are validated against **WCAG 2.1 AA**
   (the legal conformance baseline) *and* **APCA** (the perceptual
   WCAG-3-draft method, implemented in-repo from the published APCA-W3 0.1.9
   constants). APCA is applied with tiered Lc targets by text emphasis
   (primary 75 / secondary 60 / tertiary 45) — its intended contextual use.

6. **Color is never the sole channel (INV-CLR-011).** Every color-coded
   state also carries a label, glyph, or shape. This is the primary
   accessibility guarantee; CVD distinctness (INV-CLR-005) is the strong
   secondary one.

## Consequences
**Easier.** Theming (light/dark) is a CSS-variable swap. Contrast and CVD
safety are machine-verified and regression-proof. New surfaces consume one
typed token API. The core is portable — the in-progress TS "Atlas Console"
redesign can adopt the same artifacts.

**Harder / accepted trade-offs.**
- 8-way categorical color is inherently hard under *full* dichromacy; the
  agent palette is tuned for maximum separation (lightness is staggered, not
  held equal) and the residual risk is covered by INV-CLR-011, not pretended
  away.
- Agent hue families intentionally overlap the semantic state hues
  (disruption is red, like danger; pricing is gold, like warning). They are
  kept apart by **disjoint UI roles** — agent color appears only on identity
  affordances, state color only on status — not by hue distance. INV-CLR-014
  therefore verifies the *state palette's* internal distinctness, not an
  agent-vs-state distance.
- The `color-system.spec.yml` file is deliberately named `.spec.yml` (not
  `spec.yaml`) so the repo's agent `spec-validate` hook does not validate it
  against the agent schema; a dedicated `color-spec-validate` hook is added.
- APCA is a WCAG-3 *draft*; it is used as a perceptual signal alongside — not
  instead of — conformant WCAG 2.1.

## Alternatives Rejected
- **Keep sRGB hex / HSL.** No perceptual axes — the Orthogonal Encoding
  Principle is impossible; contrast cannot be reasoned about; rejected.
- **Tailwind default palette (the worktree's `tokens.css` approach).**
  sRGB slate/blue ramps, equal-energy categorical colors, WCAG-2 only. Flat,
  not CVD-staggered, no agent identities; rejected as below the bar.
- **Material You / runtime color extraction.** Over-engineered for an ops
  console; non-deterministic; rejected.
- **Style Dictionary for the build.** Capable but heavier; a ~200-line
  `culori`-only build keeps the dependency surface minimal (I-1) and the
  output deterministic (INV-CLR-010); rejected in favor of the custom build.
- **An external APCA package.** License of `apca-w3` is not on the I-1
  allow-list; the algorithm is published, so it is implemented in-repo
  instead.
