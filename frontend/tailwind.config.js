// SYNAPSE HITL Console — Tailwind configuration.
// Colour, radius, motion utilities are bound to the SYNAPSE Chromatic System
// via its generated preset (design-system/color). Never hard-code a colour
// here — the no-raw-hex gate (INV-CLR-009) will reject it.
import chromatic from "../design-system/color/dist/tailwind-preset.cjs";

/** @type {import('tailwindcss').Config} */
export default {
  presets: [chromatic],
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px oklch(0 0 0 / 0.30), 0 8px 24px -12px oklch(0 0 0 / 0.45)",
        raised: "0 2px 4px oklch(0 0 0 / 0.34), 0 16px 40px -16px oklch(0 0 0 / 0.55)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(2px)" }, to: { opacity: "1", transform: "none" } },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 var(--pulse-color, transparent)" },
          "70%, 100%": { boxShadow: "0 0 0 10px transparent" },
        },
        sheen: { "0%": { backgroundPosition: "0% 50%" }, "100%": { backgroundPosition: "200% 50%" } },
      },
      animation: {
        "fade-in": "fade-in var(--motion-duration-base, 200ms) var(--motion-ease-decelerate, ease-out)",
        "pulse-ring": "pulse-ring var(--motion-duration-pulse, 2400ms) var(--motion-ease-emphasized, ease) infinite",
        sheen: "sheen 6s linear infinite",
      },
    },
  },
  plugins: [],
};
