import type { Preview } from "@storybook/react";
import "../src/styles/globals.css";

/**
 * Global Storybook preview config — Synaptic Calm canvas, a11y gate.
 */
const preview: Preview = {
  parameters: {
    layout: "centered",
    backgrounds: {
      default: "void",
      values: [
        { name: "void", value: "#05070D" },
        { name: "paper", value: "#0C111B" },
        { name: "elevated", value: "#141B2A" },
      ],
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    // Accessibility violations fail the story (plan 10.2 a11y budget).
    a11y: {
      test: "error",
    },
  },
};

export default preview;
