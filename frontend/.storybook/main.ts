import type { StorybookConfig } from "@storybook/react-vite";

/**
 * Storybook — the design-system workbench and visual-regression source.
 * Every primitive and meaningful component ships a story (plan 9.5).
 */
const config: StorybookConfig = {
  stories: ["../src/**/*.mdx", "../src/**/*.stories.@(ts|tsx)"],
  addons: [
    "@storybook/addon-essentials",
    "@storybook/addon-a11y",
    "@storybook/addon-interactions",
  ],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  core: {
    // No phone-home telemetry — aligns with invariant I-1 / tenet T-12.
    disableTelemetry: true,
  },
  typescript: {
    reactDocgen: "react-docgen-typescript",
  },
};

export default config;
