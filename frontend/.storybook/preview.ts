import type { Preview } from "@storybook/react";
import { type Theme, applyTheme, useThemeStore } from "../src/state/theme.store";
import "../src/styles/global.css";

/**
 * The SYNAPSE surfaces a story is drawn on (finding 130), as the backgrounds
 * addon's swatches. Each value is the surface's own token, so axe judges a story
 * against a colour the product paints, never one of Storybook's built-in
 * swatches. The addon (8.6, `values` mode) writes the chosen value as
 * `background: <value> !important` on `<body class="sb-show-main">`, the element
 * behind `#storybook-root`. Being the shorthand, it also resets
 * `background-image`, so the body's ambient radial glow (src/styles/global.css)
 * gives way to a flat surface whose contrast axe can decide.
 */
const SURFACES = [
  { name: "canvas", value: "rgb(var(--syn-canvas))" },
  { name: "surface", value: "rgb(var(--syn-surface))" },
  { name: "surface-raised", value: "rgb(var(--syn-surface-raised))" },
] as const;

type SurfaceName = (typeof SURFACES)[number]["name"];

const SURFACE_NAMES = SURFACES.map((surface) => surface.name).join(", ");

const THEMES: readonly Theme[] = ["dark", "light", "hc"];

function isSurfaceName(value: unknown): value is SurfaceName {
  return SURFACES.some((surface) => surface.name === value);
}

function isTheme(value: unknown): value is Theme {
  return THEMES.some((theme) => theme === value);
}

/**
 * The theme a story's background belongs to. A surface token resolves per
 * theme, so a background is a (surface, theme) pair: `backgrounds.default` names
 * the surface, and `backgrounds.theme`, a SYNAPSE key the addon ignores, names the
 * theme, dark when absent. Either naming anything else throws, so no story is
 * judged on a colour no SYNAPSE surface has, or on a light surface drawn with the
 * dark tokens.
 */
function backgroundTheme(storyId: string, backgrounds: unknown): Theme {
  const declared: object =
    typeof backgrounds === "object" && backgrounds !== null ? backgrounds : {};
  const surface = "default" in declared ? declared.default : undefined;
  if (!isSurfaceName(surface)) {
    throw new Error(
      `story "${storyId}" sets backgrounds.default to ${JSON.stringify(surface)}, which is not a SYNAPSE surface (${SURFACE_NAMES}); see finding 130`,
    );
  }
  const theme = "theme" in declared ? declared.theme : "dark";
  if (!isTheme(theme)) {
    throw new Error(
      `story "${storyId}" sets backgrounds.theme to ${JSON.stringify(theme)}, which is not a SYNAPSE theme (${THEMES.join(", ")})`,
    );
  }
  return theme;
}

const preview: Preview = {
  parameters: {
    backgrounds: { default: "canvas", values: SURFACES },
    options: {
      storySort: { order: ["Primitives", "Compounds", "Surfaces"] },
    },
    a11y: { config: { rules: [{ id: "color-contrast", enabled: true }] } },
  },
  // The product applies the theme store to <html data-theme> (src/app/providers.tsx).
  // A story does the same before it renders, so its surface and its component resolve
  // to one theme's tokens, and a component that reads the store (CouncilStrip's glyph
  // ink) agrees with what the page paints.
  beforeEach({ id, parameters }) {
    const theme = backgroundTheme(id, parameters.backgrounds);
    useThemeStore.getState().setTheme(theme);
    applyTheme(theme);
  },
};

export default preview;
