# ADR-046: Warm-Graphite Neutralization — Quiet Foundation, Loud Meaning (Chromatic v1.3.0)

**Status**: Accepted
**Date**: 2026-06-14
**Sprint**: 17 (Living Interface — Visual Reinvention)
**Relates to**: ADR-025 (chromatic system), ADR-045 (Obsidian visual identity — supersedes its colour rationale, NOT its typography/borderless-depth decisions), INV-CLR-002/003/006/012/015, I-1
**Supersedes (in part)**: ADR-045 §D1 (cold-void H265 neutrals) and the H258 brand/tier hue

## Context

ADR-045 made the interface honest and gave it real fonts + borderless depth.
But it chose a **deep blue-violet (H265)** neutral void with the brand, focus
ring, and the entire decision-tier ramp on **H258 ("cognition blue")**. The
result: every surface, panel, border, and primary affordance was tinted blue.

Two problems followed:

1. **The blue dominated as *decoration*, not meaning.** SYNAPSE already encodes
   enormous meaning in colour — 8 agent identities (Hue), 4 tiers (Lightness), a
   continuous confidence scale (diverging), and 7 semantic states. With the
   whole canvas tinted blue and the chrome (brand/tier/focus) *also* blue, the
   foundation competed with the data it was supposed to frame. The product
   owner's verdict was blunt and correct: it read like a generic, "AI-generated
   vibe" interface rather than a considered operational console.
2. **Decorative hue violated the system's own first principle.** PR-CLR-002 —
   "every hue is earned; no decorative or arbitrary colour." A blue-tinted
   *neutral* is, by definition, decorative: the neutral's job is to recede.

## Decision

Adopt the principle the best data-dense operational consoles converge on
(Linear, Vercel, Stripe; corroborated by Carbon/IBM and arXiv 2107.02270
data-viz accessibility guidance, and OKLCH luminance-first palette practice):

> **Quiet foundation, loud meaning.** A near-neutral foundation, one *rationed*
> accent, and saturated colour reserved strictly for semantic meaning — high
> contrast, no muddy mid-tones. The richness comes from the *meaning-bearing*
> palette popping against a quiet ground, not from tinting the ground.

### D1 — Neutral foundation → warm graphite (H75, near-neutral)

`ref.neutral` moves from **H265 blue-violet** to **H75 (a faint warm
graphite)** at *roughly half* the previous chroma (dark steps 0.008–0.010 vs
0.014–0.018). It is deliberately near-achromatic so it recedes; the residual
warmth keeps the darkest surfaces from reading as dead grey (the ADR-045 goal,
re-expressed without a dominant hue). Lightness steps are **unchanged**, so the
borderless-depth contrast model and every WCAG/APCA pairing survive untouched.

| Role (dark) | v1.2.0 (H265) | v1.3.0 (H75) |
|---|---|---|
| canvas | `#0c0e13` blue-black | **`#0a0805`** warm graphite |
| panel  | bluish | **`#14110d`** |
| raised | bluish | **`#1f1b17`** |
| overlay| bluish | **`#2d2a25`** |

### D2 — Brand / focus / tier → warm-brass signature (H65), rationed

The SYNAPSE signature (brand, focus ring, decision-tier cognition ramp) moves
from **H258 blue** to **H65 (warm brass-gold)**:

- **Brand** is *rationed* to one primary action per surface. Dark theme: a
  bright gold base (`#f9aa58`) carries a near-black label (clears APCA
  secondary). Light theme: a deeper bronze base carries white (gold is
  intrinsically light, so the solid affordance is darkened for white-text
  contrast).
- **Tier** stays an ordinal **Lightness** ramp (INV-CLR-006 unchanged: L
  strictly decreases Tier 1→4) on the brass hue, with chroma kept *modest*
  (0.05–0.105) so tier reads as ordered lightness — "quiet chrome" — light gold
  (Tier 1) deepening to bronze (Tier 4). Conceptually coherent: the brand *is*
  the cognition hue, and tiers are cognition depth.

### D3 — Keep exactly one measured blue

`state.info` stays **H248**. Info/pending is conventionally blue; it remains the
*only* blue in the system and is used purely for meaning, satisfying "a little
blue is fine, just not dominant."

### D4 — Agent hues stay FROZEN (INV-CLR-012)

No agent identity hue changes. This is an additive neutral/chrome retune, not an
identity change. `state.neutral` follows the foundation to H75 and is separated
from the chroma-drained `degraded` state by lightness (L 0.66 dark) to hold the
INV-CLR-015 7-state distinctness floor.

## Consequences

- **Positive**: the blue/violet domination is gone; the agent/confidence/state
  colours read as vivid and intentional against a quiet ground; the foundation
  now *obeys* PR-CLR-002 (earned hue). All 58 chromatic spec tests pass; the
  orthogonal-encoding principle and INV-CLR-012 frozen agents are untouched.
- **Cost**: a Chromatic **v1.3.0** version bump; `dist/` regenerated and
  committed; the frontend `tokens.css` mirror + `chromatics.test.ts` pins +
  viz-literal mirrors re-transcribed from the new `dist/tokens.json` (the
  drift-killer test enforces this).
- **Neutral**: the change is value-only — no token *roles*, API, or component
  contracts change. Surfaces are still surfaces; tier is still ordinal
  lightness; the brand var name is unchanged.
