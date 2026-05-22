import type { Preview } from "@storybook/react";
import "../src/styles/global.css";

const preview: Preview = {
  parameters: {
    backgrounds: { default: "synapse-dark" },
    options: {
      storySort: { order: ["Primitives", "Compounds", "Surfaces"] },
    },
    a11y: { config: { rules: [{ id: "color-contrast", enabled: true }] } },
  },
};

export default preview;
