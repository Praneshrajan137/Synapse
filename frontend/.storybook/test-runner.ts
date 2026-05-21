import type { TestRunnerConfig } from "@storybook/test-runner";
import { getStoryContext } from "@storybook/test-runner";
import { injectAxe, checkA11y, configureAxe } from "axe-playwright";

// SYNAPSE Atlas Console — Storybook test-runner config.
// Runs every story through Playwright; axe-a11y is enforced.
//
// AAA-tagged stories raise the bar to color-contrast-enhanced (7:1) per
// plan §12 / ADR-028. Storybook story tags drive the configuration so a
// component author can ship a single AAA story alongside the AA default.

const config: TestRunnerConfig = {
  async preVisit(page) {
    await injectAxe(page);
  },
  async postVisit(page, context) {
    const storyContext = await getStoryContext(page, context);
    const tags: string[] = storyContext.tags ?? [];
    const isAAA = tags.includes("a11y-aaa");

    await configureAxe(page, {
      rules: [
        { id: "color-contrast", enabled: !isAAA },
        { id: "color-contrast-enhanced", enabled: isAAA },
      ],
    });

    await checkA11y(page, "#storybook-root", {
      detailedReport: true,
      detailedReportOptions: { html: false },
      axeOptions: {
        runOnly: {
          type: "tag",
          values: isAAA ? ["wcag2aaa", "wcag2aa", "wcag21aa"] : ["wcag2aa", "wcag21aa"],
        },
      },
    });
  },
};

export default config;
