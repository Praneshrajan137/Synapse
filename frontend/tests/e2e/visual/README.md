# Visual Regression Gate (Req 14)

Deterministic screenshot diffing for the SYNAPSE Console's key Surfaces, using
**only** Playwright's built-in `toHaveScreenshot()` — a $0-cost / OSS tool
already in the stack. **No paid visual-diffing SaaS is used** (Req 14.6, 20.2).

## What it covers

`visual-regression.spec.ts` captures a defined set of key Surfaces across every
`Theme_Mode` and diffs each against a committed baseline:

| Surface           | Route         | Theme_Mode |
| ----------------- | ------------- | ---------- |
| mission-control   | `/`           | light      |
| mission-control   | `/`           | dark       |
| mission-control   | `/`           | hc         |
| override-cockpit  | `/cockpit`    | dark       |
| decision-theater  | `/decisions`  | light      |
| audit-vault       | `/audit`      | hc         |

Mission Control is captured in **all three** Theme_Modes so a Chromatic_Token
regression in any mode is caught (Req 14.5).

## Determinism (Req 14.1, 14.3)

Every capture is made non-flaky by:

- **Fixed viewport** — pinned per test (1280×800).
- **Fixed theme** — forced through the persisted `synapse.theme` store before
  the app boots, asserted via `<html data-theme>`.
- **Fixed seed** — the page clock is frozen so every `relativeTime` render is
  stable; when the Effectiveness_Harness is wired, its deterministic fixtures
  are seeded too.
- **Disabled animation** — reduced-motion emulation + an all-animations-off
  stylesheet + `animations: "disabled"`.
- **Fixed fonts** — font-smoothing pinned and `document.fonts.ready` awaited.
- **Masked volatile regions** — live WebGL canvases and `aria-live` streaming
  regions are masked out of the diff.

The diff threshold is defined centrally in `playwright.config.ts`
(`expect.toHaveScreenshot`).

## Running the gate

```bash
# Compare against committed baselines (what CI runs — the `e2e-visual` job):
pnpm test:visual
```

A failing diff names the changed Surface + Theme_Mode via the snapshot name
(`<surface>-<theme>`), and the full diff image is uploaded as the
`visual-regression-report` CI artifact (Req 14.2).

## Updating the baseline for an approved change (Req 14.4)

When a visual change is intentional, advance the committed baseline and commit
the regenerated PNGs:

```bash
pnpm test:visual:update
```

> **Platform note.** Playwright screenshots are platform-specific (baselines are
> suffixed, e.g. `-visual-linux.png`). The committed baselines must be generated
> on the **same Linux/Chromium runner CI uses**. Generate/refresh them either in
> CI (download the `visual-regression-report` artifact, or run
> `pnpm test:visual:update` in a Linux container matching the CI image) and
> commit the resulting files under
> `tests/e2e/visual/visual-regression.spec.ts-snapshots/`. Do not commit
> baselines generated on macOS/Windows — they will not match the Linux gate.
