# ADR-048: Cobalt Reversal — Blue-Forward Cinematic Identity (Chromatic v2.0.0)

**Status**: Accepted
**Date**: 2026-06-15
**Sprint**: 20 (post — operator-directed visual overhaul)
**Relates to**: ADR-025 (chromatic system), ADR-045 (Obsidian visual identity), ADR-046 (warm-graphite neutralization), INV-CLR-002/003/004/005/006/007/012/014/015/016, I-1
**Supersedes (in part)**: ADR-046 §D1 (warm-graphite H75 neutrals), §D2 (warm-brass H65 brand/tier/focus), and §D3 ("keep exactly one measured blue")

## Context

ADR-046 (one sprint prior) moved the SYNAPSE foundation and signature *off*
blue — warm-graphite (H75) neutrals and a warm-brass (H65) brand/tier/focus
ramp — on the rationale that an all-blue interface "read like a generic
AI-generated vibe." That was a sound call for that palette.

The operator has now directed the opposite: a deliberate, cinematically-argued
**blue-forward identity**. The brief draws on colour-grading practice —
*monochromatic harmony* (a single dominant hue family), *complementary
contrast* (a saturated warm pop against a cool field to draw the eye), and
*cinematic shadows* (dark areas tinted cool rather than dead-neutral). The goal
is a premium "highest quality blue" as the system signature, with the legacy
amber/gold/dark-goldenrod accent retired.

This reverses ADR-046's hue decisions. It is recorded as a superseding ADR
(not a silent edit) so the governance trail stays honest, and it is executed
inside the existing mechanical gate — the design-system's own 58-test, 7-layer
spec suite plus the frontend drift-killer (`chromatics.test.ts`) — so every
WCAG/APCA/CVD/monotonicity invariant still holds.

## Decision

> **Quiet cool foundation, loud meaning, warm pop.** A near-neutral *cool*
> foundation; one rationed cobalt accent as the signature; saturated colour
> reserved for meaning; and warm (orange/red) caution as the deliberate
> complementary contrast that makes the blue read as dominant.

### D1 — Foundation → cool blue-graphite (H250, near-neutral)

`ref.neutral` moves from **H75 warm graphite** to **H250 (a faint cool
blue-graphite)**. Chroma rises with depth (dark steps ~0.013–0.016) so the
darkest surfaces read as cinematic blue-tinted shadow rather than dead grey;
the lighter steps stay near-achromatic so light-theme surfaces remain
near-white. **Lightness steps are unchanged**, so the borderless-depth contrast
model and every WCAG/APCA pairing survive untouched. `state.neutral` follows
the foundation to H250.

### D2 — Brand / focus / tier → royal cobalt (H250), rationed

The SYNAPSE signature moves from **H65 warm brass** to **H250 royal cobalt**.
The *contrast structure is unchanged* — only the hue rotates:

- **Brand** stays rationed to one primary action per surface. Dark theme: a
  bright cobalt base (`#7cbdff`) carries a near-black label (clears APCA
  secondary ≥60 + WCAG AA). Light theme: a deeper cobalt base (`#0060a6`)
  carries a white label.
- **Tier** stays an ordinal **Lightness** ramp (INV-CLR-006 unchanged: L
  strictly decreases Tier 1→4) on the cobalt hue, chroma modest (0.05–0.105),
  light cobalt (Tier 1) deepening to deep cobalt (Tier 4).
- **Focus ring** follows to H250.

### D3 — Retire the gold; warm caution becomes the complementary pop

The amber/gold/dark-goldenrod accent is gone. Two semantic golds move off gold
but stay *warm* — they cannot become blue without breaking invariants, and as
warm signals against the cobalt field they ARE the complementary contrast:

- **`state.warning`** → **orange (H50)**, lightness-staggered above `danger`
  (red H26) so the two warm states survive CVD (INV-CLR-014/015).
- **confidence `caution`** (the 0.70 escalation band) → **orange (H55)**. The
  diverging scale stays strictly hue-increasing red(27)→orange(55)→green(150)→
  teal(184), so INV-CLR-007 holds; a blue midpoint would have violated it.
- **`state.degraded`** follows warning to a drained orange (chroma ≤0.08 and
  ≥0.05 below every full state — INV-CLR-016).

`state.info` (H248) is no longer "the *only* blue" (ADR-046 §D3 retired) — it
remains the measured info/pending blue and coexists with the cobalt chrome, as
it did pre-ADR-046.

### D4 — Pricing-oracle agent re-hued (INV-CLR-012 version-bump clause)

`pricing_oracle` was the one amber-gold agent identity. It is re-hued to
**deep blue-violet (H80 → H270)**, placed in the wide H248..H292 gap with a
strongly staggered lightness (dark L0.50 / light L0.37) so it clears the ≥20°
hue, ΔEok ≥0.090 normal-vision (INV-CLR-004), and ΔEok ≥0.020 CVD (INV-CLR-005)
floors against `routing_navigator` (azure H248) and `demand_prophet`
(indigo-violet H292). INV-CLR-012 permits a frozen-hue change *with a version
bump + a supersede note* — this ADR is that note. The other 7 agent hues are
unchanged.

## Consequences

- **Positive**: the product reads as a considered, blue-forward operational
  console; the cool ground + cobalt chrome + warm caution pops realise the
  cinematic brief (monochromatic harmony + complementary contrast + cool
  shadows). All **58/58** chromatic spec tests pass; the orthogonal-encoding
  principle and the tier/confidence monotonicity invariants are intact.
- **Cost**: a Chromatic **v2.0.0** major bump (it changes a frozen agent
  identity, hence major not minor); `dist/` regenerated and committed; the
  frontend `tokens.css` mirror + `chromatics.ts` confidence stops +
  `chromatics.test.ts` pins + MapLibre/deck.gl viz-literal mirrors
  re-transcribed from the new `dist/tokens.json` (the drift-killer enforces it).
- **Neutral**: no token *roles*, API, or component contracts change — surfaces
  are still surfaces, tier is still ordinal lightness, the brand/agent var
  names are unchanged; this is a hue/value rotation, not a structural change.
- **Note**: ADR-046's *first-principle* reasoning ("a blue-tinted neutral is
  decorative; the neutral's job is to recede") is consciously traded here for
  the operator's cinematic intent. The cool neutral is kept near-achromatic and
  the cobalt accent rationed precisely to keep that tension in check.
