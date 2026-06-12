# Self-hosted fonts — provenance & licensing (I-1: $0, no paid services)

All three families are licensed under the **SIL Open Font License 1.1**
(free for any use, including commercial; embedding/self-hosting permitted).
Fetched 2026-06-11. No font CDN is contacted at runtime (FE-INV-001).

| File | Family | Source |
|---|---|---|
| `InterVariable.woff2` | Inter Variable (wght 100–900) | https://rsms.me/inter/font-files/InterVariable.woff2 (rsms/inter v4.x, OFL-1.1) |
| `SpaceGrotesk[wght].woff2` | Space Grotesk Variable (wght 300–700, latin subset) | https://cdn.jsdelivr.net/fontsource/fonts/space-grotesk:vf@latest/latin-wght-normal.woff2 (floriankarsten/space-grotesk via Fontsource, OFL-1.1) |
| `JetBrainsMono-{Regular,Medium,Bold}.woff2` | JetBrains Mono 400/500/700 | https://github.com/JetBrains/JetBrainsMono `fonts/webfonts/` (OFL-1.1) |

Roles (ADR-045): Space Grotesk = display (titles, brand, KPI numerals);
Inter Variable = body/UI; JetBrains Mono = ids, data, tabular numerals.
`@font-face` rules live in `frontend/src/styles/fonts.css`; the two
paint-critical variable files are preloaded from `index.html`.
