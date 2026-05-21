# ADR-028: Storybook a11y AAA tagging for safety-critical components

## Status
Accepted (S6)

## Context
WCAG 2.2 AA contrast (4.5:1 on normal text, 3:1 on large) is the
project-wide bar. Three classes of UI carry safety-critical meaning
beyond AA:

- **Pricing-cap badges** (I-6 essential ≤ 1.3×).
- **Freshness ≤ 6h pins / banners** (Freshness Guardian).
- **Disruption tier-4 banner** + Mission Control urgency bar.

A misread on any of these can ship a regulatory or freshness violation
under low-ambient control-room lighting. We need a per-component
guarantee, not just an audit.

## Decision

Storybook stories that surface a safety-critical state are tagged
**`a11y-aaa`**. The Storybook test-runner (`.storybook/test-runner.ts`)
flips the axe configuration when it sees the tag:

- AA stories run `wcag2aa` + `wcag21aa` rule sets.
- AAA-tagged stories additionally enable
  `color-contrast-enhanced` (WCAG AAA, 7:1).

The token palette in `frontend/src/shared/design-tokens/tokens.css`
already defines AAA-clearing safety colours (`--color-safety-critical`
etc.) on both light and dark themes. CI fails the visual gate if any
AAA-tagged story regresses.

`CODEOWNERS` requires design + a11y review on token changes
(`frontend/src/shared/design-tokens/`) and on the AAA-tagged stories
themselves.

## Consequences

### Positive
- Author-time enforcement: a contrast regression in an AAA component
  fails CI on the PR that introduced it.
- Clear, named contract: a single grep
  (`grep -r 'a11y-aaa' src/surfaces`) lists every safety-critical
  surface.
- Token-driven palette means a theme change can never accidentally
  drop AAA below 7:1 — the test guards the assumption.

### Negative
- AAA-grade colour ranges are narrow; designers lose some palette
  freedom on safety-critical surfaces. We accept the trade-off.
- AA-only surfaces still need vigilance — the test does not run
  `color-contrast-enhanced` there.

## References
- Plan §12 (Security & compliance) and the Storybook test-runner
  config at `frontend/.storybook/test-runner.ts`.
- Critical files registry: `docs/security/frontend-threat-model.md`.
