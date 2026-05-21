import type { Preview } from "@storybook/react";
import { withThemeByDataAttribute } from "@storybook/addon-themes";
import { initialize, mswLoader } from "msw-storybook-addon";

import "../src/shared/design-tokens/index.css";

// SYNAPSE Atlas Console — Storybook preview.
//
// - Theme decorator flips [data-theme] so light + dark are first-class.
// - MSW initialised once; surfaces register handlers per-story.
// - axe-a11y rules: AAA contrast on stories tagged "a11y-aaa" (plan §12).
//   Component-level overrides via parameters.a11y.config.

initialize({
  onUnhandledRequest: "warn",
  serviceWorker: { url: "./mockServiceWorker.js" },
});

const preview: Preview = {
  parameters: {
    layout: "padded",
    controls: { expanded: true, sort: "alpha" },
    backgrounds: { disable: true }, // theme decorator owns the background
    a11y: {
      element: "#storybook-root",
      config: {
        // Default to AA app-wide; AAA stories opt in via parameters.
        rules: [
          { id: "color-contrast", enabled: true },
          { id: "color-contrast-enhanced", enabled: false },
        ],
      },
      options: {},
    },
    docs: {
      toc: true,
    },
  },
  loaders: [mswLoader],
  decorators: [
    withThemeByDataAttribute({
      themes: { light: "light", dark: "dark" },
      defaultTheme: "dark",
      attributeName: "data-theme",
    }),
  ],
  globalTypes: {
    locale: {
      description: "i18n locale",
      defaultValue: "en-IN",
      toolbar: {
        title: "Locale",
        icon: "globe",
        items: [
          { value: "en-IN", title: "English (India)" },
          { value: "hi-IN", title: "हिन्दी (India)" },
          { value: "kn-IN", title: "ಕನ್ನಡ" },
          { value: "mr-IN", title: "मराठी" },
        ],
        dynamicTitle: true,
      },
    },
    city: {
      description: "Active city (multi-city per plan §1)",
      defaultValue: "bengaluru",
      toolbar: {
        title: "City",
        icon: "globe",
        items: [
          { value: "bengaluru", title: "Bengaluru" },
          { value: "mumbai", title: "Mumbai" },
        ],
        dynamicTitle: true,
      },
    },
  },
  tags: ["autodocs"],
};

export default preview;
