import { AxeBuilder } from "@axe-core/playwright";
import type { TestRunnerConfig } from "@storybook/test-runner";

/**
 * SYNAPSE Console -- every Storybook story judged by axe-core (FE-INV-031).
 *
 * `.github/workflows/frontend.yml::storybook-a11y` serves the static Storybook build and runs
 * `pnpm storybook:test` (@storybook/test-runner 0.19.1) against it. The test-runner renders
 * each story in Chromium; `postVisit` below then runs axe-core over the story's root and
 * throws when axe reports a violation, so that story's test fails and the job fails with it.
 *
 * What is checked:
 * - the WCAG 2.0 and 2.1 level A and AA rules (`WCAG_TAGS`); best-practice rules are not;
 * - inside `#storybook-root`, the element Storybook 8 renders a story into, so page-level
 *   rules about Storybook's own iframe document (title, lang, landmarks) do not apply;
 * - every story export. `tags` admits every tag, so a story cannot leave the run with
 *   `!test`, and `parameters.a11y` is never read, so a story's addon settings cannot turn a
 *   rule off;
 * - with motion at rest. `preVisit` emulates prefers-reduced-motion, as
 *   tests/e2e/visual/visual-regression.spec.ts does, so framer-motion and CSS transitions are
 *   at rest, and the backgrounds addon drops its 0.3 s colour transition, when axe reads
 *   colours.
 *
 * What is not checked: nodes outside the root, such as a portal into document.body; the
 * full-motion rendering; and checks axe reports as incomplete because it could not decide
 * them (colour contrast over a background gradient or an SVG is the usual one). Incomplete
 * checks are printed per story and do not fail it. A root with nothing in it fails the
 * story, because zero violations over an empty root says nothing (I-7).
 */

/** The axe-core tags for WCAG 2.0 and 2.1, levels A and AA. */
const WCAG_TAGS: string[] = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/** Where Storybook 8 renders a story; the test-runner's own render wait looks for it too. */
const STORY_ROOT = "#storybook-root";

type AxeResults = Awaited<ReturnType<AxeBuilder["analyze"]>>;
type AxeResult = AxeResults["violations"][number];
type AxeTarget = AxeResult["nodes"][number]["target"];

/** One node's selector path, frame by frame; a shadow-DOM step is joined with `>>`. */
function formatTarget(target: AxeTarget): string {
  return target.map((step) => (Array.isArray(step) ? step.join(" >> ") : step)).join(" -> ");
}

/** The failure message: each violation's id, impact and help, then every node it names. */
function describeViolations(storyId: string, violations: readonly AxeResult[]): string {
  const lines = [
    `axe-core found ${violations.length} WCAG A/AA violation(s) in story "${storyId}" (FE-INV-031):`,
  ];
  for (const violation of violations) {
    lines.push(
      `- ${violation.id} (impact: ${violation.impact ?? "none given"}): ${violation.help} (${violation.helpUrl})`,
    );
    for (const node of violation.nodes) {
      lines.push(`    target: ${formatTarget(node.target)}`);
      for (const detail of (node.failureSummary ?? "").split("\n")) {
        if (detail.trim() !== "") lines.push(`      ${detail.trim()}`);
      }
    }
  }
  return lines.join("\n");
}

/** `rule xN` for each rule axe could not decide, N being the nodes it left undecided. */
function describeIncomplete(incomplete: readonly AxeResult[]): string {
  return incomplete.map((result) => `${result.id} x${result.nodes.length}`).join(", ");
}

const config: TestRunnerConfig = {
  // Every story export is a test. test-runner 0.19.1 falls back to include ["test"] only when
  // `tags.include` is absent, and an empty include list admits every story.
  tags: { include: [], exclude: [], skip: [] },

  async preVisit(page) {
    await page.emulateMedia({ reducedMotion: "reduce" });
  },

  async postVisit(page, context) {
    const markup = await page.locator(STORY_ROOT).evaluate((root) => root.innerHTML.trim());
    if (markup === "") {
      throw new Error(
        `story "${context.id}" rendered nothing into ${STORY_ROOT}, so there is nothing for axe to judge (FE-INV-031)`,
      );
    }

    const results = await new AxeBuilder({ page })
      .include(STORY_ROOT)
      .withTags(WCAG_TAGS)
      .analyze();

    if (results.incomplete.length > 0) {
      console.warn(
        `[axe] ${context.id}: not judged, axe could not decide: ${describeIncomplete(results.incomplete)}`,
      );
    }
    if (results.violations.length > 0) {
      throw new Error(describeViolations(context.id, results.violations));
    }
  },
};

export default config;
