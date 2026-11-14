/**
 * Every text ProposalConstellation draws clears 4.5:1 on what it is painted on (finding 133).
 *
 * It drew agent tokens as text: the Pricing Oracle's read 3.15:1 on the dark canvas and 2.97:1
 * on the dark surface, and a dimmed node at opacity 0.28 stayed a control. The inks are read
 * from the rendered classes and judged in every theme: the initials against the node's fill,
 * and the utility label, drawn below its node, against every page surface.
 */

import {
  type AgentName,
  ProposalConstellation,
  type ProposalLike,
} from "@ds/compounds/ProposalConstellation";
import {
  PAGE_SURFACES,
  TOKEN_THEMES,
  WCAG_AA_NORMAL_TEXT,
  contrast,
  tokenIn,
  tokenRgb,
} from "@test/token-contrast";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function token(element: Element | undefined, prefix: "bg" | "text"): string {
  const use = tokenIn(element?.getAttribute("class") ?? "", prefix);
  if (use === undefined) throw new Error(`no ${prefix} token on ${element?.outerHTML}`);
  return use.name;
}

const PRICING_ORACLE: ProposalLike = {
  agent_name: "pricing_oracle",
  utility_score: 0.86,
  confidence: 0.91,
};

describe("ProposalConstellation text", () => {
  it("every text the constellation draws clears 4.5:1, in every theme", () => {
    render(<ProposalConstellation proposals={[PRICING_ORACLE]} onSelectAgent={() => undefined} />);
    const node = screen.getByRole("button", { name: /Pricing Oracle .* utility/ });
    const empty = screen.getByRole("button", { name: /Demand Prophet .* no proposal yet/ });
    const [initials, utility] = Array.from(node.querySelectorAll("span"));
    const [dimmed] = Array.from(empty.querySelectorAll("span"));
    for (const theme of TOKEN_THEMES) {
      const fill = tokenRgb(theme, token(node, "bg"));
      const onFill = (span: Element | undefined): number =>
        contrast(tokenRgb(theme, token(span, "text")), fill);
      expect(onFill(initials), `initials (${theme})`).toBeGreaterThan(WCAG_AA_NORMAL_TEXT);
      expect(onFill(dimmed), `placeholder (${theme})`).toBeGreaterThan(WCAG_AA_NORMAL_TEXT);
      for (const surface of PAGE_SURFACES) {
        const ratio = contrast(tokenRgb(theme, token(utility, "text")), tokenRgb(theme, surface));
        expect(ratio, `utility on ${surface} (${theme})`).toBeGreaterThan(WCAG_AA_NORMAL_TEXT);
      }
    }
  });

  it("a proposal not yet revealed is not a control", () => {
    render(
      <ProposalConstellation
        proposals={[PRICING_ORACLE]}
        revealed={new Set<AgentName>()}
        onSelectAgent={() => undefined}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Pricing Oracle .* not yet revealed/ }),
    ).toBeDisabled();
  });
});
