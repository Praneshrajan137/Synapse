import type { StorybookConfig } from "@storybook/react-vite";

// SYNAPSE Atlas Console — Storybook config.
//
// Stories live alongside source under src/surfaces/*/stories/. The a11y addon
// runs axe on every story; AAA-tagged stories enforce 7:1 contrast (plan §12).
// MSW handlers are registered globally via msw-storybook-addon so component
// fetches resolve against the same mock fixtures used in Vitest contract tests.
const config: StorybookConfig = {
  stories: [
    "../src/**/*.mdx",
    "../src/**/*.stories.@(ts|tsx)",
  ],
  addons: [
    "@storybook/addon-essentials",
    "@storybook/addon-interactions",
    "@storybook/addon-themes",
    "@storybook/addon-a11y",
    "msw-storybook-addon",
  ],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  typescript: {
    check: false,
    reactDocgen: "react-docgen-typescript",
  },
  staticDirs: ["../public"],
  docs: { autodocs: "tag" },
  core: { disableTelemetry: true, disableWhatsNewNotifications: true },
};

export default config;
